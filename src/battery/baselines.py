"""Estrategias de referencia para comparar y para la presentación. NO se empaquetan.

Owner: P1 (optimizador).

Todas exponen la interfaz del agente oficial: `act(raw_obs) -> float`.
- NothingAgent: nunca usa la batería. Es la referencia del score (ΔCO2 = ΔCoste = 0).
- GreedyAgent: reglas simples con la demanda y la solar de la hora anterior.
- OracleAgent: LP con información perfecta de todo el episodio. Hace trampa a
  propósito: es la cota superior (techo teórico) que ningún agente real alcanza.
"""
from .adapter import from_official
from .optimizer import plan
from .params import DEFAULT_PARAMS, BatteryParams
from .policy import greedy_action
from .safety import clip_action


class NothingAgent:
    def act(self, raw_obs) -> float:
        return 0.0


class GreedyAgent:
    def __init__(self, p: BatteryParams = DEFAULT_PARAMS):
        self.p = p

    def act(self, raw_obs) -> float:
        obs = from_official(raw_obs)
        return greedy_action(obs, obs.load_prev_kw, obs.pv_prev_kw, self.p)


class OracleAgent:
    """`df` con las columnas estándar de battery.data (todo el episodio)."""

    def __init__(self, df, w_co2: float, w_cost: float, p: BatteryParams = DEFAULT_PARAMS):
        self.p = p
        self.actions = plan(p.soc_init_kwh, df["load_kw"].to_numpy(), df["pv_kw"].to_numpy(),
                            df["price_eur_kwh"].to_numpy(), df["co2_kg_kwh"].to_numpy(),
                            w_co2, w_cost, terminal_value=0.0, p=p)
        self.t = 0

    def act(self, raw_obs) -> float:
        obs = from_official(raw_obs)
        a = self.actions[self.t] if self.t < len(self.actions) else 0.0
        self.t += 1
        return clip_action(a, obs.soc_kwh, self.p)
