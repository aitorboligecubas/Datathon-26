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


def test_forecasts_as_list_tuple_array_or_series():
    """El servidor podría pasar las previsiones como array o Series: el agente tiene que actuar igual."""
    from battery.policy import BatteryAgent

    price = np.r_[np.full(4, 0.05), np.full(20, 0.30)]      # barato ahora: hay que cargar
    base = make_official_obs(pd.Timestamp("2025-03-26 03:00"), 200.0, price, price, 900.0, 0.0)
    actions = []
    for conv in (list, tuple, np.array, pd.Series):
        raw = dict(base, preus_properes_24h=conv(price), co2_properes_24h=conv(price))
        assert len(from_official(raw).price) == 24
        actions.append(BatteryAgent().act(raw))
    assert actions[0] > 0 and max(actions) - min(actions) < 1e-9
    for empty in ([], None, np.array([])):
        raw = dict(base, preus_properes_24h=empty, co2_properes_24h=empty)
        assert list(from_official(raw).price) == [price[0]]
    for odd in (None, pd.DataFrame({"x": [1]}), "texto"):   # lecturas en un formato inesperado: sin romper
        obs = from_official(dict(base, noves_dades_5min=odd))
        assert np.isnan(obs.load_prev_kw)
