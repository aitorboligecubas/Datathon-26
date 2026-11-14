"""Cota superior para el encargo de transiciones: un agente que, en cuanto ve el primer 0 del contador,
SABE cuántas horas va a durar el tramo a 0. NO se empaqueta (hace trampa a propósito).

Sirve para saber cuánto se podría ganar, como mucho, con mejores creencias sobre la duración:
    informado (sin salida)   conoce la duración, pero en la hora en que vuelve el consumo todavía no puede
                             descargar (la lectura que tiene sigue siendo 0), como cualquier agente real
    informado (con salida)   además descarga ya en la primera hora con consumo
Lo que NO sabe: que la avería va a empezar (la primera hora a 0 le pilla igual que a nosotros), ni los
precios más allá de 24 h.
"""
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "p1_lab"))

from cand_trans import TransPolicy  # noqa: E402
from battery.optimizer import plan  # noqa: E402
from battery.policy import greedy_action  # noqa: E402
from battery.safety import clip_action  # noqa: E402


class Informed(TransPolicy):
    PATIENCE = "full"

    def __init__(self, df, know_exit: bool):
        super().__init__()
        self.true_zero = df["load_kw"].to_numpy() == 0.0
        self.know_exit = know_exit
        self.exit_now = False

    def remaining(self) -> int:
        t, n, r = self.t, len(self.true_zero), 0
        while t + r < n and self.true_zero[t + r]:
            r += 1
        return r

    def cap_discharge(self, action_kw, obs):
        if self.exit_now:
            return action_kw
        return super().cap_discharge(action_kw, obs)

    def plan_action(self, obs) -> float:
        self.forecaster.update(obs)
        H = max(1, min(self.horizon, len(obs.price)))
        load, pv = self.forecaster.forecast(obs, H)
        self.exit_now = False
        try:
            terminal = self.terminal_value(obs, H)
            detected = obs.load_prev_kw == 0.0
            if detected:
                R = self.remaining()
                n = len(self.true_zero)
                load, pv = np.array(load, dtype=float), np.array(pv, dtype=float)
                if R == 0 and self.know_exit:
                    self.exit_now = True
                    lp = self.forecaster._load_profile(obs.hour_of_week)
                    load[0] = lp if math.isfinite(lp) else 0.0
                else:
                    R = max(R, 1)          # sin conocer la salida: esta hora se trata como a 0
                    load[:R] = 0.0
                    pv[:R] = 0.0
                    if self.t + R >= n:
                        terminal = 0.0
                    elif R >= H and not self.episode_ends_soon(obs) and len(self.valleys) >= 7:
                        terminal = self.reserve_weight(int(math.ceil((R - H) / 24.0)) + 1) / self.p.eta_charge
            actions = plan(obs.soc_kwh, load, pv, obs.price[:H], obs.co2[:H], self.w_co2, self.w_cost, terminal, self.p)
            return clip_action(actions[0], obs.soc_kwh, self.p)
        except Exception:
            self.n_fallbacks += 1
            return greedy_action(obs, load[0], pv[0], self.p)


class InformedAgent:
    def __init__(self, df, know_exit: bool):
        self.policy = Informed(df, know_exit)

    def act(self, obs):
        return self.policy.act(obs)
