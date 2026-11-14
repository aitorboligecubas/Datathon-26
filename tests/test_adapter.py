"""Owner: INTEGRADOR. El formato oficial (environment.py) se traduce bien a Obs."""
import numpy as np
import pandas as pd

from battery.adapter import from_official, make_official_obs


def test_roundtrip():
    price = np.linspace(0.05, 0.3, 24)
    co2 = np.linspace(0.08, 0.3, 24)
    ts = pd.Timestamp("2025-03-26 13:00")   # miércoles
    raw = make_official_obs(ts, 1234.5, price, co2, 600.0, 150.0)
    assert len(raw["preus_properes_24h"]) == 24 and raw["preu_actual"] == price[0]
    assert np.isclose(raw["soc_pct"], 1234.5 / 2000)
    obs = from_official(raw)
    assert (obs.hour, obs.weekday, obs.hour_of_week) == (13, 2, 61)
    assert np.isclose(obs.soc_kwh, 1234.5)
    assert np.allclose(obs.price, price) and np.allclose(obs.co2, co2)
    assert (obs.load_prev_kw, obs.pv_prev_kw) == (600.0, 150.0)
    assert obs.timestamp == ts


def test_check_submission_style_obs():
    """check_submission.py pasa el timestamp como texto y previsiones planas."""
    raw = {
        "timestamp": "2026-01-15 12:00:00", "hour": 12, "day_of_week": 3,
        "soc_kwh": 1000.0, "soc_pct": 0.5, "soc_percent": 50.0,
        "preu_actual": 0.17, "co2_actual": 0.23,
        "preus_properes_24h": [0.14] * 24, "co2_properes_24h": [0.18] * 24,
        "noves_dades_5min": {"ultim_consum_kw": 470.0, "ultima_solar_kw": 120.0},
    }
    obs = from_official(raw)
    assert obs.timestamp == pd.Timestamp("2026-01-15 12:00")
    assert obs.price[0] == 0.17 and obs.co2[0] == 0.23 and len(obs.price) == 24


def test_end_of_data_and_missing_fields():
    raw = make_official_obs(pd.Timestamp("2025-01-31 23:00"), 1000, np.ones(3), np.ones(3), 1.0, 2.0)
    assert len(from_official(raw).price) == 3
    raw["noves_dades_5min"] = None
    obs = from_official(raw)
    assert np.isnan(obs.load_prev_kw) and np.isnan(obs.pv_prev_kw)
