"""Previsión del precio y del CO2 para el HARD MODE (solo se conocen 3 horas).

Owner: P1 (optimizador), con P2 (datos). Se empaqueta en el agent.py del modo difícil.

CONTRATO (no cambiar sin avisar):
    m = MarketForecaster(prior)                 # prior: dict de models/hard_market.json, o None
    price, co2 = m.forecast(obs, times, weather)
        obs.price / obs.co2: lo que da el entorno (la hora actual y las siguientes, 3 valores)
        times: lista de pd.Timestamp, una por hora del plan ([0] = hora actual)
        weather: dict con la meteo de la hora anterior (o None)
        -> dos np.ndarray de la misma longitud que `times`, >= 0; las horas conocidas se respetan
Se llama una vez por hora y tiene que tardar menos de ~2 ms. Solo numpy, pandas y math.
"""
import math
from typing import Optional

import numpy as np

from .obs import Obs

KNOWN_HOURS = 3             # horas de precio y CO2 que da el entorno (la actual y las dos siguientes)
MARKET_FILE = "hard_market.json"
LEVEL_PRIOR_H = 6.0         # horas "ficticias" a nivel 1 con las que se estima el nivel al empezar una semana
LEVEL_WINDOW_H = 48         # horas recientes con las que se estima el nivel del precio y del CO2
YESTERDAY_WEIGHT = 0.5      # cuánto pesa "ayer a esta hora" frente al nivel reciente


def hour_index(ts) -> int:
    """Número de hora absoluto (para medir cuántas horas separan dos fechas sin restar fechas)."""
    return ts.toordinal() * 24 + ts.hour


class MarketForecaster:
    """Previsión del precio y del CO2 más allá de las 3 horas que da el entorno.

    Perfil por mes, tipo de día (laborable, sábado, domingo) y hora, aprendido en el train, escalado al
    nivel de los últimos días y corregido con lo que pasó ayer a la misma hora.
    """

    def __init__(self, prior: Optional[dict] = None, yesterday_weight: float = YESTERDAY_WEIGHT):
        self.prof = {}
        if prior:
            for name in ("price", "co2"):
                self.prof[name] = np.asarray(prior[name], dtype=float)      # [mes 0-11][tipo 0-2][hora 0-23]
        self.seen = {"price": {}, "co2": {}}       # número de hora -> (valor real, valor del perfil)
        self.yesterday_weight = yesterday_weight

    def profile(self, name: str, ts) -> float:
        p = self.prof.get(name)
        if p is None:
            return float("nan")
        wd = ts.dayofweek
        return float(p[ts.month - 1][0 if wd < 5 else (1 if wd == 5 else 2)][ts.hour])

    def remember(self, obs: Obs, times: list) -> None:
        """Guarda los valores reales que se acaban de conocer (la hora actual y las siguientes)."""
        now = hour_index(times[0])
        for name, arr in (("price", obs.price), ("co2", obs.co2)):
            store = self.seen[name]
            for k in range(min(len(arr), len(times))):
                store[hour_index(times[k])] = (float(arr[k]), self.profile(name, times[k]))
            if len(store) > 400:
                for key in [key for key in store if key < now - 200]:
                    del store[key]

    def level(self, name: str, now: int) -> float:
        """Nivel reciente frente al perfil: mediana de real/perfil en las últimas horas, tirando a 1
        cuando hay pocas (al empezar una semana solo se conocen 3)."""
        ratios = [v / b for key, (v, b) in self.seen[name].items()
                  if now - LEVEL_WINDOW_H <= key <= now + KNOWN_HOURS and b > 0 and math.isfinite(v) and math.isfinite(b)]
        if not ratios:
            return 1.0
        n = float(len(ratios))
        return float((n * float(np.median(ratios)) + LEVEL_PRIOR_H) / (n + LEVEL_PRIOR_H))

    def forecast(self, obs: Obs, times: list, weather: Optional[dict] = None) -> tuple:
        """Precio y CO2 para cada fecha de `times` ([0] = hora actual). Lo conocido se respeta."""
        self.remember(obs, times)
        now = hour_index(times[0])
        out = []
        for name, arr in (("price", obs.price), ("co2", obs.co2)):
            lvl = self.level(name, now)
            store = self.seen[name]
            x = np.empty(len(times))
            for k, t in enumerate(times):
                if k < len(arr):
                    x[k] = arr[k]
                    continue
                base = self.profile(name, t)
                if not (base > 0 and math.isfinite(base)):
                    x[k] = arr[-1]                       # sin perfil: se repite lo último conocido
                    continue
                ratio = lvl
                prev = store.get(hour_index(t) - 24)     # ayer a esta hora (solo si es de esta misma semana)
                if prev is not None and prev[1] > 0 and now - hour_index(t) + 24 <= 30:
                    ratio = self.yesterday_weight * prev[0] / prev[1] + (1.0 - self.yesterday_weight) * lvl
                x[k] = base * ratio
            out.append(np.maximum(x, 0.0))
        return out[0], out[1]
