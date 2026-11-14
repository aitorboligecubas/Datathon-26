"""Candidato "info": usar lo que el train dice del contador JUSTO ANTES de cada semana del test.

Parte de MPCPolicy (v2). El train son los días 1 a 23/24 de cada mes y el test, los 7 últimos: cada semana
del test empieza en la hora siguiente a la última del train de ese mes. Y en el train el contador no tiene
ni una lectura del 1 al 23 de noviembre de 2025 (contador.csv: una sola fila, vacía). Un contador que lleva
23 días mudo lo más probable es que siga mudo una hora después.

Piezas (cada una con su interruptor):

S. SILENT_START: una semana que viene detrás de un tramo del train sin contador empieza ya en modo "sin
   datos" (no espera a ver el primer 0). Si la primera lectura trae consumo, sale del modo como siempre.
   Ahorra la compra a ciegas de la primera hora (en noviembre, de madrugada y cara).
V. SELL_BEFORE: en las últimas horas de la semana anterior, no se cuenta con poder descargar al otro lado:
   la energía que quede solo valdrá lo que cueste reponerla en el mejor valle de la semana muda (el precio
   de reserva). Así la batería llega vacía, como hace el óptimo.
G. RESET_ERR (del candidato "trans"): al cambiar de semana, el previsor olvida el error de la anterior.

La lista SILENT sale del train (tests/ lo comprueba contra contador.csv), no del test.
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from battery.policy import BLOCK_GAP_H, FINAL_MONTH, LONG_OUTAGE_H, MPCPolicy, hours_to_month_end  # noqa: E402

NAN = float("nan")
SILENT = {(2025, 11)}     # meses cuyo train no tiene contador en los días previos a la semana del test


def next_block(ts) -> tuple:
    """(año, mes) de la semana del test que viene después de la de `ts`."""
    return (ts.year + 1, 1) if ts.month == 12 else (ts.year, ts.month + 1)


class InfoPolicy(MPCPolicy):
    SILENT_START = True     # S
    SELL_BEFORE = True      # V
    RESET_ERR = True        # G
    SILENT_SET = SILENT

    def track_block(self, obs) -> bool:
        new_block = super().track_block(obs)
        ts = obs.timestamp
        if new_block and self.SILENT_START and ts is not None and (ts.year, ts.month) in self.SILENT_SET:
            self.no_data_block = True
        return new_block

    def act_obs(self, obs) -> float:
        try:
            new_block = self.track_block(obs)
        except Exception:
            new_block, self.no_data_block = False, False
        if new_block:
            obs = obs._replace(load_prev_kw=NAN, pv_prev_kw=NAN)
            if self.RESET_ERR:
                try:
                    self.forecaster.err_load, self.forecaster.err_pv = 0.0, 0.0
                except Exception:
                    pass
        try:
            self.note_weight(obs)
        except Exception:
            pass
        return self.cap_discharge(self.plan_action(obs), obs)

    def before_silent_view(self, obs, H: int, load, pv, terminal: float) -> tuple:
        """Últimas horas antes de una semana que se espera muda: al otro lado no hay consumo que cubrir."""
        ts = obs.timestamp
        if ts is None or self.episode_ends_soon(obs):
            return load, pv, terminal
        k0 = hours_to_month_end(ts)
        if k0 >= H or next_block(ts) not in self.SILENT_SET:
            return load, pv, terminal
        load, pv = np.array(load, dtype=float), np.array(pv, dtype=float)
        load[k0:] = 0.0
        pv[k0:] = 0.0
        if len(self.valleys) >= 7:
            terminal = self.reserve_weight(7) / self.p.eta_charge
        return load, pv, terminal

    def no_data_view(self, obs, H: int, load, pv, terminal: float) -> tuple:
        return super().no_data_view(obs, H, load, pv, terminal)

    def plan_action(self, obs) -> float:
        if self.SELL_BEFORE and not self.no_data_block:
            return self._plan_with_view(obs)
        return super().plan_action(obs)

    def _plan_with_view(self, obs) -> float:
        """Como MPCPolicy.plan_action en semana normal, con la vista de "la semana siguiente viene muda"."""
        from battery.optimizer import plan
        from battery.policy import greedy_action
        from battery.safety import clip_action
        self.forecaster.update(obs)
        H = max(1, min(self.horizon, len(obs.price)))
        load, pv = self.forecaster.forecast(obs, H)
        if self.elapsed_s > self.time_budget_s:
            self.n_fallbacks += 1
            return greedy_action(obs, load[0], pv[0], self.p)
        try:
            terminal = self.terminal_value(obs, H)
            try:
                load, pv, terminal = self.before_silent_view(obs, H, load, pv, terminal)
            except Exception:
                pass
            actions = plan(obs.soc_kwh, load, pv, obs.price[:H], obs.co2[:H],
                           self.w_co2, self.w_cost, terminal, self.p)
            return clip_action(actions[0], obs.soc_kwh, self.p)
        except Exception:
            self.n_fallbacks += 1
            return greedy_action(obs, load[0], pv[0], self.p)


def variant(**cfg):
    cls = type("InfoVariant", (InfoPolicy,), cfg)

    class _A:
        def __init__(self):
            self.policy = cls()

        def act(self, obs):
            return self.policy.act(obs)
    return _A


def make_agent():
    return variant()()


def solo_S():
    return variant(SELL_BEFORE=False, RESET_ERR=False)()


def solo_V():
    return variant(SILENT_START=False, RESET_ERR=False)()


def solo_G():
    return variant(SILENT_START=False, SELL_BEFORE=False)()


def S_y_G():
    return variant(SELL_BEFORE=False)()


def sin_G():
    return variant(RESET_ERR=False)()
