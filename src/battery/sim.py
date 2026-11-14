"""Simulador local que imita al evaluador oficial, y cálculo del score. NO se empaqueta.

Owner: P3 (validación). Primera tarea: calibrarlo contra starter_kit/environment.py
(mismo agente y mismos datos -> mismo score) y apuntar las diferencias en docs/reto.md.

Hora a hora:
    obs oficial (adapter.make_official_obs) -> agent.act(obs) -> potencia pedida (kW)
    infracción si no cabe -> se cuenta y se recorta (VERIFICAR qué hace el oficial)
    red = demanda - solar + acción
    red > 0: compramos (precio, CO2)    red < 0: vendemos a EXPORT_PRICE, sin CO2
Score respecto a no usar la batería:
    ΔCO2% = 100·(CO2_ref - CO2)/CO2_ref, ΔCoste% igual con el coste
    Score = max(0, 0,70·ΔCO2% + 0,30·ΔCoste% - W_INFRACTION·infracciones)

CONTRATO con el análisis: log hora a hora con columnas
    t, timestamp, hour, weekday, load_kw, pv_kw, price_eur_kwh, co2_kg_kwh,
    action_req_kw, action_kw, infraction, soc_kwh (al final de la hora),
    grid_kw, import_kw, export_kw, cost_eur, co2_kg
"""
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .adapter import make_official_obs
from .params import (DEFAULT_PARAMS, FORECAST_HOURS, W_CO2, W_COST, W_INFRACTION,
                     BatteryParams)
from .safety import clip_action, is_infraction, soc_after

LOG_COLUMNS = ["t", "timestamp", "hour", "weekday", "load_kw", "pv_kw", "price_eur_kwh",
               "co2_kg_kwh", "action_req_kw", "action_kw", "infraction", "soc_kwh",
               "grid_kw", "import_kw", "export_kw", "cost_eur", "co2_kg"]


@dataclass
class SimResult:
    log: pd.DataFrame
    totals: dict


def _totals(grid: np.ndarray, price: np.ndarray, co2: np.ndarray, p: BatteryParams) -> dict:
    imp = np.clip(grid, 0, None)
    exp = np.clip(-grid, 0, None)
    return {
        "co2_kg": float((imp * co2).sum()),
        "cost_eur": float((imp * price).sum() - (exp * p.export_price_eur_kwh).sum()),
        "import_kwh": float(imp.sum()),
        "export_kwh": float(exp.sum()),
    }


def baseline_totals(df: pd.DataFrame, p: BatteryParams = DEFAULT_PARAMS) -> dict:
    """Totales sin batería: la referencia del score."""
    grid = (df["load_kw"] - df["pv_kw"]).to_numpy()
    return _totals(grid, df["price_eur_kwh"].to_numpy(), df["co2_kg_kwh"].to_numpy(), p)


def simulate(agent, df: pd.DataFrame, p: BatteryParams = DEFAULT_PARAMS,
             fc_noise: float = 0.0, seed: int = 0, init_s: float = 0.0) -> SimResult:
    """Ejecuta `agent` sobre todas las filas de `df` (un episodio sin reinicios).

    `fc_noise` añade ruido a las previsiones de precio y CO2 (crece con la antelación)
    para medir robustez si las previsiones oficiales no son exactas.
    `init_s`: lo que tardó en crearse el agente (cuenta para los 60 s).
    """
    rng = np.random.default_rng(seed)
    load = df["load_kw"].to_numpy(float)
    pv = df["pv_kw"].to_numpy(float)
    price = df["price_eur_kwh"].to_numpy(float)
    co2 = df["co2_kg_kwh"].to_numpy(float)
    ts = pd.DatetimeIndex(df["timestamp"])
    hours, weekdays = ts.hour.to_numpy(), ts.weekday.to_numpy()
    last = len(df) - 1
    lead = np.arange(FORECAST_HOURS + 1)
    noise_scale = fc_noise * np.sqrt(lead / FORECAST_HOURS)

    soc = p.soc_init_kwh
    rows = []
    agent_s = init_s
    for t in range(len(df)):
        idx = np.minimum(t + lead, last)
        price_path, co2_path = price[idx].copy(), co2[idx].copy()
        if fc_noise > 0:
            price_path *= 1 + noise_scale * rng.standard_normal(len(lead))
            co2_path *= 1 + noise_scale * rng.standard_normal(len(lead))
        prev_load = load[t - 1] if t > 0 else float("nan")
        prev_pv = pv[t - 1] if t > 0 else float("nan")
        obs = make_official_obs(ts[t], soc, price_path, co2_path, prev_load, prev_pv,
                                p.capacity_kwh)

        t0 = time.perf_counter()
        raw = agent.act(obs)
        agent_s += time.perf_counter() - t0

        try:
            a_req = float(raw)
        except (TypeError, ValueError):
            a_req = float("nan")
        infr = is_infraction(a_req, soc, p)
        a = clip_action(a_req, soc, p)
        soc = soc_after(soc, a, p)
        grid = load[t] - pv[t] + a
        imp, exp = max(grid, 0.0), max(-grid, 0.0)
        rows.append((t, ts[t], hours[t], weekdays[t], load[t], pv[t], price[t], co2[t],
                     a_req, a, infr, soc, grid, imp, exp,
                     imp * price[t] - exp * p.export_price_eur_kwh, imp * co2[t]))

    log = pd.DataFrame(rows, columns=LOG_COLUMNS)
    totals = {
        "co2_kg": float(log["co2_kg"].sum()),
        "cost_eur": float(log["cost_eur"].sum()),
        "import_kwh": float(log["import_kw"].sum()),
        "export_kwh": float(log["export_kw"].sum()),
        "infractions": int(log["infraction"].sum()),
        "final_soc_kwh": float(soc),
        "runtime_s": float(agent_s),
        "n_steps": int(len(df)),
    }
    return SimResult(log=log, totals=totals)


def score(totals: dict, base: dict) -> dict:
    d_co2 = 100.0 * (base["co2_kg"] - totals["co2_kg"]) / base["co2_kg"]
    d_cost = 100.0 * (base["cost_eur"] - totals["cost_eur"]) / abs(base["cost_eur"])
    n_inf = int(totals.get("infractions", 0))
    raw = W_CO2 * d_co2 + W_COST * d_cost - W_INFRACTION * n_inf
    return {"score": max(0.0, raw), "score_raw": raw, "d_co2_pct": d_co2,
            "d_cost_pct": d_cost, "infractions": n_inf}
