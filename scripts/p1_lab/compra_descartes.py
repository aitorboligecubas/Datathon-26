"""Piezas probadas y DESCARTADAS en el encargo "compra". NO se empaqueta: está para reproducir los números.

Cada variante es el agente actual (v2) más una sola pieza; se mide con el banco:

    python scripts/p1_banco.py --suite dev --agent scripts/p1_lab/compra_descartes.py:primera_hora_sin_descarga \
        --ref results/p1_banco/dev_actual.csv --only nov0,normal

    primera_hora_sin_descarga  en la primera hora de cada semana del test no se descarga
    primera_hora_quieto        en la primera hora de cada semana no se hace nada
    apuesta_1_12 / apuesta_1_6 en la primera hora se actúa solo si la ganancia esperada supera a la pérdida
                               esperada, con una probabilidad a priori de que la semana venga sin datos
    tras_cero                  después de una semana sin datos, no se descarga en la primera hora de la siguiente
    sin_puente                 al final de cada semana no se cuenta con el consumo de la siguiente

Resultados y motivos en results/p1_banco/compra_notas.md.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from battery.optimizer import plan  # noqa: E402
from battery.policy import MPCPolicy, greedy_action, hours_to_month_end  # noqa: E402
from battery.safety import clip_action  # noqa: E402
from cand_compra import cheapest_mean  # noqa: E402


def plan_cost(soc_kwh: float, actions, net, weights, terminal: float, p) -> float:
    """Valor del objetivo del LP para un plan dado: compras ponderadas menos el valor de la carga final."""
    a = np.asarray(actions, dtype=float)
    soc_end = soc_kwh + float(np.where(a > 0, a * p.eta_charge, a / p.eta_discharge).sum())
    return float((weights * np.maximum(net + a, 0.0)).sum() - terminal * soc_end)


class BlockForecaster:
    """Previsión que no cuenta con el consumo de la semana siguiente del test (solo si policy.NO_BRIDGE)."""

    def __init__(self, inner, policy):
        self.inner, self.policy = inner, policy

    def update(self, obs) -> None:
        self.inner.update(obs)

    def forecast(self, obs, h: int) -> tuple:
        load, pv = self.inner.forecast(obs, h)
        pol = self.policy
        if pol.NO_BRIDGE and not pol.no_data_block and obs.timestamp is not None:
            k = hours_to_month_end(obs.timestamp)
            if k < h:
                load, pv = np.array(load, dtype=float), np.array(pv, dtype=float)
                load[k:] = 0.0
                pv[k:] = 0.0
        return load, pv


class Discarded(MPCPolicy):
    FIRST_HOUR = "v2"          # "v2" | "no_discharge" | "wait" | "ev"
    P_ZERO = 1.0 / 12.0        # en el train, 1 de los 12 meses no tiene contador
    AFTER_NO_DATA = False
    NO_BRIDGE = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.first_hour = False
        self.forecaster = BlockForecaster(self.forecaster, self)

    def first_hour_bet(self, obs, H: int, load, pv, terminal: float, actions, a0: float) -> float:
        """Si la semana es normal, actuar ya vale `gain`; si viene sin datos, descargar es tirar la energía
        y cargar es comprar antes de tiempo (`loss`). Se actúa si la ganancia esperada supera a la pérdida."""
        if H < 2 or abs(a0) < 1e-6:
            return a0
        w = self.w_co2 * obs.co2[:H] + self.w_cost * obs.price[:H]
        net = np.asarray(load, dtype=float) - np.asarray(pv, dtype=float)
        later = plan(obs.soc_kwh, load[1:], pv[1:], obs.price[1:H], obs.co2[1:H],
                     self.w_co2, self.w_cost, terminal, self.p)
        wait = w[0] * max(float(net[0]), 0.0) + plan_cost(obs.soc_kwh, later, net[1:], w[1:], terminal, self.p)
        gain = wait - plan_cost(obs.soc_kwh, actions, net, w, terminal, self.p)
        valley = cheapest_mean(w)
        if a0 > 0:
            loss = a0 * max(float(w[0]) - valley, 0.0)
        else:
            loss = -a0 * valley / (self.p.eta_charge * self.p.eta_discharge)
        return a0 if (1.0 - self.P_ZERO) * gain >= self.P_ZERO * loss else 0.0

    def plan_action(self, obs) -> float:
        if not (self.first_hour and self.FIRST_HOUR == "ev"):
            return super().plan_action(obs)
        self.forecaster.update(obs)
        H = max(1, min(self.horizon, len(obs.price)))
        load, pv = self.forecaster.forecast(obs, H)
        try:
            terminal = self.terminal_value(obs, H)
            actions = plan(obs.soc_kwh, load, pv, obs.price[:H], obs.co2[:H],
                           self.w_co2, self.w_cost, terminal, self.p)
            a0 = clip_action(actions[0], obs.soc_kwh, self.p)
            return self.first_hour_bet(obs, H, load, pv, terminal, actions, a0)
        except Exception:
            self.n_fallbacks += 1
            return greedy_action(obs, load[0], pv[0], self.p)

    def act_obs(self, obs) -> float:
        was_no_data = bool(self.no_data_block)       # ¿la semana anterior acabó sin datos?
        try:
            new_block = self.track_block(obs)
        except Exception:
            new_block, self.no_data_block = False, False
        if new_block:
            obs = obs._replace(load_prev_kw=float("nan"), pv_prev_kw=float("nan"))
        try:
            self.note_weight(obs)
        except Exception:
            pass
        self.first_hour = bool(new_block and self.t > 0)
        action = self.cap_discharge(self.plan_action(obs), obs)
        if self.first_hour:
            if self.FIRST_HOUR == "wait":
                return 0.0
            if self.FIRST_HOUR == "no_discharge" or (self.AFTER_NO_DATA and was_no_data):
                return max(action, 0.0)
        return action


class _Agent:
    def __init__(self, cls):
        self.policy = cls()

    def act(self, obs):
        return self.policy.act(obs)


def variant(**attrs):
    cls = type("Variant", (Discarded,), attrs)
    return lambda: _Agent(cls)


primera_hora_sin_descarga = variant(FIRST_HOUR="no_discharge")
primera_hora_quieto = variant(FIRST_HOUR="wait")
apuesta_1_12 = variant(FIRST_HOUR="ev")
apuesta_1_6 = variant(FIRST_HOUR="ev", P_ZERO=1.0 / 6.0)
tras_cero = variant(AFTER_NO_DATA=True)
sin_puente = variant(NO_BRIDGE=True)
make_agent = primera_hora_sin_descarga
