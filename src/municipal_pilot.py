"""Assign pilot pixel centers to official IBGE municipalities and reconcile."""

import hashlib
import json

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.features import rasterize
from shapely import transform
from shapely.geometry import box

from src.boundaries import OPERATIONAL, read_boundaries
from src.official_tables import ROOT
from src.urban_trajectory import analyze


def run(
    path=None,
    report_name="municipal_pilot",
    scope="Somente interseção dos municípios com a grade piloto; não ranking municipal completo",
):
    out = ROOT / "reports/geourban_w002"
    out.mkdir(exist_ok=True)
    path = path or ROOT / "data/raw/geourban_w001/GeoUrban_annual_LAEA_col11.tif"
    boundaries, crs = read_boundaries()
    with rasterio.open(path) as ds:
        project = Transformer.from_crs(crs, ds.crs, always_xy=True)
        shapes = [
            (transform(g, project.transform, interleaved=False), i + 1)
            for i, (_, g) in enumerate(boundaries)
        ]
        zones = rasterize(
            shapes, out_shape=ds.shape, transform=ds.transform, fill=0, dtype="uint16"
        )
        if ds.count != 41 or ds.descriptions != tuple(
            f"classification_{y}" for y in range(1985, 2026)
        ):
            raise ValueError("Exige 41 bandas anuais identificadas")
        if (
            ds.nodata != 255
            or not ds.crs.is_projected
            or "lambert_azimuthal_equal_area" not in ds.crs.to_wkt().lower()
        ):
            raise ValueError("Exige nodata 255 e LAEA")
        data = ds.read()
        valid = ds.read_masks() > 0
        cell = abs(ds.transform.determinant)
        rows, first, origin, domain = analyze(data, valid, list(range(1985, 2026)), cell)
        records = []
        for zone in np.unique(zones):
            if zone == 0:
                continue
            p, _ = boundaries[int(zone) - 1]
            mask = domain & (zones == zone)
            if not mask.any():
                continue
            start = float(((data[0] == 24) & mask).sum() * cell / 10000)
            end = float(((data[-1] == 24) & mask).sum() * cell / 10000)
            geometry = shapes[int(zone) - 1][0]
            outside = geometry.difference(box(*ds.bounds)).area
            territory = zones == zone
            excluded = int((territory & ~domain).sum())
            series = []
            for i, year in enumerate(range(1985, 2026)):
                series.append(
                    {
                        "year": year,
                        "urban_area_ha": float(((data[i] == 24) & mask).sum() * cell / 10000),
                        "first_conversion_ha": float(((first == year) & mask).sum() * cell / 10000),
                    }
                )
            records.append(
                {
                    "municipality_code": p["CD_MUN"],
                    "name": p["NM_MUN"],
                    "complete_territory": outside <= 1,
                    "boundary_outside_raster_m2": outside,
                    "excluded_territory_pixels": excluded,
                    "series": series,
                    "growth_percent": (end / start - 1) * 100 if start else None,
                    "operational_area": p["CD_MUN"] in OPERATIONAL,
                    "sample_covered_ha": float(mask.sum() * cell / 10000),
                    "urban_1985_ha": start,
                    "urban_2025_ha": end,
                    "first_conversion_ha": float(((first > 0) & mask).sum() * cell / 10000),
                    "first_origins_ha": {
                        str(int(c)): float(n * cell / 10000)
                        for c, n in zip(*np.unique(origin[(first > 0) & mask], return_counts=True))
                    },
                }
            )
        unassigned = domain & (zones == 0)
        errors = {}
        for key, total in [
            ("urban_1985_ha", rows[0]["urban_area_ha"]),
            ("urban_2025_ha", rows[-1]["urban_area_ha"]),
            ("first_conversion_ha", float((first > 0).sum() * cell / 10000)),
        ]:
            extra = float(
                (
                    (
                        (data[0] == 24)
                        if key == "urban_1985_ha"
                        else (data[-1] == 24)
                        if key == "urban_2025_ha"
                        else (first > 0)
                    )
                    & unassigned
                ).sum()
                * cell
                / 10000
            )
            errors[key] = sum(r[key] for r in records) + extra - total
        if any(abs(v) > 1e-6 for v in errors.values()):
            raise ValueError("Falha de reconciliação")
        report = {
            "scope": scope,
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "assignment": "Centro do pixel, all_touched=False; sem frações de borda",
            "unassigned_valid_pixels": int(unassigned.sum()),
            "reconciliation_residuals_ha": errors,
            "municipalities": records,
        }
    (out / f"{report_name}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path)
    parser.add_argument("--report-name", default="municipal_pilot")
    args = parser.parse_args()
    run(args.path, args.report_name)
