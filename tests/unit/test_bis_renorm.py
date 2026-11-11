import numpy as np

from mls_bench_impact.config.settings import settings


def compute_bis(ssi, ati, pif):
    comps = {"ssi": ssi, "ati": ati, "pif": pif}
    weights = {
        "ssi": settings.bis_weight_ssi,
        "ati": settings.bis_weight_ati,
        "pif": settings.bis_weight_pif,
    }
    available = {k: v for k, v in comps.items() if v is not None and not (isinstance(v, float) and np.isnan(v))}
    if len(available) == 3:
        return sum(weights[k] * available[k] for k in available)
    if len(available) == 2:
        wsum = sum(weights[k] for k in available)
        return sum(weights[k] / wsum * available[k] for k in available)
    return np.nan


def test_bis_full():
    assert abs(compute_bis(100, 100, 100) - 100) < 1e-9


def test_bis_renorm_not_fifty():
    val = compute_bis(80, None, 20)
    assert val != 50
    assert abs(val - (0.5 / 0.7 * 80 + 0.2 / 0.7 * 20)) < 1e-9


def test_bis_single_component_missing_score():
    assert np.isnan(compute_bis(80, None, None))