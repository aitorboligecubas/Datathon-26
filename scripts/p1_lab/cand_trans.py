"""Candidato "trans": transiciones y creencias sobre cuánto dura un contador a 0.

Parte de MPCPolicy (el agente actual, "v2") y cambia cuatro piezas, cada una con su interruptor para
poder medirla sola (ver results/p1_banco/trans_notas.md):

A. CARRY_ZERO. Al cambiar de semana, si la última lectura de la semana anterior era 0, la racha a 0
   sigue hasta que se vea consumo: en esa primera hora no se descarga a ciegas y se actúa como en una
   semana sin datos. v2 ignoraba siempre esa lectura (es de otro mes) y descargaba con la previsión normal:
   si la semana nueva también venía a 0, tiraba hasta 500 kWh.
B. FIRST_READING. En el primer paso del episodio el entorno da el consumo de la PROPIA hora
   (environment.py: `if self.t > 0 else row["load_kw"]`), así que no es una lectura vieja: sirve de tope
   de descarga y, si es 0, la semana empieza sin datos desde la hora 0.
C. POOL_DAYS. El precio de reserva de una semana sin datos se calcula con los valles de los últimos 7 días
   vistos (v2: 35). El nivel de los valles cambia mucho de un mes a otro (media mensual de 4,0 a 8,0 en
   el train): con 35 días de otros meses la reserva podía quedar por debajo de todos los valles de la
   semana y el agente no compraba nunca (y, si el consumo volvía, lo pillaba con la batería vacía).
D. PATIENCE. Cuántos días "quedan" para comprar. v2 contaba todos los que faltan hasta fin de mes (cree
   que el contador no vuelve). Aquí, la mitad: si no sabemos cuándo vuelve el consumo y puede ser en
   cualquier momento de lo que queda de semana, lo esperado es la mitad.

Se puede llevar a src/battery/policy.py tal cual: solo numpy y math, determinista, sin ficheros.
"""
import math
import sys
from collections import deque
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from battery.optimizer import plan  # noqa: E402
from battery.policy import (BLOCK_GAP_H, FINAL_MONTH, LONG_OUTAGE_H, VALLEY_HOURS, MPCPolicy,  # noqa: E402
                            greedy_action, hours_to_month_end)
from battery.safety import clip_action  # noqa: E402

NAN = float("nan")


class TransPolicy(MPCPolicy):
    CARRY_ZERO = True       # A
    FIRST_READING = True    # B
    POOL_DAYS = 7           # C (v2: 35)
    PATIENCE = "half"       # D: "full" (v2) | "half" | "one"
    LINDY = True            # E: tras z horas de avería a media semana, P(poder descargar en k horas) = k/(z+k)
    LEVEL = True            # F: la reserva se reescala al nivel de los valles de esta semana

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.valleys = deque(maxlen=self.POOL_DAYS)
        self.keep_reading = False    # la lectura de esta hora sirve aunque sea la primera de un bloque
        self.block_valleys = []      # valles de los días ya completos de la semana en curso

    # ------------------------------------------------------------------ seguimiento de bloques
    def track_block(self, obs) -> bool:
        ts = obs.timestamp
        first_step = self.prev_ts is None and self.t == 0
        new_block = False
        if ts is not None:
            prev, self.prev_ts = self.prev_ts, ts
            if prev is None:
                new_block = True
            else:
                new_block = abs((ts - prev).total_seconds()) / 3600.0 > BLOCK_GAP_H
        zero = obs.load_prev_kw == 0.0
        if new_block:
            self.block_hours = 0
            if first_step:
                carry = zero and self.FIRST_READING        # es el consumo de esta misma hora
            else:
                carry = zero and self.CARRY_ZERO           # la semana anterior acabó a 0
            self.keep_reading = carry                      # una lectura con consumo se ignora, como en v2
            self.zero_hours = self.zero_hours + 1 if carry else 0
            self.no_data_block = carry
            return True
        self.keep_reading = True
        self.block_hours += 1
        if zero:
            self.zero_hours += 1
            if self.block_hours == 1 or self.zero_hours >= LONG_OUTAGE_H:
                self.no_data_block = True
        else:
            self.zero_hours, self.no_data_block = 0, False
        return False

    def act_obs(self, obs) -> float:
        try:
            new_block = self.track_block(obs)
        except Exception:
            new_block, self.no_data_block, self.keep_reading = False, False, True
        if new_block and not self.keep_reading:
            # Primera hora de una semana nueva y la anterior acabó con consumo: esa lectura es de hace
            # un mes y no sirve ni de previsión ni de tope.
            obs = obs._replace(load_prev_kw=NAN, pv_prev_kw=NAN)
        try:
            self.note_weight(obs)
        except Exception:
            pass
        return self.cap_discharge(self.plan_action(obs), obs)

    # ------------------------------------------------------------------ avería a media semana
    def outage_view(self, H: int, load, pv) -> tuple:
        """Avería corta (menos de un día a 0, empezada a media semana): consumo que se puede cubrir.

        v2 contaba con que el consumo volvía seguro en la hora siguiente. Aquí, tras z horas a 0, la
        probabilidad de poder descargar dentro de k horas es k / (z + k): una avería tiene las mismas
        opciones de durar otro tanto que de acabar antes (a k = z, 1/2), y la hora en que vuelve el
        consumo se pierde siempre porque todavía no se ha visto ninguna lectura. El LP recibe la descarga
        esperada: como mucho 500 kW x esa probabilidad en cada hora. Sin parámetros. Solo cambia
        decisiones de carga: deja de comprar con poco margen para un pico que, si la avería sigue,
        no se podrá cubrir; las compras con margen amplio (valle del día) se siguen haciendo.
        """
        z = int(self.zero_hours)
        if z < 1:
            return load, pv
        net = np.clip(np.asarray(load, dtype=float) - np.asarray(pv, dtype=float), 0.0, self.p.max_discharge_kw)
        k = np.arange(H, dtype=float)
        return net * k / (z + k), np.zeros(H)

    def plan_action(self, obs) -> float:
        """Como MPCPolicy.plan_action, con la vista de avería corta entre la previsión y el LP."""
        self.forecaster.update(obs)
        H = max(1, min(self.horizon, len(obs.price)))
        load, pv = self.forecaster.forecast(obs, H)
        if self.elapsed_s > self.time_budget_s:
            self.n_fallbacks += 1
            return greedy_action(obs, load[0], pv[0], self.p)
        try:
            terminal = self.terminal_value(obs, H)
            if self.no_data_block:
                try:
                    load, pv, terminal = self.no_data_view(obs, H, load, pv, terminal)
                except Exception:
                    pass
            elif self.LINDY and obs.load_prev_kw == 0.0:
                try:
                    load, pv = self.outage_view(H, load, pv)
                except Exception:
                    pass
            actions = plan(obs.soc_kwh, load, pv, obs.price[:H], obs.co2[:H],
                           self.w_co2, self.w_cost, terminal, self.p)
            return clip_action(actions[0], obs.soc_kwh, self.p)
        except Exception:
            self.n_fallbacks += 1
            return greedy_action(obs, load[0], pv[0], self.p)

    # ------------------------------------------------------------------ semana sin datos
    def note_weight(self, obs) -> None:
        """Como en v2, y además guarda aparte los valles de los días ya completos de esta semana."""
        w = self.w_co2 * obs.co2[0] + self.w_cost * obs.price[0]
        key = (obs.timestamp.year, obs.timestamp.month, obs.timestamp.day) if obs.timestamp is not None else None
        if key != self.day_key:
            if len(self.day_weights) >= 20:
                valley = sum(sorted(self.day_weights)[:VALLEY_HOURS]) / VALLEY_HOURS
                self.valleys.append(valley)
                self.block_valleys.append(valley)
            self.day_key, self.day_weights = key, []
        if self.block_hours == 0:
            self.block_valleys = []      # semana nueva: el día que se acaba de cerrar era de la anterior
        if math.isfinite(w):
            self.day_weights.append(float(w))

    def level_factor(self) -> float:
        """Cuánto hay que subir o bajar la reserva para ponerla al nivel de esta semana.

        El nivel de los valles cambia de un mes a otro casi tanto como de un día a otro dentro del mes
        (en el train, desviación del logaritmo: 0,21 entre meses y 0,20 entre días del mismo mes). Por
        eso la media de la historia cuenta como UN día más de esta semana: nivel = (media de la historia
        + valles de los días ya vistos esta semana) / (1 + días vistos).
        """
        x = np.asarray(self.valleys, dtype=float)
        m = float(x.mean())
        n = len(self.block_valleys)
        if n == 0 or not m > 0:
            return 1.0
        return (m + float(sum(self.block_valleys))) / ((1 + n) * m)

    def patience(self, days_left: int) -> int:
        if self.PATIENCE == "half":
            return max(1, int(math.ceil(days_left / 2.0)))
        if self.PATIENCE == "one":
            return 1
        return days_left

    def no_data_view(self, obs, H: int, load, pv, terminal: float) -> tuple:
        ts = obs.timestamp
        last_block = ts is not None and (ts.year, ts.month) >= FINAL_MONTH
        K = hours_to_month_end(ts) if ts is not None and not last_block else H
        load, pv = np.array(load, dtype=float), np.array(pv, dtype=float)
        load[:K] = 0.0
        pv[:K] = 0.0
        if last_block:
            terminal = 0.0
        elif K >= H and not self.episode_ends_soon(obs) and len(self.valleys) >= min(7, self.POOL_DAYS):
            days_left = int(math.ceil((K - H) / 24.0)) + 1
            reserve = self.reserve_weight(self.patience(days_left))
            if self.LEVEL:
                reserve *= self.level_factor()
            terminal = reserve / self.p.eta_charge
        return load, pv, terminal


def variant(**cfg):
    """Fábrica de agentes con otra configuración (para medir cada pieza sola)."""
    cls = type("TransVariant", (TransPolicy,), cfg)

    class _A:
        def __init__(self):
            self.policy = cls()

        def act(self, obs):
            return self.policy.act(obs)
    return _A


class _Agent:
    def __init__(self):
        self.policy = TransPolicy()

    def act(self, obs):
        return self.policy.act(obs)


def make_agent():
    return _Agent()


# Variantes para las ablaciones (scripts/p1_banco.py --agent scripts/p1_lab/cand_trans.py:solo_A, etc.)
V2 = dict(CARRY_ZERO=False, FIRST_READING=False, POOL_DAYS=35, PATIENCE="full", LINDY=False, LEVEL=False)


def como_v2():
    return variant(**V2)()


def solo_A():
    return variant(**dict(V2, CARRY_ZERO=True))()


def solo_B():
    return variant(**dict(V2, FIRST_READING=True))()


def solo_C():
    return variant(**dict(V2, POOL_DAYS=7))()


def solo_D():
    return variant(**dict(V2, PATIENCE="half"))()


def solo_E():
    return variant(**dict(V2, LINDY=True))()


def sin_E():
    return variant(LINDY=False, LEVEL=False)()


def sin_F():
    return variant(LEVEL=False)()


def solo_F():
    return variant(**dict(V2, LEVEL=True))()


def f_full():
    return variant(PATIENCE="full")()


def abc_full():
    return variant(PATIENCE="full")()


def abc_one():
    return variant(PATIENCE="one")()


def abc_pool14():
    return variant(POOL_DAYS=14)()


def abc_pool14_full():
    return variant(POOL_DAYS=14, PATIENCE="full")()
