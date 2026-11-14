"""Previsión del consumo y de la solar para el HARD MODE (solar x12: hay horas con excedente).

Owner: P1 (optimizador), con P2 (datos). Se empaqueta en el agent.py del modo difícil.

CONTRATO (no cambiar sin avisar):
    f = NetLoadForecaster(prior, base)          # prior: dict de models/hard_solar.json, o None
                                                # base: el Forecaster de P2 (perfil de consumo por hora de la semana)
    f.update(obs, weather)                      # una vez por hora, antes de forecast
    load_kw, pv_kw = f.forecast(obs, times)     # np.ndarray de la longitud de `times`, >= 0, [0] = hora actual
    a = f.adjust_action(action_kw, obs, p)      # último retoque de la acción de esta hora (p: BatteryParams)
        obs.load_prev_kw / obs.pv_prev_kw: consumo y solar (ya x12) de la hora ANTERIOR
        weather: {"irradiancia_wm2", "temp_ambient_c", "temp_panel_c", "vent_ms"} de la hora anterior
Tiene que tardar menos de ~2 ms por hora. Solo numpy, pandas y math.

Cómo prevé:
- Solar: "cielo despejado" del mes a esa hora (percentil 90 del train) por la claridad del día, que es
  solar medida / cielo despejado en la hora anterior. La claridad se va acercando a la media del mes
  cuanto más lejos se mira.
- Consumo: perfil por hora de la semana (el de P2) por el cociente consumo medido / perfil de la hora
  anterior, que también se apaga con el horizonte.
Y un retoque final de la acción (`adjust_action`), porque la previsión de la hora actual se equivoca
(unos 140 kW de día): descargar de más es tirar energía y cargar de menos es perder excedente gratis, así
que se descarga un poco por debajo de lo previsto y se carga un poco por encima.
"""
import math
from typing import Optional

import numpy as np

from .obs import Obs

PV_FACTOR = 12.0            # la solar del modo difícil es 12 veces la del train
SOLAR_FILE = "hard_solar.json"
CLEAR_MIN_KW = 30.0         # por debajo de esto el "cielo despejado" no sirve para medir la claridad
PV_DAMP = 0.85              # cuánto se mantiene la claridad de una hora a la siguiente
LOAD_DAMP = 0.90            # ídem para el cociente consumo / perfil
Z_DISCHARGE = 1.0           # margen al descargar, en desviaciones típicas del error de la hora actual
Z_CHARGE = 1.0              # margen al cargar cuando puede haber excedente
DEFAULT_SD_KW = 150.0       # error típico del consumo neto de la hora actual si no hay tabla


class NetLoadForecaster:
    def __init__(self, prior: Optional[dict], base, z_discharge: float = Z_DISCHARGE, z_charge: float = Z_CHARGE):
        self.base = base
        self.z_discharge, self.z_charge = z_discharge, z_charge
        prior = prior or {}
        try:
            self.clear = np.asarray(prior["pv_clear"], dtype=float)       # [mes 0-11][hora 0-23], kW ya x12
            self.mean = np.asarray(prior["pv_mean"], dtype=float)
            self.sd = np.asarray(prior["net_sd"], dtype=float)            # [hora 0-23]
            self.ok = self.clear.shape == (12, 24) and self.mean.shape == (12, 24) and self.sd.shape == (24,)
        except Exception:
            self.ok = False
        try:    # sin tabla propia: la solar que verá el previsor de P2 es 12 veces la del train
            self.base.pv_prior = self.base.pv_prior * PV_FACTOR
        except Exception:
            pass
        self.weather = {}
        self.clearness = float("nan")     # solar medida / cielo despejado, de la última hora con sol
        self.load_ratio = 1.0             # consumo medido / perfil, de la hora anterior
        self.meter_down = False
        self.net_now = float("nan")       # previsión del consumo neto de la hora actual (para adjust_action)
        self.hour_now = 0

    def update(self, obs: Obs, weather: Optional[dict] = None) -> None:
        self.weather = weather or {}
        prev_how = (obs.hour_of_week - 1) % 168
        expected = self.load_profile(prev_how)          # antes de que el perfil aprenda de esta lectura
        self.base.update(obs)
        load, pv, ts = obs.load_prev_kw, obs.pv_prev_kw, obs.timestamp
        self.meter_down = load == 0.0
        if math.isfinite(load) and load > 0 and expected > 0:
            self.load_ratio = min(max(load / expected, 0.3), 3.0)
        if self.ok and ts is not None and math.isfinite(pv):
            prev_hour = (obs.hour - 1) % 24
            month = ts.month if obs.hour > 0 else (ts.month - 1 if ts.day == 1 else ts.month)
            clear_prev = float(self.clear[(month - 1) % 12][prev_hour])
            if clear_prev >= CLEAR_MIN_KW:
                self.clearness = min(max(pv / clear_prev, 0.0), 1.5)

    def load_profile(self, how: int) -> float:
        try:
            v = float(self.base.load_how[how % 168])
            return v if math.isfinite(v) else float("nan")
        except Exception:
            return float("nan")

    def forecast(self, obs: Obs, times: list) -> tuple:
        H = max(1, len(times))
        if not self.ok or times[0] is None:
            load, pv = self.base.forecast(obs, H)
            self.net_now, self.hour_now = float(load[0] - pv[0]), obs.hour
            return np.maximum(load, 0.0), np.maximum(pv, 0.0)
        base_load, _ = self.base.forecast(obs, H)
        load, pv = np.empty(H), np.empty(H)
        for k, t in enumerate(times):
            m, h = t.month - 1, t.hour
            clear, mean = float(self.clear[m][h]), float(self.mean[m][h])
            typical = mean / clear if clear > 0 else 0.0
            c = self.clearness if math.isfinite(self.clearness) else typical
            c = typical + (c - typical) * PV_DAMP ** (k + 1)
            pv[k] = clear * c
            prof = self.load_profile(t.dayofweek * 24 + h)
            if math.isfinite(prof) and prof > 0:
                load[k] = prof * (1.0 + (self.load_ratio - 1.0) * LOAD_DAMP ** (k + 1))
            else:
                load[k] = base_load[k]
        if self.meter_down:          # contador caído (lectura 0 exacta): si sigue, descargar es tirar energía
            load[0] = 0.0
            pv[0] = 0.0
        load, pv = np.maximum(load, 0.0), np.maximum(pv, 0.0)
        self.net_now, self.hour_now = float(load[0] - pv[0]), times[0].hour
        return load, pv

    def adjust_action(self, action_kw: float, obs: Obs, p) -> float:
        """Margen de seguridad con el consumo neto de ESTA hora, que solo se conoce aproximadamente."""
        net = self.net_now
        if not math.isfinite(net):
            return action_kw
        sd = float(self.sd[self.hour_now % 24]) if self.ok else DEFAULT_SD_KW
        if action_kw < 0:
            # Descargar por encima del consumo neto real es verter: se descarga algo menos de lo previsto.
            return -min(-action_kw, max(net - self.z_discharge * sd, 0.0))
        surplus = -(net - self.z_charge * sd)       # excedente solar que puede llegar a haber esta hora
        if surplus > action_kw and net < sd:
            # Si puede sobrar solar, se carga al menos eso: lo que no se guarde se regala a la red.
            return min(surplus, p.max_charge_kw)
        return action_kw
