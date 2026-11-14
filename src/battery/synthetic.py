"""Datos sintéticos con la forma del problema, para trabajar antes de tener los oficiales.

Owner: P2 (datos y análisis). No los uséis para sacar conclusiones: solo sirven para que todo el
circuito (previsión -> LP -> simulador -> score) funcione desde el minuto uno.
Patrones imitados: campus con más consumo laborable de 8 a 20 h, solar con
estación y nubes, PVPC con picos de mañana y noche, CO2 alto por la noche
(ciclos combinados) y bajo a mediodía (solar del sistema).
"""
import numpy as np
import pandas as pd


def make_synthetic(start: str = "2025-01-01", days: int = 365, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ts = pd.date_range(start, periods=days * 24, freq="h")
    hour = ts.hour.to_numpy()
    wd = ts.weekday.to_numpy()
    doy = ts.dayofyear.to_numpy()
    day_idx = np.arange(len(ts)) // 24
    season = np.cos(2 * np.pi * (doy - 172) / 365)  # 1 en verano, -1 en invierno

    # Demanda del campus (kWh por hora)
    workday = wd < 5
    office = ((hour >= 8) & (hour < 20)).astype(float)
    demand = 260 + workday * office * 520 + (~workday) * office * 60
    demand = demand * np.where(ts.month.to_numpy() == 8, 0.6, 1.0)
    demand = demand * (1 + 0.08 * np.clip(season, 0, None))  # aire acondicionado en verano
    demand = demand * (1 + 0.05 * rng.standard_normal(len(ts)))

    # Solar (kWh por hora): forma de campana con duración del día según estación
    half_day = 6.0 + 1.8 * season
    x = (hour + 0.5 - 13.0) / half_day
    clear = np.clip(np.cos(np.pi / 2 * x), 0, None) * (np.abs(x) < 1)
    peak = 520 + 180 * season
    clouds_day = rng.beta(4, 1.6, size=days)[day_idx]
    clouds_hour = np.clip(1 + 0.15 * rng.standard_normal(len(ts)), 0.3, 1.2)
    solar = peak * clear * clouds_day * clouds_hour

    # Precio PVPC (€/kWh)
    level = rng.lognormal(0, 0.2, size=days)[day_idx]
    shape = (0.09
             + 0.04 * ((hour >= 8) & (hour < 11))
             + 0.08 * ((hour >= 19) & (hour < 23))
             - 0.03 * ((hour >= 12) & (hour < 17)) * (1 + season) / 2)
    price = np.clip(shape * level * (1 + 0.05 * rng.standard_normal(len(ts))), 0.02, None)

    # Intensidad de CO2 del mix (kg/kWh al final)
    wind = rng.uniform(0, 70, size=days)[day_idx]
    sun_system = 70 * clear * (0.6 + 0.4 * season)
    ccgt = 90 * ((hour >= 19) | (hour < 1))
    co2 = 170 + ccgt - sun_system - wind + 10 * rng.standard_normal(len(ts))
    co2 = np.clip(co2, 30, None)

    return pd.DataFrame({
        "timestamp": ts,
        "load_kw": demand.round(2),
        "pv_kw": solar.round(2),
        "price_eur_kwh": price.round(5),
        "co2_kg_kwh": (co2 / 1000).round(4),
    })
