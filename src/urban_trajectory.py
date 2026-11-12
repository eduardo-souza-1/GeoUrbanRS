"""Annual transitions on a fixed, fully observed domain; no gap interpolation."""

import numpy as np


def analyze(classes, valid, years, cell_area_m2):
    classes = np.asarray(classes)
    if classes.ndim != 3 or classes.shape != valid.shape:
        raise ValueError("Exige bandas e máscaras alinhadas")
    if len(years) != len(classes) or list(years) != list(range(years[0], years[-1] + 1)):
        raise ValueError("Exige anos consecutivos e ordenados")
    if not np.isfinite(cell_area_m2) or cell_area_m2 <= 0:
        raise ValueError("Área de pixel inválida")
    domain = (valid & ~np.isin(classes, [0, 27, 255])).all(axis=0)
    unit = cell_area_m2 / 10000
    urban = (classes == 24) & domain
    first_year = np.zeros(domain.shape, dtype=np.uint16)
    origin = np.zeros(domain.shape, dtype=np.uint8)
    seen = urban[0].copy()  # 1985 urbano é estoque inicial, não nova conversão
    rows = []
    for i, year in enumerate(years):
        row = {"year": int(year), "urban_area_ha": float(urban[i].sum() * unit)}
        if i:
            gain = domain & ~urban[i - 1] & urban[i]
            loss = domain & urban[i - 1] & ~urban[i]
            first = gain & ~seen
            first_year[first] = year
            origin[first] = classes[i - 1][first]
            seen |= urban[i]
            origins = {
                str(int(c)): float(n * unit)
                for c, n in zip(*np.unique(classes[i - 1][gain], return_counts=True))
            }
            row.update(
                converted_to_urban_ha=float(gain.sum() * unit),
                urban_to_other_ha=float(loss.sum() * unit),
                first_conversion_ha=float(first.sum() * unit),
                origin_classes_ha=origins,
            )
            residual = (
                row["urban_area_ha"] - rows[-1]["urban_area_ha"] - (gain.sum() - loss.sum()) * unit
            )
            if abs(residual) > 1e-6:
                raise ValueError("Reconciliação anual falhou")
        rows.append(row)
    return rows, first_year, origin, domain
