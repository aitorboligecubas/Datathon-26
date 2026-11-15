"""Rama mejora-score-hard: semilla de consumo y solar al empezar cada semana del test, margen del plan y desempate."""
import math

import numpy as np
import pandas as pd

from test_agent import _hard_obs


def _seed_last(pol, ts):
    return pol.netload_seed[pd.Timestamp(ts) - pd.Timedelta(hours=1)]


def test_models_carry_a_seed_right_before_each_test_week():
    """La semilla de models/hard_solar.json acaba justo antes de las semanas del test que tienen train."""
    from battery.hard import HardPolicy

    pol = HardPolicy()
    for start in ("2025-09-24", "2025-10-25", "2025-12-25", "2026-01-25", "2026-02-22", "2026-03-25",
                  "2026-04-24", "2026-05-25", "2026-06-24", "2026-07-25"):
        assert pd.Timestamp(start) - pd.Timedelta(hours=1) in pol.netload_seed, start


def test_week_start_replays_the_seed_and_checks_it():
    """La primera hora de la semana el previsor arranca con las 48 h de la semilla; la segunda se comprueba con la
    lectura de las 00 h (contador congelado = la de las 23 h anteriores). Si casa, se sigue; si no, se olvida."""
    from battery.hard import HardPolicy

    pol = HardPolicy()
    a0 = pol.act(_hard_obs("2025-09-24 00:00", 3000.0, load_prev=1234.0))     # lectura de hace un mes: se ignora
    assert math.isfinite(a0)
    assert len(pol.netload.r_hist) >= 24                                       # memoria de la semilla
    last = _seed_last(pol, "2025-09-24 00:00")
    pol.act(_hard_obs("2025-09-24 01:00", 3000.0, load_prev=last[0]))
    assert pol.seed_mismatches == 0 and len(pol.netload.r_hist) >= 25

    pol = HardPolicy()
    pol.act(_hard_obs("2025-09-24 00:00", 3000.0))
    pol.act(_hard_obs("2025-09-24 01:00", 3000.0, load_prev=last[0] * 1.3))   # no casa: el test no sigue al train
    assert pol.seed_mismatches == 1 and len(pol.netload.r_hist) <= 1


def test_week_start_without_seed_behaves_as_before():
    """Sin semilla para esa fecha (noviembre no tiene train) o con la semilla apagada, nada cambia."""
    from battery.hard import HardPolicy

    for ts in ("2025-11-24 00:00", "2025-09-24 00:00"):
        on, off = HardPolicy(), HardPolicy()
        off.use_seed = False
        if ts.startswith("2025-11"):
            assert on.act(_hard_obs(ts, 3000.0)) == off.act(_hard_obs(ts, 3000.0))
        else:
            off.act(_hard_obs(ts, 3000.0))
            assert len(off.netload.r_hist) <= 1


def test_broken_seed_never_raises():
    from battery.hard import HardPolicy, netload_seed_dict

    for bad in (None, {}, {"seed": "roto"}, {"seed": [{"start": "no es fecha", "load": [1], "pv": [0]}]},
                {"seed": [{"start": "2025-09-23 23:00", "load": [float("nan")], "pv": [0.0]}]}):
        assert isinstance(netload_seed_dict(bad), dict)
    pol = HardPolicy()
    pol.netload_seed = {pd.Timestamp("2025-09-23 23:00"): ("x", "y")}
    assert math.isfinite(pol.act(_hard_obs("2025-09-24 00:00", 3000.0)))


def test_optimizer_extras_default_to_the_old_plan():
    """Desempate y tope de descarga por hora: con los valores por defecto el plan es el de siempre."""
    from battery.hard import HARD_PARAMS
    from battery.optimizer import plan

    rng = np.random.default_rng(0)
    load, pv = 900 + 200 * rng.random(24), 1500 * rng.random(24)
    price, co2 = 0.1 + 0.1 * rng.random(24), 0.05 + 0.1 * rng.random(24)
    base = plan(3000.0, load, pv, price, co2, 8.0, 2.0, 0.0, HARD_PARAMS)
    same = plan(3000.0, load, pv, price, co2, 8.0, 2.0, 0.0, HARD_PARAMS, cycle_cost=0.0, export_cost=0.0,
                discharge_cap=None)
    assert np.allclose(base, same)
    capped = plan(3000.0, load, pv, price, co2, 8.0, 2.0, 0.0, HARD_PARAMS, discharge_cap=np.full(24, 100.0))
    assert capped.min() >= -100.0 - 1e-6


def test_cap_discharge_defers_to_the_forecast_after_a_solar_surplus():
    """Revisión de la decisión: tras una hora con excedente solar (lectura neta < 0), el tope del modo estándar
    bloqueaba toda descarga. Con la previsión de esta hora manda adjust_action; sin ella, el tope de siempre."""
    from battery.hard import HardPolicy
    from battery.obs import Obs

    pol = HardPolicy()
    obs = Obs(hour=17, weekday=0, soc_kwh=5000.0, price=np.array([0.1]), co2=np.array([0.1]),
              load_prev_kw=900.0, pv_prev_kw=1000.0, timestamp=pd.Timestamp("2026-08-31 17:00"))
    assert getattr(pol.netload, "uncap", False)
    pol.netload.fresh = False
    assert pol.cap_discharge(-600.0, obs) == 0.0          # sin previsión: lo comprado la hora anterior (nada)
    pol.netload.fresh = True
    assert pol.cap_discharge(-600.0, obs) == -600.0       # con previsión: el margen lo pone adjust_action
    assert pol.cap_discharge(800.0, obs) == 800.0         # la carga no se toca
    a = pol.act(_hard_obs("2026-08-31 16:00", 5000.0, load_prev=900.0, pv_prev=1000.0))
    a = pol.act(_hard_obs("2026-08-31 17:00", 5000.0, load_prev=900.0, pv_prev=1000.0))
    assert math.isfinite(a) and -1500.0 <= a <= 1500.0
