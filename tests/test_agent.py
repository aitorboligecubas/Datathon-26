"""Owner: P1. El agente completo: sin infracciones, mejor que no hacer nada y rápido."""
from battery.data import load, validation_split
from battery.params import N_STEPS, TIME_BUDGET_S
from battery.policy import BatteryAgent
from battery.sim import baseline_totals, score, simulate


def test_agent_one_week():
    df = validation_split(load()).iloc[:168].reset_index(drop=True)
    agent = BatteryAgent()
    res = simulate(agent, df)
    sc = score(res.totals, baseline_totals(df))
    assert sc["infractions"] == 0
    assert sc["score"] > 0
    assert agent.policy.n_fallbacks == 0
    projected = res.totals["runtime_s"] * N_STEPS / len(df)
    assert projected < TIME_BUDGET_S, f"proyección a 2.016 h: {projected:.1f} s"


def test_spends_battery_when_data_ends():
    """Con la previsión recortada (fin de los datos), la carga final no vale nada."""
    import numpy as np

    from battery.obs import Obs

    agent = BatteryAgent()
    full = Obs(12, 2, 1500.0, np.full(24, 0.1), np.full(24, 0.1), 900.0, 0.0)
    end = Obs(12, 2, 1500.0, np.full(3, 0.1), np.full(3, 0.1), 900.0, 0.0)
    assert not agent.policy.episode_ends_soon(full)
    assert agent.policy.episode_ends_soon(end)
    assert agent.policy.terminal_value(end, 3) == 0.0
    assert agent.policy.act_obs(end) < 0          # descarga lo que queda
