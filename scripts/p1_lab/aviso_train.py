"""Experimento "aviso del train": usar lo que el train dice del contador JUSTO ANTES de cada semana del test.

NO se empaqueta y NO está en el agente. Se construyó, se verificó y se DESCARTÓ el sábado 14/11:

- La idea. El train son los días 1 a 23/24 de cada mes y el test, los 7 últimos. En el train el contador no
  tiene ni una lectura del 1 al 23 de noviembre de 2025 (tests/test_agent.py lo comprueba). Un contador que
  lleva 23 días mudo lo más probable es que siga mudo una hora después: si la semana del 24 al 30 de
  noviembre estuviera en el test, llegaría con el consumo a 0.
- Las piezas. S: esa semana empieza ya como "semana sin datos" (no compra a ciegas en la primera hora).
  V: en las últimas horas de la semana anterior no se cuenta con poder descargar al otro lado, así que la
  batería llega vacía, como hace el óptimo. G: al cambiar de semana, el previsor olvida el error de la
  última hora de la semana anterior.
- Lo que daba. 60 episodios reservados con el calendario real (results/p1_banco/alineado_test_v4.txt):
  con noviembre a 0, +0,019 sobre el agente actual (+0,044 en la primera mitad), sin perder en ninguno de
  los 20 y a 0,005 del óptimo. Con noviembre normal, -0,001 de media (peor caso -0,03 en el banco estándar).
- Por qué se descartó. El envío 2 (agente actual, que ya trata una semana a 0) sacó EXACTAMENTE lo mismo
  que el envío 1 (4.288,0 kg y 8.913,11 EUR): en el test no hay ninguna semana con el contador a 0. Lo más
  probable es que la organización haya quitado las semanas sin datos (las slides hablaban de ~1.700 h,
  no de 2.016). Sin esa semana, la pieza V vende la batería a finales de octubre para nada.

    python scripts/p1_lab/compra_banco_alineado.py --suite test --agent scripts/p1_lab/aviso_train.py \
        --ref results/p1_banco/alineado_test_actual.csv --no-oracle        # variantes: :solo_S, :solo_V, :solo_G
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from battery.optimizer import plan  # noqa: E402
from battery.policy import FINAL_MONTH, MPCPolicy, greedy_action, hours_to_month_end  # noqa: E402
from battery.safety import clip_action  # noqa: E402

NAN = float("nan")
SILENT = ((2025, 11),)     # semanas del test que llegan detrás de 7 días del train sin contador
WEEK_H = 168


def next_block(ts) -> tuple:
    """(año, mes) de la semana del test que viene después de la de `ts`."""
    return (ts.year + 1, 1) if ts.month == 12 else (ts.year, ts.month + 1)


class AvisoPolicy(MPCPolicy):
    SILENT_START = True     # S
    SELL_BEFORE = True      # V
    RESET_ERR = True        # G

    def track_block(self, obs) -> bool:
        ts = obs.timestamp
        new_block = super().track_block(obs)
        if new_block and self.SILENT_START and ts is not None and (ts.year, ts.month) in SILENT:
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

    def no_data_view(self, obs, H: int, load, pv, terminal: float) -> tuple:
        ts = obs.timestamp
        last_block = ts is not None and (ts.year, ts.month) >= FINAL_MONTH
        K = hours_to_month_end(ts) if ts is not None and not last_block else H
        if self.SELL_BEFORE and ts is not None and not last_block and next_block(ts) in SILENT:
            K += WEEK_H      # la semana siguiente tampoco tendrá contador
        load, pv = np.array(load, dtype=float), np.array(pv, dtype=float)
        load[:K] = 0.0
        pv[:K] = 0.0
        if last_block:
            terminal = 0.0
        elif K >= H and not self.episode_ends_soon(obs) and len(self.valleys) >= 7:
            terminal = self.reserve_weight(int(math.ceil((K - H) / 24.0)) + 1) / self.p.eta_charge
        return load, pv, terminal

    def before_silent_view(self, obs, H: int, load, pv, terminal: float) -> tuple:
        """Últimas horas antes de una semana que se espera muda: lo que quede en la batería solo valdrá
        lo que cueste reponerlo en el mejor valle de esa semana (el precio de reserva)."""
        ts = obs.timestamp
        if not self.SELL_BEFORE or ts is None or self.episode_ends_soon(obs) or next_block(ts) not in SILENT:
            return load, pv, terminal
        k0 = hours_to_month_end(ts)
        if k0 >= H:
            return load, pv, terminal
        load, pv = np.array(load, dtype=float), np.array(pv, dtype=float)
        load[k0:] = 0.0
        pv[k0:] = 0.0
        if len(self.valleys) >= 7:
            terminal = self.reserve_weight(7) / self.p.eta_charge
        return load, pv, terminal

    def plan_action(self, obs) -> float:
        self.forecaster.update(obs)
        H = max(1, min(self.horizon, len(obs.price)))
        load, pv = self.forecaster.forecast(obs, H)
        if self.elapsed_s > self.time_budget_s:
            self.n_fallbacks += 1
            return greedy_action(obs, load[0], pv[0], self.p)
        try:
            terminal = self.terminal_value(obs, H)
            try:
                if self.no_data_block:
                    load, pv, terminal = self.no_data_view(obs, H, load, pv, terminal)
                else:
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
    cls = type("AvisoVariant", (AvisoPolicy,), cfg)

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
