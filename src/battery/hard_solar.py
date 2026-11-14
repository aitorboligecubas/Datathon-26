"""Previsión del consumo y de la solar para el HARD MODE (solar x12: hay horas con excedente).

Owner: P1 (optimizador), con P2 (datos). Se empaqueta en el agent.py del modo difícil.

CONTRATO (no cambiar sin avisar):
    f = NetLoadForecaster(prior, base)          # prior: dict de models/hard_solar.json, o None
                                                # base: el Forecaster de P2 (perfil de consumo y solar)
    f.update(obs, weather)                      # una vez por hora, antes de forecast
    load_kw, pv_kw = f.forecast(obs, times)     # np.ndarray de la longitud de `times`, >= 0, [0] = hora actual
    a = f.adjust_action(action_kw, obs, p)      # último retoque de la acción de esta hora (p: BatteryParams)
        obs.load_prev_kw / obs.pv_prev_kw: consumo y solar (ya x12) de la hora ANTERIOR
        weather: {"irradiancia_wm2", "temp_ambient_c", "temp_panel_c", "vent_ms"} de la hora anterior
Tiene que tardar menos de ~2 ms por hora. Solo numpy, pandas y math.

v0: delega en la previsión de P2 con el perfil solar del train multiplicado por 12. No usa la meteo.
"""
from typing import Optional

import numpy as np

from .obs import Obs

PV_FACTOR = 12.0            # la solar del modo difícil es 12 veces la del train
SOLAR_FILE = "hard_solar.json"


class NetLoadForecaster:
    def __init__(self, prior: Optional[dict], base):
        self.prior = prior or {}
        self.base = base
        try:    # la solar que verá el previsor de P2 es 12 veces la del train
            self.base.pv_prior = self.base.pv_prior * PV_FACTOR
        except Exception:
            pass
        self.weather = {}

    def update(self, obs: Obs, weather: Optional[dict] = None) -> None:
        self.weather = weather or {}
        self.base.update(obs)

    def forecast(self, obs: Obs, times: list) -> tuple:
        load, pv = self.base.forecast(obs, max(1, len(times)))
        return np.maximum(load, 0.0), np.maximum(pv, 0.0)

    def adjust_action(self, action_kw: float, obs: Obs, p) -> float:
        """Último retoque de la acción con lo que se sabe del consumo y la solar de ESTA hora.
        v0: no cambia nada (el tope de descarga por la lectura anterior ya lo aplica la política)."""
        return action_kw
