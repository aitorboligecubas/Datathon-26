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
