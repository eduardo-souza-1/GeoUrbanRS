"""Validate and persist the real annual pilot, including derived spatial layers."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio

from src.official_tables import ROOT
from src.urban_trajectory import analyze


def run(path):
    out = ROOT / "reports/geourban_w002"
    out.mkdir(exist_ok=True)
    years = list(range(1985, 2026))
    with rasterio.open(path) as ds:
        if ds.descriptions != tuple(f"classification_{y}" for y in years):
            raise ValueError("Exige 41 bandas identificadas e ordenadas")
        if not ds.crs or "lambert_azimuthal_equal_area" not in ds.crs.to_wkt().lower():
            raise ValueError("Exige LAEA equivalente")
        if ds.nodata != 255 or ds.res != (30, 30):
            raise ValueError("Exige 30 m e nodata 255")
        data = ds.read()
        rows, first, origin, domain = analyze(
            data, ds.read_masks() > 0, years, abs(ds.transform.determinant)
        )
        reference = ROOT / "data/raw/geourban_w001/GeoUrban_pilot_col11_1985_2025.tif"
        with rasterio.open(reference) as old:
            if ds.crs != old.crs or ds.transform != old.transform or ds.shape != old.shape:
                raise ValueError("Grade difere do piloto inicial")
            if not np.array_equal(data[[0, -1]], old.read()):
                raise ValueError("Extremos diferem do piloto inicial")
        profile = ds.profile.copy()
        profile.update(count=1, dtype="uint16", nodata=65535)
        for name, array in [("first_urban_year", first), ("prior_class", origin)]:
            layer = array.astype("uint16")
            layer[~domain] = 65535
            with rasterio.open(out / f"{name}.tif", "w", **profile) as dest:
                dest.write(layer, 1)
                dest.set_band_description(1, name)
        summary = {
            "source": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "scope": "Recorte piloto em Porto Alegre; não município inteiro",
            "excluded_pixels": int(domain.size - domain.sum()),
            "endpoint_pixels_match": True,
            "first_conversion_ha": float((first > 0).sum() * 0.09),
            "annual_entries_including_reentries_ha": sum(
                r.get("converted_to_urban_ha", 0) for r in rows
            ),
            "first_conversion_origins_ha": {
                str(int(c)): float(n * 0.09)
                for c, n in zip(*np.unique(origin[first > 0], return_counts=True))
            },
            "peak_first_conversion": max(rows[1:], key=lambda r: r["first_conversion_ha"]),
            "series": rows,
            "layer_semantics": "0=sem primeira conversão observada após 1985; 65535=excluído. Estoque urbano em 1985 não é nova conversão.",
        }
    (out / "annual_pilot.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in summary.items() if k != "series"}, ensure_ascii=False, indent=2
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    run(parser.parse_args().path)
