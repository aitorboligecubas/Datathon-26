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
