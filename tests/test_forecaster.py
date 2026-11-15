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
        raw = make_official_obs(df.timestamp[t], 1000.0, np.full(24, 0.1), np.full(24, 0.2),
                                df.load_kw[t - 1], df.pv_kw[t - 1])
        obs = from_official(raw)
        t0 = time.perf_counter()
        f.update(obs)
        load_kw, pv_kw = f.forecast(obs, 24)
        worst = max(worst, time.perf_counter() - t0)
        assert load_kw.shape == (24,) and pv_kw.shape == (24,)
        assert np.isfinite(load_kw).all() and np.isfinite(pv_kw).all()
        assert (load_kw >= 0).all() and (pv_kw >= 0).all()
    assert worst < 0.05, f"forecast demasiado lento: {worst * 1000:.1f} ms"


def test_meter_failure_means_no_load_now():
    """Si el contador marcó 0 kW la hora anterior (fallo de comunicación), no se prevé consumo
    para la hora actual (así el LP no descarga) y el 0 no contamina el perfil."""
    import numpy as np

    from battery.forecaster import Forecaster
    from battery.obs import Obs

    f = Forecaster({"load_how": [1000.0] * 168, "pv_hod": [10.0] * 24})
    ok = Obs(10, 2, 1000.0, np.full(24, 0.1), np.full(24, 0.1), 1100.0, 20.0)
    down = Obs(11, 2, 1000.0, np.full(24, 0.1), np.full(24, 0.1), 0.0, 0.0)
    f.update(ok)
    assert f.forecast(ok, 24)[0][0] > 900
    f.update(down)
    load, pv = f.forecast(down, 24)
    assert load[0] == 0.0 and pv[0] == 0.0 and load[1] > 900
    assert min(f.load_how) > 900                      # el perfil no ha aprendido el 0
    f.update(Obs(12, 2, 1000.0, np.full(24, 0.1), np.full(24, 0.1), 1050.0, 20.0))
    assert f.forecast(ok, 24)[0][0] > 900             # al volver la lectura, previsión normal


def test_hard_irradiance_alignment_detector():
    """v15 (modo difícil): el previsor de solar averigua solo si la irradiancia de la observación es de la hora
    anterior (lo documentado: no cambia nada) o de la hora actual (entonces la usa para la solar de esta hora)."""
    import json
    import math
    from pathlib import Path

    from battery.forecaster import Forecaster
    from battery.hard_solar import SolarCand

    tables = json.loads((Path(__file__).resolve().parents[1] / "models" / "hard_solar.json").read_text())["cand"]
    irr = [max(0.0, 900.0 * math.sin(math.pi * (h % 24 - 6) / 13.0)) * (0.6 + 0.4 * ((h // 24) % 3) / 2.0)
           if 6 <= h % 24 <= 19 else 0.0 for h in range(24 * 6)]
    pv = [1.7 * v for v in irr]                                   # solar (x12) proporcional a la irradiancia

    def run(shift: int) -> SolarCand:
        nl = SolarCand(tables, Forecaster(None))
        for t in range(1, len(irr)):
            nl.weather = {"irradiancia_wm2": irr[t - 1 + shift]}  # shift 0: de la hora anterior; 1: de la actual
            nl.irr_learn(True, pv[t - 1])                         # la solar que llega es siempre la de la hora anterior
        return nl

    assert not run(0).irr_now                                     # lo documentado: el agente decide como la v14
    now = run(1)
    assert now.irr_now and abs(now.irr_fit[1] / now.irr_fit[0] - 1.7) < 1e-6
    junk = SolarCand(tables, Forecaster(None))
    for v in (None, "x", float("nan"), -5.0, [1], 1e12):
        junk.weather = {"irradiancia_wm2": v}
        junk.irr_learn(True, 500.0)
    assert not junk.irr_now
