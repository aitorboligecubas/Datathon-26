"""Owner: INTEGRADOR. La ida y vuelta del formato oficial tiene que cuadrar."""
import numpy as np
import pandas as pd

from battery.adapter import from_official, make_official_obs, recent_load_pv


def test_roundtrip():
    price = np.linspace(0.05, 0.3, 25)
    co2 = np.linspace(0.08, 0.3, 25)
    ts = pd.Timestamp("2025-03-26 13:00")   # miércoles
    raw = make_official_obs(ts, 1234.5, price, co2, 600.0, 150.0)
    assert len(raw["preus_properes_24h"]) == 24 and np.isclose(raw["soc_pct"], 1234.5 / 2000)
    obs = from_official(raw)
    assert (obs.hour, obs.weekday, obs.hour_of_week) == (13, 2, 61)
    assert np.isclose(obs.soc_kwh, 1234.5)
    assert np.allclose(obs.price, price) and np.allclose(obs.co2, co2)
    assert np.isclose(obs.load_prev_kw, 600.0) and np.isclose(obs.pv_prev_kw, 150.0)
    assert obs.timestamp == ts


def test_first_step_without_previous_hour():
    raw = make_official_obs(pd.Timestamp("2025-01-25"), 1000, np.ones(25), np.ones(25),
                            float("nan"), float("nan"))
    obs = from_official(raw)
    assert np.isnan(obs.load_prev_kw) and np.isnan(obs.pv_prev_kw)


def test_recent_formats():
    # Solo contador e inversores (formato posible de noves_dades_5min, VERIFICAR)
    df = pd.DataFrame({"contador": [-500.0] * 12, "inversor_1": [10.0] * 12,
                       "inversor_2": [20.0] * 12, "inversor_3": [30.0] * 12})
    assert recent_load_pv(df) == (500.0, 60.0)
    assert np.isnan(recent_load_pv(None)[0])
    assert np.isnan(recent_load_pv("formato desconocido")[0])
