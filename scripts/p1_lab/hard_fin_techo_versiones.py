"""Revisor del TECHO, 4.ª parte: ¿cuánto se separa de la v10, por pura suerte de la máscara, un agente legítimo de verdad?

Con las mismas 420 máscaras de hard_fin_techo_mascaras.py, el cociente nota(vX)/nota(v10) en las horas de la máscara
para nuestras otras versiones (v6, v9, v12, v14: agentes legítimos con trayectorias distintas), y para una mezcla
v10 + a·(óptimo − v10). Sirve para saber qué parte del camino al óptimo haría falta, además de suerte, para un +16 %.

    python scripts/p1_lab/hard_fin_techo_versiones.py
"""
import pickle
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
REPO = Path(__file__).resolve().parents[2]
for extra in (str(REPO / "src"), str(REPO / "scripts"), str(REPO / "scripts" / "p1_lab")):
    if extra not in sys.path:
        sys.path.insert(0, extra)
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import p1_hard as B  # noqa: E402

OUT = REPO / "results" / "p1_hard"
full = B.hard_table()
rows = []
for win in ("val", "dev", "1-7"):
    df = B.split_frame(full, win).reset_index(drop=True)
    n = len(df)
    ts = pd.DatetimeIndex(df.timestamp)
    key = (ts.year * 12 + ts.month).to_numpy()
    wk = np.concatenate([[0], np.cumsum(key[1:] != key[:-1])])
    start = pd.Series(ts).groupby(wk).transform("min")
    hw = ((pd.Series(ts) - start).dt.total_seconds() // 3600).to_numpy(int)
    day = hw // 24
    nw = wk.max() + 1
    cal = pickle.load(open(REPO / "results" / "hourly" / f"calcal_{win}.pkl", "rb"))
    b_co2, b_eur = np.asarray(cal["base_co2"], float), np.asarray(cal["base_eur"], float)
    rng = np.random.default_rng(20261115)
    M = {}
    M["mitad contigua|1.ª (h 0-83)"] = hw < 84
    M["mitad contigua|2.ª (h 84-167)"] = hw >= 84
    for s in (24, 42, 48, 72, 96, 120, 126, 144):
        M[f"mitad contigua desplazada|empieza h {s}"] = ((hw - s) % 168) < 84
    for blk in (1, 3, 6, 12, 24):
        name = {1: "horas alternas", 24: "días alternos"}.get(blk, f"bloques de {blk} h")
        M[f"{name}|pares"] = (hw // blk) % 2 == 0
        M[f"{name}|impares"] = (hw // blk) % 2 == 1
    for i in range(200):
        m = np.zeros(n, bool)
        for w in range(nw):
            idx = np.flatnonzero(wk == w)
            m[rng.choice(idx, size=len(idx) // 2, replace=False)] = True
        M[f"azar por horas|{i}"] = m
    for i in range(200):
        m = np.zeros(n, bool)
        for w in range(nw):
            k = 3 + (rng.random() < 0.5)
            pick = rng.choice(7, size=k, replace=False)
            m |= (wk == w) & np.isin(day, pick)
        M[f"azar por días enteros|{i}"] = m

    def nota(v, m):
        return 0.7 * 100 * np.asarray(cal["out"][v]["co2"], float)[m].sum() / b_co2[m].sum() + 0.3 * 100 * np.asarray(cal["out"][v]["eur"], float)[m].sum() / b_eur[m].sum()

    ALL = np.ones(n, bool)
    for name, m in M.items():
        fam, var = name.split("|")
        r = {"ventana": win, "familia": fam, "mascara": var}
        for v in ("v6", "v9", "v12", "v14"):
            r[v] = nota(v, m) / nota("v10", m)
            r[v + "_todo"] = nota(v, ALL) / nota("v10", ALL)
        rows.append(r)
R = pd.DataFrame(rows)
R.to_csv(OUT / "fin_techo_versiones.csv", index=False)
print("cociente nota(vX)/nota(v10) en la máscara, tres ventanas juntas (1.260 máscaras)")
for v in ("v6", "v9", "v12", "v14"):
    print(f"  {v:4s} episodio completo x{R[v + '_todo'].min():.4f}-{R[v + '_todo'].max():.4f} | en las máscaras: min {R[v].min():.3f} p1 {R[v].quantile(.01):.3f} "
          f"med {R[v].median():.3f} p99 {R[v].quantile(.99):.3f} max {R[v].max():.3f} | >=1,16: {(R[v] >= 1.16).sum()} | >=1,05: {(R[v] >= 1.05).sum()}")
for fam, g in R.groupby("familia", sort=False):
    print(f"  {fam:28s} v14/v10 {g.v14.min():.3f}-{g.v14.max():.3f} | v12/v10 {g.v12.min():.3f}-{g.v12.max():.3f} | v6/v10 {g.v6.min():.3f}-{g.v6.max():.3f}")
A = pd.concat([pd.read_csv(OUT / f"fin_techo_mascaras_A_{w}.csv") for w in ("val", "dev", "1-7")])
print("\nmezcla v10 + a·(óptimo − v10): máscaras (de 1.260) que llegan a 1,16")
for a in (0.1, 0.2, 0.3, 0.5, 0.55, 0.6, 0.7, 0.8, 1.0):
    c = 1 + a * (A.coc - 1)
    print(f"  a = {a:.2f}: {int((c >= 1.16).sum()):3d} ({100 * (c >= 1.16).mean():.2f} %)  máx {c.max():.3f}")
