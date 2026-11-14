"""Candidato "trans": transiciones y creencias sobre cuánto dura un contador a 0.

Parte de MPCPolicy (el agente actual, "v2") y cambia cinco piezas. Cada una tiene su interruptor para
poder medirla sola (números en results/p1_banco/trans_notas.md):

A. CARRY_ZERO: la racha a 0 no se corta al cambiar de semana.
   v2 ignora siempre la lectura anterior en la primera hora de una semana (es de otro mes) y descarga con
   la previsión normal. Si la semana anterior acabó a 0 y la nueva también viene a 0, tira hasta 500 kWh
   (es lo que le hacía perder contra v1 en dos_ceros). Aquí, si esa última lectura era 0, el agente sigue
   creyendo que el contador está caído hasta que vea consumo: esa hora no descarga y actúa como en una
   semana sin datos. A la hora siguiente ya tiene una lectura de la semana nueva y decide como siempre.
B. FIRST_READING: en el primer paso del episodio la lectura es de la PROPIA hora.
   environment.py da `row["load_kw"]` en t = 0, no la hora anterior. Si es 0, la semana empieza sin datos
   desde la hora 0 (v2 la ignoraba y tardaba una hora en enterarse).
C. POOL_DAYS = 7: el precio de reserva se calcula con los valles de los 7 últimos días vistos (v2: 35).
   El nivel de los valles cambia de un mes a otro casi tanto como de un día a otro (desviación del
   logaritmo en el train: 0,21 entre meses, 0,20 entre días del mismo mes). Con 35 días de cinco meses
   distintos, la reserva puede quedar por debajo de todos los valles de la semana: el agente no compra
   nunca y, si el consumo vuelve a media semana, lo pilla con la batería vacía (dev-08: 0,084 perdidos).
E. LINDY: en una avería corta a media semana, el consumo vuelve "probablemente", no "seguro".
   v2 planifica como si el consumo volviese seguro en la hora siguiente, y compra de madrugada para un
   pico de la mañana que, si la avería sigue, no se puede cubrir. Aquí, tras z horas a 0, la probabilidad
   de poder descargar dentro de k horas es k / (z + k), y el LP recibe la descarga esperada.

G. RESET_ERR: al cambiar de semana, el previsor olvida el error de la última hora de la semana anterior.
   v2 ya no usa esa lectura (es de otro mes), pero el previsor seguía sumando su corrección por
   persistencia: tras la semana de Navidad, la previsión de la primera hora de enero quedaba en ~220 kW
   (real: 1.104) y el agente descargaba 220 kW en vez de 471. v1 no lo sufría.

Probado y NO adoptado (queda el interruptor para reproducir los números):
D. PATIENCE = "half": contar solo con la mitad de los días que quedan para comprar. Cuesta 0,0007 en nov0
   y solo compensa si el consumo vuelve a media semana más de una vez de cada tres.

Se puede llevar a src/battery/policy.py tal cual: solo numpy y math, determinista, sin ficheros.
"""
import math
import sys
from collections import deque
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from battery.optimizer import plan  # noqa: E402
from battery.policy import (BLOCK_GAP_H, FINAL_MONTH, LONG_OUTAGE_H, MPCPolicy, greedy_action,  # noqa: E402
                            hours_to_month_end)
from battery.safety import clip_action  # noqa: E402

NAN = float("nan")


class TransPolicy(MPCPolicy):
    CARRY_ZERO = True       # A
    FIRST_READING = True    # B
    POOL_DAYS = 7           # C (v2: 35)
    PATIENCE = "full"       # D, no adoptada: "full" (v2) | "half" | "one"
    LINDY = True            # E: tras z horas de avería a media semana, P(poder descargar en k horas) = k/(z+k)
    RESET_ERR = True        # G: el previsor olvida el error de la semana anterior al cambiar de semana

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.valleys = deque(maxlen=self.POOL_DAYS)
        self.keep_reading = False    # la lectura de esta hora sirve aunque sea la primera de un bloque

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
            if self.RESET_ERR:
                # La corrección por persistencia del previsor es el error de la última hora de la semana
                # anterior (otro mes): tras Navidad deja la previsión de la primera hora de enero en ~220 kW.
                try:
                    self.forecaster.err_load, self.forecaster.err_pv = 0.0, 0.0
                except Exception:
                    pass
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
    def patience(self, days_left: int) -> int:
        """Días con los que se cuenta para comprar. "full": todos los que quedan (el contador no vuelve
        hasta fin de mes). "half": la mitad (el consumo puede volver en cualquier momento de la semana)."""
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
            terminal = self.reserve_weight(self.patience(days_left)) / self.p.eta_charge
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
V2 = dict(CARRY_ZERO=False, FIRST_READING=False, POOL_DAYS=35, PATIENCE="full", LINDY=False, RESET_ERR=False)


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


def sin_A():
    return variant(CARRY_ZERO=False)()


def sin_C():
    return variant(POOL_DAYS=35)()


def sin_E():
    return variant(LINDY=False)()


def solo_G():
    return variant(**dict(V2, RESET_ERR=True))()


def sin_G():
    return variant(RESET_ERR=False)()


def con_D():
    return variant(PATIENCE="half")()


def con_D_one():
    return variant(PATIENCE="one")()
