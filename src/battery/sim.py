"""Simulador local que replica oficial/starter_kit/environment.py, y cálculo del score. NO se empaqueta.

Owner: P3 (validación). Debe dar el MISMO resultado que el oficial
(tests/test_sim.py lo comprueba si oficial/ existe). Es más rápido y deja un log hora a hora.

Igual que CampusBatteryEnv:
    obs: precios y CO2 de df[t : t+24] (empiezan en la hora actual), demanda y solar de t-1
         (en t = 0, las de t)
    acción: se recorta a ±500 kW (+1 infracción si se recorta) y a la capacidad
            (+1 infracción si se recorta)
    red = demanda - solar + acción_aplicada; compra si > 0, si < 0 se vierte (precio 0, sin CO2)
    referencia sin batería: compra = max(demanda - solar, 0)
    Score = max(0, 0,70·ΔCO2% + 0,30·ΔCoste% - 0,20·infracciones)

CONTRATO con el análisis: log hora a hora con columnas LOG_COLUMNS.
"""
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .adapter import make_official_obs
from .params import (DEFAULT_PARAMS, FORECAST_HOURS, W_CO2, W_COST, W_INFRACTION,
                     BatteryParams)

LOG_COLUMNS = ["t", "timestamp", "hour", "weekday", "load_kw", "pv_kw", "price_eur_kwh",
               "co2_kg_kwh", "action_req_kw", "action_kw", "infractions", "soc_kwh",
               "grid_kw", "import_kw", "export_kw", "cost_eur", "co2_kg"]


@dataclass
class SimResult:
    log: pd.DataFrame
    totals: dict


def baseline_totals(df: pd.DataFrame, p: BatteryParams = DEFAULT_PARAMS) -> dict:
    """Totales sin batería: la referencia del score (como evaluate_results)."""
    base = np.maximum((df["load_kw"] - df["pv_kw"]).to_numpy(), 0.0)
    return {
        "co2_kg": float((base * df["co2_kg_kwh"].to_numpy()).sum()),
        "cost_eur": float((base * df["price_eur_kwh"].to_numpy()).sum()),
        "import_kwh": float(base.sum()),
    }


def apply_action(soc: float, p_req: float, p: BatteryParams = DEFAULT_PARAMS) -> tuple:
    """Física de CampusBatteryEnv.step: devuelve (acción aplicada, nueva carga, infracciones)."""
    infr = 0
    pw = float(np.clip(p_req, -p.max_discharge_kw, p.max_charge_kw))
    if pw != p_req:
        infr += 1
    if pw > 0:
        max_c = (p.capacity_kwh - soc) / p.eta_charge
        applied = min(pw, max(0.0, max_c))
        if applied < pw:
            infr += 1
        soc = soc + applied * p.eta_charge
    elif pw < 0:
        max_d = soc * p.eta_discharge
        applied = -min(-pw, max(0.0, max_d))
        if applied > pw:
            infr += 1
        soc = soc + applied / p.eta_discharge
    else:
        applied = 0.0
    if soc < -1e-6 or soc > p.capacity_kwh + 1e-6:
        infr += 1
    return applied, float(np.clip(soc, 0.0, p.capacity_kwh)), infr


def simulate(agent, df: pd.DataFrame, p: BatteryParams = DEFAULT_PARAMS,
             fc_noise: float = 0.0, seed: int = 0, init_s: float = 0.0) -> SimResult:
    """Ejecuta `agent` sobre todas las filas de `df` (un episodio sin reinicios).

    `fc_noise` añade ruido a las previsiones de precio y CO2 de las horas futuras (no a la
    actual) para medir robustez. Por defecto 0, como el oficial (previsiones exactas).
    `init_s`: lo que tardó en crearse el agente (cuenta para los 60 s).
    """
    rng = np.random.default_rng(seed)
    load = df["load_kw"].to_numpy(float)
    pv = df["pv_kw"].to_numpy(float)
    price = df["price_eur_kwh"].to_numpy(float)
    co2 = df["co2_kg_kwh"].to_numpy(float)
    ts = pd.DatetimeIndex(df["timestamp"])
    n = len(df)
    lead = np.arange(FORECAST_HOURS)
    noise_scale = fc_noise * np.sqrt(lead / FORECAST_HOURS)

    soc = p.soc_init_kwh
    rows = []
    agent_s = init_s
    for t in range(n):
        end = min(t + FORECAST_HOURS, n)
        price_path, co2_path = price[t:end].copy(), co2[t:end].copy()
        if fc_noise > 0:
            k = end - t
            price_path *= 1 + noise_scale[:k] * rng.standard_normal(k)
            co2_path *= 1 + noise_scale[:k] * rng.standard_normal(k)
        prev = t - 1 if t > 0 else t
        obs = make_official_obs(ts[t], soc, price_path, co2_path, load[prev], pv[prev],
                                p.capacity_kwh)

        t0 = time.perf_counter()
        raw = agent.act(obs)
        agent_s += time.perf_counter() - t0

        a_req = float(raw)
        a, soc, infr = apply_action(soc, a_req, p)
        grid = load[t] - pv[t] + a
        imp, exp = max(grid, 0.0), max(-grid, 0.0)
        rows.append((t, ts[t], ts[t].hour, ts[t].dayofweek, load[t], pv[t], price[t], co2[t],
                     a_req, a, infr, soc, grid, imp, exp,
                     imp * price[t] - exp * p.export_price_eur_kwh, imp * co2[t]))

    log = pd.DataFrame(rows, columns=LOG_COLUMNS)
    totals = {
        "co2_kg": float(log["co2_kg"].sum()),
        "cost_eur": float(log["cost_eur"].sum()),
        "import_kwh": float(log["import_kw"].sum()),
        "export_kwh": float(log["export_kw"].sum()),
        "infractions": int(log["infractions"].sum()),
        "final_soc_kwh": float(soc),
        "runtime_s": float(agent_s),
        "n_steps": int(n),
    }
    return SimResult(log=log, totals=totals)


def score(totals: dict, base: dict) -> dict:
    d_co2 = 100.0 * (base["co2_kg"] - totals["co2_kg"]) / base["co2_kg"]
    d_cost = 100.0 * (base["cost_eur"] - totals["cost_eur"]) / base["cost_eur"]
    n_inf = int(totals.get("infractions", 0))
    raw = W_CO2 * d_co2 + W_COST * d_cost - W_INFRACTION * n_inf
    return {"score": max(0.0, raw), "score_raw": raw, "d_co2_pct": d_co2,
            "d_cost_pct": d_cost, "infractions": n_inf}


def to_env_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Nuestro formato -> el que espera CampusBatteryEnv (para calibrar contra el oficial)."""
    return df.rename(columns={"timestamp": "Fecha", "price_eur_kwh": "precio_eur_per_kwh",
                              "co2_kg_kwh": "co2_kg_per_kwh"})[
        ["Fecha", "load_kw", "pv_kw", "precio_eur_per_kwh", "co2_kg_per_kwh"]]
