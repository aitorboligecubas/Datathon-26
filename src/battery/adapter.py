"""Único punto que conoce el formato OFICIAL de la observación y de la acción.

Owner: INTEGRADOR.

Formato verificado en oficial/starter_kit/environment.py (CampusBatteryEnv._get_obs):
    timestamp           pd.Timestamp (check_submission.py lo pasa como str)
    hour, day_of_week   int (0 = lunes)
    soc_kwh, soc_pct, soc_percent
    preu_actual         €/kWh de la hora actual
    co2_actual          kg CO2/kWh de la hora actual
    preus_properes_24h  df[t : t+24] -> EMPIEZA EN LA HORA ACTUAL ([0] == preu_actual);
                        al final de los datos trae menos de 24 valores
    co2_properes_24h    igual
    noves_dades_5min    {"ultim_consum_kw": demanda de t-1, "ultima_solar_kw": solar de t-1}
                        (en t = 0 da los de la propia hora t)
Acción: float en kW, > 0 carga, < 0 descarga. El entorno recorta a ±500 y a la capacidad,
y cuenta una infracción por cada recorte.
"""
import math
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .obs import Obs

FORECAST_LEN = 24


def _to_float(x: Any) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return v if math.isfinite(v) else float("nan")


def _to_timestamp(x: Any):
    try:
        return pd.Timestamp(x)
    except (TypeError, ValueError):
        return None


def _to_series(x: Any, fallback: float) -> np.ndarray:
    """Lista, tupla, array de numpy o Series de pandas -> array 1-D; vacío o None -> [fallback].

    El simulador local pasa listas, pero el servidor podría pasar arrays: con `x or [...]` un array
    lanzaría ValueError y el agente se quedaría parado todo el test sin avisar.
    """
    if x is None:
        return np.asarray([fallback], dtype=float)
    arr = np.asarray(x, dtype=float).ravel()
    return arr if arr.size else np.asarray([fallback], dtype=float)


def from_official(raw: Mapping[str, Any]) -> Obs:
    """Diccionario oficial -> Obs interna."""
    price_now = _to_float(raw["preu_actual"])
    co2_now = _to_float(raw["co2_actual"])
    price = _to_series(raw.get("preus_properes_24h"), price_now)
    co2 = _to_series(raw.get("co2_properes_24h"), co2_now)
    n = min(len(price), len(co2))
    price, co2 = price[:n].copy(), co2[:n].copy()
    price[0], co2[0] = price_now, co2_now
    recent = raw.get("noves_dades_5min")
    if not isinstance(recent, Mapping):   # None, o un formato inesperado: seguimos sin esas lecturas
        recent = {}
    return Obs(
        hour=int(raw["hour"]),
        weekday=int(raw["day_of_week"]),
        soc_kwh=_to_float(raw["soc_kwh"]),
        price=price,
        co2=co2,
        load_prev_kw=_to_float(recent.get("ultim_consum_kw")),
        pv_prev_kw=_to_float(recent.get("ultima_solar_kw")),
        timestamp=_to_timestamp(raw.get("timestamp")),
    )


def make_official_obs(timestamp, soc_kwh: float, price: np.ndarray, co2: np.ndarray,
                      load_prev_kw: float, pv_prev_kw: float,
                      capacity_kwh: float = 2000.0) -> dict:
    """Construye el diccionario oficial igual que environment.py (lo usa el simulador local).

    `price` y `co2` empiezan en la hora actual (como mucho 24 valores).
    """
    ts = pd.Timestamp(timestamp)
    return {
        "timestamp": ts,
        "hour": int(ts.hour),
        "day_of_week": int(ts.dayofweek),
        "soc_kwh": float(soc_kwh),
        "soc_pct": float(soc_kwh / capacity_kwh),
        "soc_percent": float(soc_kwh / capacity_kwh * 100),
        "preu_actual": float(price[0]),
        "co2_actual": float(co2[0]),
        "preus_properes_24h": [float(v) for v in price[:FORECAST_LEN]],
        "co2_properes_24h": [float(v) for v in co2[:FORECAST_LEN]],
        "noves_dades_5min": {
            "ultim_consum_kw": float(load_prev_kw),
            "ultima_solar_kw": float(pv_prev_kw),
        },
    }
