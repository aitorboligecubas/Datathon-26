"""Previsión de demanda (load) y producción solar (pv) para las próximas H horas.

Owner: P2 (previsión).

El entorno solo da la demanda y la solar de la hora ANTERIOR: hay que prever la
hora actual y las siguientes. v0 (punto de partida, mejorable):
- Demanda: perfil por hora de la semana (168 casillas), aprendido online con media
  exponencial y arrancado con el perfil de entrenamiento (models/forecaster.json),
  más una corrección por persistencia del último error que se apaga con el horizonte.
- Solar: media de las últimas `pv_days` observaciones a esa hora del día (capta la
  estación), con el perfil de entrenamiento de respaldo, más la misma corrección.

CONTRATO con P1 (no cambiar sin avisar):
    f = Forecaster(prior)          # prior: dict cargado de models/ o None
    f.update(obs)                  # una vez por hora, antes de forecast
    load_kw, pv_kw = f.forecast(obs, h)
        -> dos np.ndarray de longitud h, en kW, >= 0, índice 0 = hora ACTUAL
Tiene que tardar < 2 ms por llamada (2.016 llamadas en < 60 s junto con el LP).
Solo puede importar: numpy, pandas, scipy, sklearn, joblib, xgboost, lightgbm,
math, datetime, collections, itertools, random, json, pathlib, typing.
"""
import math
from collections import deque
from typing import Optional

import numpy as np

from .obs import Obs

FORECASTER_FILE = "forecaster.json"


class Forecaster:
    def __init__(self, prior: Optional[dict] = None, alpha: float = 0.5,
                 rho_load: float = 0.85, rho_pv: float = 0.75, pv_days: int = 3):
        self.alpha = alpha          # peso de la observación nueva en el perfil semanal
        self.rho_load = rho_load    # persistencia del error de demanda por hora
        self.rho_pv = rho_pv        # persistencia del error solar por hora
        self.load_how = (np.array(prior["load_how"], dtype=float) if prior
                         else np.full(168, np.nan))
        self.pv_prior = (np.array(prior["pv_hod"], dtype=float) if prior
                         else np.full(24, np.nan))
        self.pv_recent = [deque(maxlen=pv_days) for _ in range(24)]
        self.last_load = float("nan")
        self.err_load = 0.0
        self.err_pv = 0.0

    def _load_profile(self, how: int) -> float:
        v = self.load_how[how % 168]
        return float(v) if math.isfinite(v) else self.last_load

    def _pv_profile(self, hod: int) -> float:
        recent = self.pv_recent[hod % 24]
        if recent:
            return float(sum(recent) / len(recent))
        v = self.pv_prior[hod % 24]
        return float(v) if math.isfinite(v) else 0.0

    def update(self, obs: Obs) -> None:
        """Incorpora la demanda y la solar de la hora anterior."""
        prev_how = (obs.hour_of_week - 1) % 168
        prev_hod = (obs.hour - 1) % 24
        load, pv = obs.load_prev_kw, obs.pv_prev_kw
        if math.isfinite(load):
            expected = self._load_profile(prev_how)
            self.err_load = load - expected if math.isfinite(expected) else 0.0
            old = self.load_how[prev_how]
            self.load_how[prev_how] = load if not math.isfinite(old) else (
                (1 - self.alpha) * old + self.alpha * load)
            self.last_load = load
        if math.isfinite(pv):
            self.err_pv = pv - self._pv_profile(prev_hod)
            self.pv_recent[prev_hod].append(pv)

    def forecast(self, obs: Obs, h: int) -> tuple:
        how0, hod0 = obs.hour_of_week, obs.hour
        load = np.empty(h)
        pv = np.empty(h)
        for k in range(h):
            lp = self._load_profile(how0 + k)
            load[k] = (lp if math.isfinite(lp) else 0.0) + self.err_load * self.rho_load ** (k + 1)
            pp = self._pv_profile(hod0 + k)
            pv[k] = pp + (self.err_pv * self.rho_pv ** (k + 1) if pp > 0 else 0.0)
        return np.maximum(load, 0.0), np.maximum(pv, 0.0)
