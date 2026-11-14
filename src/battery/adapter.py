"""Único punto que conoce el formato OFICIAL de la observación y de la acción.

Owner: INTEGRADOR.

Claves confirmadas con la plantilla oficial (starter_kit/agent.py):
    timestamp (pd.Timestamp), hour (0..23), day_of_week (0 = lunes), soc_kwh, soc_pct,
    preu_actual (€/kWh), co2_actual (kg CO2/kWh), preus_properes_24h (24 valores),
    co2_properes_24h (24 valores), noves_dades_5min (sensores de la última hora)
    Acción: float en kW, > 0 carga (hasta +500), < 0 descarga (hasta -500).

Todavía por VERIFICAR con starter_kit/environment.py:
    - Si `preus_properes_24h[0]` es la hora siguiente (t+1) o la actual (t).
    - El formato de `noves_dades_5min` (DataFrame, lista de dicts...) y sus columnas
      de demanda y solar. Mientras no se sepa, `recent_load_pv` prueba varias opciones
      y, si no reconoce nada, devuelve NaN (la previsión sigue con su perfil).
Al comprobarlo: se cambia aquí, se actualiza docs/reto.md y tests/test_adapter.py sigue en verde.
"""
import math
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .obs import Obs
from .params import FORECAST_HOURS

OBS_KEYS = {
    "timestamp": "timestamp",
    "hour": "hour",
    "weekday": "day_of_week",
    "soc": "soc_kwh",
    "price": "preu_actual",
    "co2": "co2_actual",
    "price_forecast": "preus_properes_24h",
    "co2_forecast": "co2_properes_24h",
    "recent": "noves_dades_5min",
}
FORECAST_STARTS_NEXT_HOUR = True   # VERIFICAR

# Columnas de noves_dades_5min. VERIFICAR con environment.py y tutorial.ipynb.
RECENT_LOAD_COLS = ["demanda_kw", "demand_kw", "load_kw", "consum_kw", "demanda"]
RECENT_PV_COLS = ["solar_kw", "pv_kw", "fotovoltaica_kw", "generacio_kw", "solar"]
RECENT_METER_COL = "contador"       # si solo viene el contador: demanda = -contador (VERIFICAR)
RECENT_INVERTER_PREFIX = "inversor"  # solar = suma de las columnas inversor*


def _to_float(x: Any) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return v if math.isfinite(v) else float("nan")


def _col_mean(df: pd.DataFrame, names) -> float:
    for n in names:
        if n in df.columns:
            return _to_float(pd.to_numeric(df[n], errors="coerce").mean())
    return float("nan")


def recent_load_pv(recent: Any) -> tuple:
    """Demanda y solar medias (kW) de la última hora a partir de noves_dades_5min."""
    try:
        if recent is None:
            return float("nan"), float("nan")
        df = recent if isinstance(recent, pd.DataFrame) else pd.DataFrame(recent)
        if df.empty:
            return float("nan"), float("nan")
        load = _col_mean(df, RECENT_LOAD_COLS)
        if not math.isfinite(load) and RECENT_METER_COL in df.columns:
            load = -_col_mean(df, [RECENT_METER_COL])
        pv = _col_mean(df, RECENT_PV_COLS)
        inv = [c for c in df.columns if str(c).lower().startswith(RECENT_INVERTER_PREFIX)]
        if not math.isfinite(pv) and inv:
            pv = _to_float(df[inv].apply(pd.to_numeric, errors="coerce").sum(axis=1).mean())
        return load, pv
    except Exception:
        return float("nan"), float("nan")


def from_official(raw: Mapping[str, Any]) -> Obs:
    """Diccionario oficial -> Obs interna."""
    k = OBS_KEYS
    price_now = _to_float(raw[k["price"]])
    co2_now = _to_float(raw[k["co2"]])
    price_fc = np.asarray(raw[k["price_forecast"]], dtype=float)
    co2_fc = np.asarray(raw[k["co2_forecast"]], dtype=float)
    if FORECAST_STARTS_NEXT_HOUR:
        price = np.concatenate(([price_now], price_fc))
        co2 = np.concatenate(([co2_now], co2_fc))
    else:
        price, co2 = price_fc.copy(), co2_fc.copy()
        price[0], co2[0] = price_now, co2_now
    load_prev, pv_prev = recent_load_pv(raw.get(k["recent"]))
    return Obs(
        hour=int(raw[k["hour"]]),
        weekday=int(raw[k["weekday"]]),
        soc_kwh=_to_float(raw[k["soc"]]),
        price=price,
        co2=co2,
        load_prev_kw=load_prev,
        pv_prev_kw=pv_prev,
        timestamp=raw.get(k["timestamp"]),
    )


def make_official_obs(timestamp, soc_kwh: float, price: np.ndarray, co2: np.ndarray,
                      load_prev_kw: float, pv_prev_kw: float,
                      capacity_kwh: float = 2000.0) -> dict:
    """Construye el diccionario oficial (lo usa el simulador local, no el agente).

    `price` y `co2` tienen longitud 1 + FORECAST_HOURS y empiezan en la hora actual.
    `noves_dades_5min` se imita con 12 filas iguales a la media de la hora anterior.
    """
    k = OBS_KEYS
    ts = pd.Timestamp(timestamp)
    if FORECAST_STARTS_NEXT_HOUR:
        price_fc, co2_fc = price[1:FORECAST_HOURS + 1], co2[1:FORECAST_HOURS + 1]
    else:
        price_fc, co2_fc = price[:FORECAST_HOURS], co2[:FORECAST_HOURS]
    if math.isfinite(load_prev_kw) and math.isfinite(pv_prev_kw):
        recent = pd.DataFrame({RECENT_LOAD_COLS[0]: [float(load_prev_kw)] * 12,
                               RECENT_PV_COLS[0]: [float(pv_prev_kw)] * 12})
    else:
        recent = pd.DataFrame(columns=[RECENT_LOAD_COLS[0], RECENT_PV_COLS[0]])
    return {
        k["timestamp"]: ts,
        k["hour"]: int(ts.hour),
        k["weekday"]: int(ts.weekday()),
        k["soc"]: float(soc_kwh),
        "soc_pct": float(soc_kwh) / capacity_kwh,
        k["price"]: float(price[0]),
        k["co2"]: float(co2[0]),
        k["price_forecast"]: [float(v) for v in price_fc],
        k["co2_forecast"]: [float(v) for v in co2_fc],
        k["recent"]: recent,
    }
