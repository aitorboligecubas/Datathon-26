"""Owner: P2. Contrato del Forecaster con P1."""
import time

import numpy as np

from battery.adapter import from_official, make_official_obs
from battery.data import load, validation_split
from battery.forecaster import Forecaster


def test_contract_shape_and_speed():
    df = validation_split(load()).iloc[:200].reset_index(drop=True)
    f = Forecaster()
    worst = 0.0
    for t in range(1, len(df)):
        raw = make_official_obs(df.timestamp[t], 1000.0, np.full(25, 0.1), np.full(25, 0.2),
                                df.load_kw[t - 1], df.pv_kw[t - 1])
        obs = from_official(raw)
        t0 = time.perf_counter()
        f.update(obs)
        load_kw, pv_kw = f.forecast(obs, 25)
        worst = max(worst, time.perf_counter() - t0)
        assert load_kw.shape == (25,) and pv_kw.shape == (25,)
        assert np.isfinite(load_kw).all() and np.isfinite(pv_kw).all()
        assert (load_kw >= 0).all() and (pv_kw >= 0).all()
    assert worst < 0.05, f"forecast demasiado lento: {worst * 1000:.1f} ms"
