"""Owner: P3. El simulador y el score se comportan como el oficial."""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from battery.baselines import NothingAgent
from battery.data import ensure_official, load, validation_split
from battery.params import DEFAULT_PARAMS as P
from battery.sim import baseline_totals, score, simulate

REPO = Path(__file__).resolve().parents[1]
OFFICIAL_ENV = REPO / "oficial" / "starter_kit" / "environment.py"
ensure_official()


def _week():
    return validation_split(load()).iloc[:168].reset_index(drop=True)


def test_nothing_agent_scores_zero():
    df = _week()
    res = simulate(NothingAgent(), df)
    sc = score(res.totals, baseline_totals(df))
    assert abs(sc["score_raw"]) < 1e-9 and sc["infractions"] == 0
    assert res.totals["final_soc_kwh"] == P.soc_init_kwh


def test_energy_accounting():
    class Constant:
        def act(self, obs):
            return 100.0

    df = _week()
    log = simulate(Constant(), df).log
    # La carga sube 100·eta por hora hasta llenarse; la red absorbe la acción aplicada.
    assert np.allclose(log.grid_kw, log.load_kw - log.pv_kw + log.action_kw)
    assert np.isclose(log.soc_kwh[0], P.soc_init_kwh + 100 * P.eta_charge)
    assert log.soc_kwh.max() <= P.capacity_kwh + 1e-9
    # Con la batería llena, pedir 100 kW es infracción: se cuenta y se recorta.
    soc_prev = log.soc_kwh.shift(fill_value=P.soc_init_kwh)
    no_room = (P.capacity_kwh - soc_prev) / P.eta_charge < 100
    assert (log.infractions[no_room] == 1).all() and (log.action_kw[no_room] < 100).all()
    assert (log.infractions[~no_room] == 0).all()


def test_power_limit_counts_like_official():
    from battery.sim import apply_action
    assert apply_action(1000.0, 600.0)[2] == 1          # recorte de potencia
    assert apply_action(1999.0, 600.0)[2] == 2          # potencia + capacidad
    assert apply_action(1000.0, -500.0)[2] == 0


@pytest.mark.skipif(not OFFICIAL_ENV.exists(), reason="sin oficial/ (ZIP oficial)")
def test_matches_official_environment():
    out = subprocess.run([sys.executable, "scripts/calibrate_sim.py", "--hours", "336"],
                         cwd=REPO, capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stdout + out.stderr
