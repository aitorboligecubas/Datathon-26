"""Piezas comunes de los ataques de robustez al agente del HARD MODE. NO se empaqueta.

Owner: P1. Lo usan scripts/p1_lab/hard_ataque_*.py. No toca src/: solo lo importa.

Qué aporta:
- episodio_test(): un episodio con el CALENDARIO DEL TEST (los últimos 7 días de cada mes, uno detrás
  de otro). El banco (scripts/p1_hard.py) evalúa en fechas del train (días 8-14 o 17-23), donde el agente
  nunca cruza un fin de mes: su lógica de calendario no se ejecuta nunca ahí. Aquí sí.
  Los datos de cada semana son las 168 h del train de 14 días antes (mismo día de la semana; 21 días en
  agosto, porque el train de agosto acaba el día 16). Noviembre no tiene contador en el train: se copia
  el consumo y la solar de octubre ("copia"), se deja a cero ("cero") o se quita la semana ("omitir").
- priors(): tablas del agente ajustadas SIN las horas de origen del episodio (como hace el banco).
- simular(): el simulador del banco con un gancho para deformar la observación y contar fallos.
"""
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import p1_hard  # noqa: E402
from battery.hard import HARD_PARAMS  # noqa: E402
from battery.sim import apply_action, baseline_totals, score  # noqa: E402

WEEK = 168
TEST_STARTS = ["2025-09-24", "2025-10-25", "2025-11-24", "2025-12-25", "2026-01-25", "2026-02-22",
               "2026-03-25", "2026-04-24", "2026-05-25", "2026-06-24", "2026-07-25", "2026-08-25"]
NOV = 2
_CACHE = {}


def tabla() -> pd.DataFrame:
    if "tabla" not in _CACHE:
        _CACHE["tabla"] = p1_hard.hard_table()
    return _CACHE["tabla"]


def episodio_test(nov: str = "copia", semanas=None) -> tuple:
    """(episodio, horas de origen). `semanas`: índices de TEST_STARTS que se quieren (por defecto, todas)."""
    full = tabla().set_index("timestamp")
    market = p1_hard.market_frame()
    weeks, origen = {}, []
    for i, start in enumerate(TEST_STARTS):
        hours = pd.date_range(start, periods=WEEK, freq="h")
        # Hora a hora: la de 14 días antes; si falta en el train, la de 21 o la de 7 (pasa en agosto).
        src = []
        for h in hours:
            cands = [h - pd.Timedelta(days=s) for s in (14, 21, 7)]
            src.append(next((c for c in cands if c in full.index), None))
        if all(s is not None for s in src):
            w = full.loc[src].reset_index(drop=True).copy()
            w.insert(0, "timestamp", hours)
            weeks[i] = w
            origen.extend(src)
            continue
        src = hours - pd.Timedelta(days=14)
        if i == NOV and src.isin(market.index).all():      # noviembre: solo hay precio y CO2
            weeks[i] = pd.DataFrame({"timestamp": hours, "load_kw": 0.0, "pv_kw": 0.0,
                                     "price_eur_kwh": market.price.reindex(src).to_numpy(),
                                     "co2_kg_kwh": market.co2.reindex(src).to_numpy()})
            origen.extend(src)
    if NOV in weeks and (NOV - 1) in weeks:
        if nov == "copia":
            for c in weeks[NOV - 1].columns:
                if c not in ("timestamp", "price_eur_kwh", "co2_kg_kwh"):
                    weeks[NOV][c] = weeks[NOV - 1][c].to_numpy()
        elif nov == "cero":
            for c in p1_hard.METEO_COLS.values():
                weeks[NOV][c] = weeks[NOV - 1][c].to_numpy()
        elif nov == "omitir":
            del weeks[NOV]
    keep = sorted(weeks) if semanas is None else [i for i in semanas if i in weeks]
    df = pd.concat([weeks[i] for i in keep], ignore_index=True)
    return df, set(origen)


def priors(origen: set) -> tuple:
    """(prior de mercado, prior de solar) ajustados sin las horas de origen del episodio."""
    key = ("priors", len(origen), min(origen), max(origen))
    if key not in _CACHE:
        full = tabla()
        fit_df = full[~full.timestamp.isin(origen)]
        _CACHE[key] = (p1_hard.fit_market(origen, fit_df), p1_hard.fit_solar(fit_df))
    return _CACHE[key]


class Envoltorio:
    """Deforma la observación antes de pasarla al agente y apunta lo que el agente hace mal."""

    def __init__(self, agent, fn=None):
        self.agent, self.fn = agent, fn
        self.t = 0
        self.excepciones, self.no_finitas, self.ceros = 0, 0, 0
        self.primer_error = ""
        self.ms = []

    def act(self, obs):
        o = obs
        if self.fn is not None:
            o = self.fn(dict(obs, noves_dades_5min=dict(obs["noves_dades_5min"])), self.t)
        self.t += 1
        t0 = time.perf_counter()
        try:
            a = self.agent.act(o)
            af = float(a)
        except Exception as e:      # el evaluador se pararía aquí
            self.excepciones += 1
            if not self.primer_error:
                self.primer_error = f"{type(e).__name__}: {e}"[:120]
            af = 0.0
        self.ms.append(1000 * (time.perf_counter() - t0))
        if not math.isfinite(af):
            self.no_finitas += 1
            af = 0.0
        if af == 0.0:
            self.ceros += 1
        return af


def simular(agent, df: pd.DataFrame, fn=None, p=HARD_PARAMS, known: int = 3) -> dict:
    """Simula `agent` en `df` con la física `p`. `fn(obs, t) -> obs` deforma cada observación."""
    env = Envoltorio(agent, fn)
    totals, log = p1_hard.simulate_hard(env, df, known=known, p=p)
    sc = score(totals, baseline_totals(df))
    ex = log[log.export_kw > 1e-6]
    return {"score": sc["score_raw"], "infr": int(totals["infractions"]), "excepciones": env.excepciones,
            "no_finitas": env.no_finitas, "pct_cero": 100.0 * env.ceros / max(len(df), 1),
            "vert_descarga": float(ex[ex.action_kw < -1e-6].export_kw.sum()),
            "vert_solar": float(ex[ex.action_kw >= -1e-6].export_kw.sum()),
            "soc_final": float(totals["final_soc_kwh"]), "ms_medio": float(np.mean(env.ms)),
            "ms_max": float(np.max(env.ms)), "s_total": float(np.sum(env.ms)) / 1000.0,
            "error": env.primer_error, "log": log, "ms": env.ms}


def agente(prior: dict, solar: dict, **cfg):
    """El agente actual de src/ con las tablas dadas (el mismo constructor que usa el banco)."""
    return p1_hard.hard_agent(prior, solar, **cfg)


def pesos(df: pd.DataFrame) -> tuple:
    from battery.optimizer import score_weights
    b = baseline_totals(df)
    return score_weights(b["co2_kg"] / len(df), b["cost_eur"] / len(df))


__all__ = ["HARD_PARAMS", "NOV", "TEST_STARTS", "WEEK", "agente", "apply_action", "episodio_test", "pesos",
           "priors", "simular", "tabla"]
