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

from .hard_market import KNOWN_HOURS, MARKET_FILE, MarketForecaster
from .hard_solar import SOLAR_FILE, NetLoadForecaster
from .obs import Obs
from .optimizer import plan, score_weights
from .params import BatteryParams
from .policy import MPCPolicy, find_models_dir, greedy_action, load_json
from .safety import clip_action

HARD_PARAMS = BatteryParams(capacity_kwh=6000.0, soc_init_kwh=3000.0, max_charge_kw=1500.0, max_discharge_kw=1500.0)
LAST_MONTHS = ((2026, 7), (2026, 8))   # el test acaba al final de uno de estos meses: se llega con la batería vacía
# Qué hacer al final de cada semana del test (cada una acaba con su mes):
#   False: la batería sigue de una semana a la siguiente; solo se vacía al final del test (LAST_MONTHS).
#   True:  cada semana se cierra con la batería vacía (por si cada semana, o cada mitad, se simula por separado).
EMPTY_EVERY_WEEK = False
# Si la simulación se corta cada RUN_STEPS pasos (la web dice que el conjunto público son 1.008 horas), el
# agente llega a ese corte con la batería vacía. 0 = no se cuenta con ningún corte por número de pasos.
RUN_STEPS = 0
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
        self.market = MarketForecaster(prior)
        self.netload = NetLoadForecaster(load_json(models_dir, SOLAR_FILE), self.forecaster)
        self.weather = {}
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
        last = EMPTY_EVERY_WEEK or (ts.year, ts.month) in LAST_MONTHS
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
        load[same] = 0.0
        pv[same] = 0.0
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

    def act_obs(self, obs: Obs) -> float:
        try:
            new_block = self.track_block(obs)      # semanas del test y semanas sin datos de contador (policy.py)
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
        return clip_action(action, obs.soc_kwh, self.p)

    def read_battery(self, raw_obs) -> None:
        """El entorno del modo difícil da la capacidad y la potencia en cada observación: mandan ellas."""
        try:
            cap, power = float(raw_obs.get("cap_max_kwh")), float(raw_obs.get("power_max_kw"))
        except (TypeError, ValueError, AttributeError):
            return
        if math.isfinite(cap) and math.isfinite(power) and cap > 0 and power > 0:
            if cap != self.p.capacity_kwh or power != self.p.max_charge_kw:
                self.p = self.p._replace(capacity_kwh=cap, max_charge_kw=power, max_discharge_kw=power)

    def act(self, raw_obs) -> float:
        self.weather = read_weather(raw_obs)
        self.read_battery(raw_obs)
        return super().act(raw_obs)


class HardBatteryAgent:
    """Punto de entrada del modo difícil (misma firma que BatteryAgent)."""

    def __init__(self):
        self.policy = HardPolicy()

    def act(self, obs) -> float:
        return self.policy.act(obs)
