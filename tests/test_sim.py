"""Owner: P3. El simulador y el score se comportan como el oficial."""
import numpy as np

from battery.baselines import NothingAgent
from battery.data import load, validation_split
from battery.params import DEFAULT_PARAMS as P
from battery.sim import baseline_totals, score, simulate


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
    assert log.infraction[no_room].all() and (log.action_kw[no_room] < 100).all()
    assert not log.infraction[~no_room].any()
