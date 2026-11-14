"""Agente del HARD MODE (anunciado el sábado 14/11 a las 16:33).

Owner: P1 (optimizador).

Qué cambia respecto al modo estándar:
- La batería es 3 veces mayor: 6.000 kWh y ±1.500 kW.
- La solar es 12 veces mayor: hay horas con excedente (consumo - solar < 0), que se vierte gratis.
- El precio y el CO2 solo se conocen para las 3 horas siguientes. El resto hay que preverlo.
- La lectura de la hora anterior trae también la meteo (irradiancia, temperaturas y viento).

El agente sigue siendo el mismo GPS: planifica 24 h con un LP y ejecuta la primera hora. Lo nuevo es que
la ruta se traza con previsiones propias del precio y del CO2 (hard_market.py) y de la solar y el consumo
(hard_solar.py), y que el final del test ya no se ve en la previsión: se sabe por el calendario.
"""
import math
from typing import Mapping

import numpy as np
import pandas as pd

from .hard_market import KNOWN_HOURS, MARKET_FILE, MarketCand
from .hard_solar import SOLAR_FILE, make_netload
from .obs import Obs
from .optimizer import plan, score_weights
from .params import BatteryParams
from .policy import MPCPolicy, find_models_dir, greedy_action, load_json
from .safety import clip_action, feasible_range, soc_after

HARD_PARAMS = BatteryParams(capacity_kwh=6000.0, soc_init_kwh=3000.0, max_charge_kw=1500.0, max_discharge_kw=1500.0)
LAST_MONTHS = ((2026, 8),)   # el test acaba el 31/08/2026 (ENUNCIAT: 12 semanas): se llega con la batería vacía
# Qué hacer al final de cada semana del test (cada una acaba con su mes):
#   False: la batería sigue de una semana a la siguiente; solo se vacía al final del test (LAST_MONTHS).
#   True:  cada semana se cierra con la batería vacía.
# No hace falta elegir: el agente lo detecta solo (`HardPolicy.empty_weeks`). Si al empezar la segunda semana
# ve la batería al 50 % y no como él la dejó, el entorno la reinicia cada semana y pasa a cerrar cada una vacía.
EMPTY_EVERY_WEEK = False
# Si la simulación se corta cada RUN_STEPS pasos, el agente llega a ese corte con la batería vacía. 0 = no se
# cuenta con ningún corte. Se deja en 0: vaciar en la hora 1.008 sube el ranking público en cualquier caso
# (esa carga se paga en la mitad pública y se usa en la privada) y puede hundir el privado.
RUN_STEPS = 0
ACTION_MARGIN_KW = 0.0       # margen extra del último recorte (0: en el servidor la carga llega exacta, 0 infracciones)
WEATHER_KEYS = ("irradiancia_wm2", "temp_ambient_c", "temp_panel_c", "vent_ms")
ONE_HOUR = pd.Timedelta(hours=1)


def read_weather(raw_obs) -> dict:
    """Meteo de la hora anterior que trae `noves_dades_5min` en el modo difícil (NaN si falta)."""
    out = {}
    try:
        recent = raw_obs.get("noves_dades_5min")
        if isinstance(recent, Mapping):
            for key in WEATHER_KEYS:
                try:
                    v = float(recent.get(key))
                except (TypeError, ValueError):
                    v = float("nan")
                out[key] = v if math.isfinite(v) else float("nan")
    except Exception:
        pass
    return out


class HardPolicy(MPCPolicy):
    """El MPC del modo estándar con previsión propia de precio, CO2, solar y consumo, y el final por calendario."""

    def __init__(self, p: BatteryParams = HARD_PARAMS, models_dir=None, horizon: int = 24, **kwargs):
        if models_dir is None:
            models_dir = find_models_dir()
        super().__init__(p=p, models_dir=models_dir, horizon=horizon, **kwargs)
        prior = load_json(models_dir, MARKET_FILE)
        self.market = MarketCand(prior)     # con memoria del train; si faltan sus tablas, decide como el previsor base
        self.netload = make_netload(load_json(models_dir, SOLAR_FILE), self.forecaster)
        self.weather = {}
        self.seen_reading = False    # ha llegado alguna lectura de consumo válida (si no, es cosa del formato)
        self.n_blocks = 0            # semanas del test empezadas
        self.expected_soc = None     # carga que debería verse en la próxima observación
        self.empty_weeks = False     # el entorno reinicia la batería cada semana: se cierra cada una vacía
        self.last_seen = None        # fecha de la última observación (para notar si el reloj vuelve atrás)
        try:    # pesos del objetivo con la referencia del modo difícil (con 12 veces más solar cambia)
            self.w_co2, self.w_cost = score_weights(float(prior["co2_ref_kg_per_h"]), float(prior["cost_ref_eur_per_h"]))
        except Exception:
            pass

    def horizon_times(self, obs: Obs) -> list:
        """Fechas de las horas del plan. El test son los últimos 7 días de cada mes, uno detrás de otro:
        tras la última hora de un mes viene la primera de la última semana del siguiente. En el último
        mes del test, el plan se corta al acabar el mes."""
        ts = obs.timestamp
        if ts is None:
            return []
        last = EMPTY_EVERY_WEEK or self.empty_weeks or (ts.year, ts.month) in LAST_MONTHS
        times, t = [], ts
        for _ in range(self.horizon):
            times.append(t)
            nxt = t + ONE_HOUR
            if nxt.month != t.month:
                if last:
                    break
                nxt = nxt + ONE_HOUR * (24 * (nxt.days_in_month - 7))
            t = nxt
        if RUN_STEPS > 0:
            left = RUN_STEPS - (self.t % RUN_STEPS)       # pasos que quedan hasta el corte, contando el actual
            if left < len(times):
                times = times[:left]
        return times

    def no_data_week(self, times: list, load, pv, terminal: float, ends: bool) -> tuple:
        """Semana con el contador a 0 desde la primera hora (o más de un día): no hay consumo que cubrir
        hasta que acabe el mes. Lo que quede en la batería vale lo que costaría cargarlo más adelante
        (precio de reserva, como en el modo estándar), así que solo se compra en horas más baratas que eso."""
        month = times[0].month
        same = np.array([t.month == month for t in times])
        load, pv = np.array(load, dtype=float), np.array(pv, dtype=float)
        load[same] = 0.0      # la solar prevista se deja: si la hay, con consumo 0 se carga gratis del excedente
        if not ends and bool(same.all()) and len(self.valleys) >= 7:
            ts = times[0]
            left_h = (ts.days_in_month - ts.day) * 24 + (24 - ts.hour) - len(times)
            terminal = self.reserve_weight(int(math.ceil(max(left_h, 0) / 24.0)) + 1) / self.p.eta_charge
        return load, pv, terminal

    def plan_action(self, obs: Obs) -> float:
        self.netload.update(obs, self.weather)
        if self.no_data_block and self.no_reading:
            # Semana sin lecturas del contador (ni siquiera ceros): no se descarga y la batería se deja llena.
            return clip_action(self.p.max_charge_kw, obs.soc_kwh, self.p)
        times = self.horizon_times(obs)
        if times and len(obs.price) < KNOWN_HOURS:
            times = times[:len(obs.price)]          # el entorno ya da menos de 3 horas: se acaban los datos
        if not times:
            times = [None] * max(1, len(obs.price))
        H = len(times)
        if times[0] is None:
            load, pv = self.forecaster.forecast(obs, H)
        else:
            load, pv = self.netload.forecast(obs, times)
        if self.elapsed_s > self.time_budget_s:
            self.n_fallbacks += 1
            return greedy_action(obs, load[0], pv[0], self.p)
        try:
            if times[0] is None:
                price, co2 = obs.price[:H], obs.co2[:H]
            else:
                price, co2 = self.market.forecast(obs, times, self.weather)
            marginal = self.w_co2 * co2 + self.w_cost * price
            ends = H < self.horizon
            terminal = 0.0 if ends else float(np.quantile(marginal, self.terminal_quantile)) * self.p.eta_discharge
            if self.no_data_block and times[0] is not None:
                try:
                    load, pv, terminal = self.no_data_week(times, load, pv, terminal, ends)
                except Exception:
                    pass
            actions = plan(obs.soc_kwh, load, pv, price, co2, self.w_co2, self.w_cost, terminal, self.p)
            return clip_action(actions[0], obs.soc_kwh, self.p)
        except Exception:
            self.n_fallbacks += 1
            return greedy_action(obs, load[0], pv[0], self.p)

    def restarted(self, obs: Obs) -> bool:
        """True si el reloj vuelve atrás: el entorno empieza otra simulación con este mismo agente (por ejemplo,
        el test después de una prueba rápida). Se olvida lo deducido de la simulación anterior."""
        ts = obs.timestamp
        if ts is None:
            return False
        back = self.last_seen is not None and ts < self.last_seen - ONE_HOUR
        self.last_seen = ts
        if back:
            self.n_blocks, self.expected_soc, self.empty_weeks = 0, None, False
            self.block_hours, self.zero_hours, self.no_data_block, self.no_reading = 0, 0, False, False
        return back

    def watch_restart(self, obs: Obs, new_block: bool) -> None:
        """¿El entorno reinicia la batería al empezar cada semana? Se mira una sola vez, al empezar la segunda:
        si la carga es el 50 % justo y no la que dejó el agente, cada semana es una simulación aparte."""
        if not new_block:
            return
        self.n_blocks += 1
        if self.n_blocks == 2 and self.expected_soc is not None and math.isfinite(obs.soc_kwh):
            self.empty_weeks = (abs(obs.soc_kwh - self.expected_soc) > 1.0
                                and abs(obs.soc_kwh - 0.5 * self.p.capacity_kwh) < 1.0)

    def act_obs(self, obs: Obs) -> float:
        try:
            new_block = self.track_block(obs)      # semanas del test y semanas sin datos de contador (policy.py)
            if self.restarted(obs):
                new_block = True
            self.watch_restart(obs, new_block)
            if math.isfinite(obs.load_prev_kw):
                self.seen_reading = True
            if self.no_reading and not self.seen_reading:
                # Nunca ha llegado una lectura de consumo: es el formato, no una avería. Se planifica con el perfil.
                self.no_data_block, self.no_reading = False, False
        except Exception:
            new_block, self.no_data_block, self.no_reading = False, False, False
        if new_block:
            # Primera hora de una semana: la "hora anterior" es de hace un mes. No sirve ni para prever ni de tope.
            obs = obs._replace(load_prev_kw=float("nan"), pv_prev_kw=float("nan"))
            try:
                self.netload.new_block()
            except Exception:
                pass
        try:
            self.note_weight(obs)
        except Exception:
            pass
        action = self.cap_discharge(self.plan_action(obs), obs)
        try:
            action = float(self.netload.adjust_action(action, obs, self.p))
        except Exception:
            pass
        action = clip_action(action, obs.soc_kwh, self.p)
        try:
            lo, hi = feasible_range(obs.soc_kwh, self.p)
            if math.isfinite(lo) and math.isfinite(hi):
                action = min(max(action, min(0.0, lo + ACTION_MARGIN_KW)), max(0.0, hi - ACTION_MARGIN_KW))
                self.expected_soc = soc_after(obs.soc_kwh, action, self.p)
        except Exception:
            pass
        return action

    def read_battery(self, raw_obs) -> None:
        """El entorno del modo difícil da la capacidad y la potencia en cada observación: mandan ellas."""
        try:
            cap, power = float(raw_obs.get("cap_max_kwh")), float(raw_obs.get("power_max_kw"))
        except (TypeError, ValueError, AttributeError):
            return
        if math.isfinite(cap) and math.isfinite(power) and cap > 0 and power > 0:
            if cap != self.p.capacity_kwh or power != self.p.max_charge_kw:
                self.p = self.p._replace(capacity_kwh=cap, max_charge_kw=power, max_discharge_kw=power)

    def complete(self, raw_obs):
        """Rellena lo que falte para que el adaptador no falle: el precio y el CO2 actuales con el primer valor
        de su lista, y la hora y el día de la semana con los de la fecha. Sin esto, una clave ausente dejaría
        al agente parado todo el test sin avisar."""
        try:
            o = dict(raw_obs)
            for now_key, list_key in (("preu_actual", "preus_properes_24h"), ("co2_actual", "co2_properes_24h")):
                try:
                    v = float(o.get(now_key))
                except (TypeError, ValueError):
                    v = float("nan")
                if not math.isfinite(v):
                    try:
                        o[now_key] = float(o.get(list_key)[0])
                    except Exception:
                        o[now_key] = float("nan")
            for key in ("hour", "day_of_week"):
                try:
                    ok = math.isfinite(float(o.get(key)))
                except (TypeError, ValueError):
                    ok = False
                if not ok:
                    o.pop(key, None)       # el adaptador los saca de la fecha
            return o
        except Exception:
            return raw_obs

    def act(self, raw_obs) -> float:
        raw_obs = self.complete(raw_obs)
        self.weather = read_weather(raw_obs)
        self.read_battery(raw_obs)
        return super().act(raw_obs)


class HardBatteryAgent:
    """Punto de entrada del modo difícil (misma firma que BatteryAgent)."""

    def __init__(self):
        self.policy = HardPolicy()

    def act(self, obs) -> float:
        return self.policy.act(obs)
