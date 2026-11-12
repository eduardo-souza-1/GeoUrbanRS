"""Validate a real two-band pilot exported from GEE. No automatic fake/sample substitution."""

import argparse
import hashlib
import json

import numpy as np
import rasterio

from src.official_tables import ROOT


def summarize(a, b, valid, cell_area_m2):
    if a.shape != b.shape or a.shape != valid.shape:
        raise ValueError("Grades incompatíveis")
    if not np.isfinite(cell_area_m2) or cell_area_m2 <= 0:
        raise ValueError("Área inválida")
    usable = valid & ~np.isin(a, [0, 27, 255]) & ~np.isin(b, [0, 27, 255])
    gain = usable & (a != 24) & (b == 24)
    loss = usable & (a == 24) & (b != 24)
    unit = cell_area_m2 / 10000
    initial = np.count_nonzero(usable & (a == 24)) * unit
    final = np.count_nonzero(usable & (b == 24)) * unit
    origins = {str(int(c)): int(n) * unit for c, n in zip(*np.unique(a[gain], return_counts=True))}
    return {
        "urban_start_common_domain_ha": initial,
        "urban_end_common_domain_ha": final,
        "converted_to_urban_ha": np.count_nonzero(gain) * unit,
        "urban_to_other_ha": np.count_nonzero(loss) * unit,
        "origin_classes_ha": origins,
        "excluded_pixels": int(valid.size - np.count_nonzero(usable)),
        "reconciliation_residual_ha": final
        - initial
        - (np.count_nonzero(gain) - np.count_nonzero(loss)) * unit,
    }


def run(path):
    with rasterio.open(path) as ds:
        if ds.crs is None or not ds.crs.is_projected:
            raise ValueError("Exige CRS projetado conhecido")
        if "lambert_azimuthal_equal_area" not in ds.crs.to_wkt().lower():
            raise ValueError("Exige projeção equivalente LAEA do exportador")
        if ds.count != 2 or ds.descriptions != ("classification_1985", "classification_2025"):
            raise ValueError("Exige bandas explicitamente identificadas 1985 e 2025")
        if ds.nodata != 255:
            raise ValueError("Exige nodata=255 explícito")
        cell = abs(ds.transform.a * ds.transform.e - ds.transform.b * ds.transform.d)
        a, b = ds.read()
        valid = (ds.read_masks() > 0).all(axis=0)
        result = summarize(a, b, valid, cell)
        result.update(
            {
                "source_file": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "crs": ds.crs.to_wkt(),
                "resolution": ds.res,
                "nodata": ds.nodata,
                "shape": [ds.height, ds.width],
                "scope": "Recorte piloto, não todo o RS",
                "input_verified": True,
            }
        )
    (ROOT / "reports/geourban_w001/raster_pilot.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=__import__("pathlib").Path)
    args = parser.parse_args()
    run(args.path)
