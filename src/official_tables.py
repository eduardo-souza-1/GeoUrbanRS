"""Read the published MapBiomas workbook without modifying or recalculating it."""

import csv
import hashlib
import json
import math
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
URBAN = 24
UNKNOWN = {0, 27}
AGRICULTURE = {18, 19, 20, 35, 36, 39, 40, 41, 46, 47, 48, 62}
AGRO_GROUP = AGRICULTURE | {14, 15, 9, 21}


def sheet_rows(path, name):
    with zipfile.ZipFile(path) as z:
        strings = [
            "".join(t.text or "" for t in si.findall(".//m:t", NS))
            for si in ET.fromstring(z.read("xl/sharedStrings.xml"))
        ]
        workbook = ET.fromstring(z.read("xl/workbook.xml"))
        sheet = next(s for s in workbook.find("m:sheets", NS) if s.get("name") == name)
        rid = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        rel = next(
            r for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")) if r.get("Id") == rid
        )
        target = posixpath.normpath(posixpath.join("xl", rel.get("Target"))).lstrip("/")
        with z.open(target) as stream:
            for _, row in ET.iterparse(stream, events=["end"]):
                if row.tag != "{" + NS["m"] + "}row":
                    continue
                values = {}
                for c in row:
                    if c.find("m:f", NS) is not None:
                        raise ValueError("Formula inesperada no dado bruto: " + c.get("r"))
                    v = c.find("m:v", NS)
                    if v is not None:
                        value = strings[int(v.text)] if c.get("t") == "s" else v.text
                        values[re.sub(r"\d", "", c.get("r"))] = value
                if values:
                    yield int(row.get("r")), values
                row.clear()


def records(path, name):
    rows = iter(sheet_rows(path, name))
    _, headers = next(rows)
    for rownum, row in rows:
        yield rownum, {label: row.get(col) for col, label in headers.items()}


def numeric(value):
    if value is None:
        raise ValueError("Área ausente não é zero")
    n = float(value)
    if not math.isfinite(n) or n < 0:
        raise ValueError("Área inválida")
    return n


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run():
    raw = ROOT / "data/raw/geourban_w001"
    path = raw / "biome_state_col11.xlsx"
    coverage = []
    transitions = []
    source_rows = []
    seen = set()
    for n, r in records(path, "COVERAGE_11"):
        if r["state"] != "Rio Grande do Sul":
            continue
        key = (r["biome"], int(float(r["class"])))
        if key in seen:
            raise ValueError("Cobertura duplicada")
        seen.add(key)
        coverage.append(r)
        if key[1] == 24:
            source_rows.append(
                {
                    "sheet": "COVERAGE_11",
                    "row": n,
                    "biome": r["biome"],
                    "class": 24,
                    "first_cell": f"L{n}",
                    "last_cell": f"AZ{n}",
                }
            )
    if not coverage:
        raise ValueError("RS ausente")
    seen = set()
    for n, r in records(path, "TRANSITION_11"):
        if r["state"] != "Rio Grande do Sul":
            continue
        key = (r["biome"], int(float(r["class_from"])), int(float(r["class_to"])))
        if key in seen:
            raise ValueError("Transição duplicada")
        seen.add(key)
        transitions.append(r)

    def stock(year):
        return math.fsum(
            numeric(r["y" + str(year)]) for r in coverage if int(float(r["class"])) == 24
        )

    series = [
        {
            "year": y,
            "urban_area_ha": stock(y),
            "net_change_ha": None if y == 1985 else stock(y) - stock(y - 1),
        }
        for y in range(1985, 2026)
    ]
    periods = []
    origins = []
    checks = []
    for start, end in [(y, y + 1) for y in range(1985, 2025)] + [(1985, 2025)]:
        col = f"p{start}_{end}"
        incoming = defaultdict(float)
        outgoing = 0.0
        unknown_in = 0.0
        for r in transitions:
            a, b = int(float(r["class_from"])), int(float(r["class_to"]))
            v = numeric(r[col])
            if b == 24 and a != 24:
                incoming[a] += v
            if a == 24 and b != 24:
                outgoing += v
        unknown_in = sum(incoming.get(c, 0) for c in UNKNOWN)
        gross = math.fsum(v for c, v in incoming.items() if c not in UNKNOWN)
        residual = (stock(end) - stock(start)) - (gross + unknown_in - outgoing)
        if abs(residual) > 0.01:
            raise ValueError(f"Falha de reconciliação em {start}-{end}: {residual} ha")
        # Published coverage and transition tabulations may have small pixel/edge differences.
        checks.append({"start": start, "end": end, "stock_flow_residual_ha": residual})
        periods.append(
            {
                "start": start,
                "end": end,
                "converted_to_urban_ha": gross,
                "unknown_to_urban_ha": unknown_in,
                "urban_to_other_ha": outgoing,
                "net_change_ha": stock(end) - stock(start),
                "agriculture_to_urban_ha": sum(incoming.get(c, 0) for c in AGRICULTURE),
                "pasture_to_urban_ha": incoming.get(15, 0),
                "silviculture_to_urban_ha": incoming.get(9, 0),
                "mosaic_to_urban_ha": incoming.get(21, 0),
                "agro_group_to_urban_ha": sum(incoming.get(c, 0) for c in AGRO_GROUP),
            }
        )
        if (start, end) == (1985, 2025):
            origins = [
                {
                    "class_from": c,
                    "class_to": 24,
                    "transition": c * 100 + 24,
                    "area_ha": v,
                    "origin_known": c not in UNKNOWN,
                }
                for c, v in sorted(incoming.items())
                if v > 0
            ]
    dest = ROOT / "reports/geourban_w001"
    dest.mkdir(exist_ok=True)
    write_csv(dest / "rs_urban_series.csv", series)
    write_csv(dest / "rs_urban_transitions.csv", periods)
    write_csv(dest / "rs_endpoint_origins.csv", origins)
    report = {
        "collection": 11,
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_rows": source_rows,
        "urban_1985_ha": stock(1985),
        "urban_2025_ha": stock(2025),
        "net_growth_ha": stock(2025) - stock(1985),
        "growth_percent": 100 * (stock(2025) - stock(1985)) / stock(1985),
        "endpoint_transition": periods[-1],
        "source_biomes": sorted({r["biome"] for r in coverage}),
        "coverage_rows_rs": len(coverage),
        "transition_rows_rs": len(transitions),
        "reconciliation": checks,
        "max_abs_residual_ha": max(abs(c["stock_flow_residual_ha"]) for c in checks),
        "limitations": [
            "Áreas em hectares publicadas pelo MapBiomas; ainda sem cálculo raster independente.",
            "Transição 1985–2025 informa a origem em 1985, não necessariamente a classe imediatamente anterior à primeira urbanização.",
            "Soma de entradas anuais pode contar reentradas; não equivale a pixels únicos urbanizados.",
            "Agropecuária segue o grupo 3 da legenda, incluindo silvicultura e mosaico, reportados separadamente.",
            "Não urbano não é sinônimo de rural.",
        ],
    }
    (dest / "first_statistics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in ["reconciliation", "limitations"]},
            ensure_ascii=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    run()
