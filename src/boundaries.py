"""Validate IBGE boundaries and distinguish operational lake areas from municipalities."""

import io
import json
import zipfile

import shapefile
from pyproj import CRS, Transformer
from shapely import transform
from shapely.geometry import shape
from shapely.ops import unary_union

from src.official_tables import ROOT

AREA_CRS = "+proj=laea +lat_0=-30 +lon_0=-53 +ellps=GRS80 +units=m +no_defs"
OPERATIONAL = {"4300001", "4300002"}


def read_boundaries():
    path = ROOT / "data/raw/geourban_w001/RS_Municipios_2024.zip"
    with zipfile.ZipFile(path) as z:
        if z.testzip():
            raise ValueError("ZIP corrompido")
        stem = "RS_Municipios_2024"
        crs = CRS.from_wkt(z.read(stem + ".prj").decode())
        if crs.to_epsg() != 4674:
            raise ValueError("CRS inesperado")
        enc = z.read(stem + ".cpg").decode().strip()
        reader = shapefile.Reader(
            **{ext: io.BytesIO(z.read(stem + "." + ext)) for ext in ["shp", "shx", "dbf"]},
            encoding=enc,
        )
        rows = []
        seen = set()
        for row in reader.iterShapeRecords():
            p = row.record.as_dict()
            g = shape(row.shape.__geo_interface__)
            if p["CD_MUN"] in seen or not g.is_valid or g.is_empty:
                raise ValueError("Geometria ou chave inválida")
            if p["CD_UF"] != "43":
                raise ValueError("Fora do RS")
            seen.add(p["CD_MUN"])
            rows.append((p, g))
    return rows, crs


def run():
    rows, crs = read_boundaries()
    project = Transformer.from_crs(crs, AREA_CRS, always_xy=True)
    polygons = [transform(g, project.transform, interleaved=False) for _, g in rows]
    merged = unary_union(polygons)
    overlap = sum(g.area for g in polygons) - merged.area
    if overlap > 1:
        raise ValueError("Sobreposição municipal material")
    report = {
        "features": len(rows),
        "municipalities": sum(p["CD_MUN"] not in OPERATIONAL for p, g in rows),
        "operational_areas": [p["NM_MUN"] for p, g in rows if p["CD_MUN"] in OPERATIONAL],
        "source_crs": crs.to_string(),
        "calculation_crs": AREA_CRS,
        "invalid_geometries": 0,
        "union_area_ha": merged.area / 10000,
        "sum_minus_union_m2": overlap,
        "method": "LAEA equivalente centrada no RS. Operacionais preservadas para reconciliar estado, excluídas de rankings municipais.",
    }
    (ROOT / "reports/geourban_w001/boundaries.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    run()
