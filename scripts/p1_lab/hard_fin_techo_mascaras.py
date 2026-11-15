"""Revisor del TECHO: ¿puede un control legítimo sacar un 16 % más que la v10 en "el 50 % de cada semana"?

Para cada familia de máscara (mitades contiguas, bloques alternos de 1, 3, 6, 12 y 24 h, 200 al azar por horas y 200
por días enteros) se calcula, sobre las horas de la máscara y con el calendario real del episodio:

  A) nota(óptimo con todo el futuro) / nota(v10)      -> el techo de un control que NO sabe qué horas son públicas
  B) nota(óptimo que solo mira la máscara) / nota(v10) -> el techo de quien mueve el coste a las horas que no se ven,
     con lo que deja en la otra mitad y en el episodio completo

No se usa para diseñar el agente: es para saber leer el ranking.

    python scripts/p1_lab/hard_fin_techo_mascaras.py val [segundos_para_B]     # también dev, 1-7
"""
import pickle
import sys
import time
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

win = sys.argv[1]
budget = float(sys.argv[2]) if len(sys.argv) > 2 else 240.0
T0 = time.time()
OUT = REPO / "results" / "p1_hard"
full = B.hard_table()
df = B.split_frame(full, win).reset_index(drop=True)
n = len(df)
ts = pd.DatetimeIndex(df.timestamp)
co2, eur = df.co2_kg_kwh.to_numpy(float), df.price_eur_kwh.to_numpy(float)
base_imp = np.maximum(df.load_kw - df.pv_kw, 0).to_numpy(float)
b_co2, b_eur = base_imp * co2, base_imp * eur

# semana (un mes cada una) y hora dentro de la semana, por fecha
key = (ts.year * 12 + ts.month).to_numpy()
wk = np.concatenate([[0], np.cumsum(key[1:] != key[:-1])])
start = pd.Series(ts).groupby(wk).transform("min")
hw = ((pd.Series(ts) - start).dt.total_seconds() // 3600).to_numpy(int)
day = hw // 24
nw = wk.max() + 1

cal = pickle.load(open(REPO / "results" / "hourly" / f"calcal_{win}.pkl", "rb"))
v10_co2, v10_eur = np.asarray(cal["out"]["v10"]["co2"], float), np.asarray(cal["out"]["v10"]["eur"], float)
assert len(v10_co2) == n and np.allclose(cal["base_co2"], b_co2, rtol=1e-6), "el pkl no casa con la ventana"


def nota(s_co2, s_eur, m):
    dc = 100 * s_co2[m].sum() / b_co2[m].sum()
    de = 100 * s_eur[m].sum() / b_eur[m].sum()
    return 0.7 * dc + 0.3 * de, dc, de


base = B.baseline_totals(df)
W = B.score_weights(base["co2_kg"] / n, base["cost_eur"] / n)


def oracle(keep=None, lam=0.0):
    """Óptimo con todo el futuro. Con `keep`, lo de fuera de la máscara pesa `lam` (0 = no cuesta nada)."""
    d = df.copy()
    if keep is not None:
        d.loc[~keep, ["price_eur_kwh", "co2_kg_kwh"]] *= lam
    totals, log = B.simulate_hard(B.OracleAgent(d, *W, p=B.HARD_PARAMS), df)
    imp = log.import_kw.to_numpy(float)
    return (base_imp - imp) * co2, (base_imp - imp) * eur, totals["infractions"]


# ------------------------------------------------------------------ máscaras
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
ALL = np.ones(n, bool)

# ------------------------------------------------------------------ A) óptimo que no conoce la máscara
o_co2, o_eur, infr = oracle()
f_v10, f_opt = nota(v10_co2, v10_eur, ALL), nota(o_co2, o_eur, ALL)
print(f"{win}: episodio completo v10 {f_v10[0]:.3f} (CO2 {f_v10[1]:.2f} coste {f_v10[2]:.2f}) | "
      f"óptimo {f_opt[0]:.3f} (CO2 {f_opt[1]:.2f} coste {f_opt[2]:.2f}) infr {infr} | cociente {f_opt[0] / f_v10[0]:.4f}", flush=True)
rows = []
for name, m in M.items():
    fam, var = name.split("|")
    a, o = nota(v10_co2, v10_eur, m), nota(o_co2, o_eur, m)
    rows.append({"ventana": win, "familia": fam, "mascara": var, "frac": m.mean(), "v10": a[0], "v10_co2": a[1], "v10_eur": a[2],
                 "opt": o[0], "opt_co2": o[1], "opt_eur": o[2], "coc": o[0] / a[0], "coc_co2": o[1] / a[1], "coc_eur": o[2] / a[2]})
A = pd.DataFrame(rows)
A.to_csv(OUT / f"fin_techo_mascaras_A_{win}.csv", index=False)
print("\nA) nota(óptimo con todo el futuro)/nota(v10) en las horas de la máscara")
for fam, g in A.groupby("familia", sort=False):
    print(f"  {fam:28s} n={len(g):3d} cociente min {g.coc.min():.3f} med {g.coc.median():.3f} max {g.coc.max():.3f} | "
          f">=1,16: {(g.coc >= 1.16).sum():3d} | v10 en la máscara {g.v10.min():.2f}-{g.v10.max():.2f} | "
          f"CO2 x{g.coc_co2.min():.3f}-{g.coc_co2.max():.3f} coste x{g.coc_eur.min():.3f}-{g.coc_eur.max():.3f}", flush=True)
print(f"  TOTAL {len(A)} máscaras, llegan a 1,16: {(A.coc >= 1.16).sum()}", flush=True)

# ------------------------------------------------------------------ B) óptimo que solo mira la máscara
order = [k for k in M if not k.startswith("azar")]
ra = [k for k in M if k.startswith("azar por horas")]
rd = [k for k in M if k.startswith("azar por días")]
for i in range(200):
    order += [rd[i], ra[i]]
rows = []
for name in order:
    if time.time() - T0 > budget:
        break
    fam, var = name.split("|")
    m = M[name]
    r_co2, r_eur, infr = oracle(m)
    a, o = nota(v10_co2, v10_eur, m), nota(r_co2, r_eur, m)
    ac, oc = nota(v10_co2, v10_eur, ~m), nota(r_co2, r_eur, ~m)
    of = nota(r_co2, r_eur, ALL)
    rows.append({"ventana": win, "familia": fam, "mascara": var, "v10_masc": a[0], "res_masc": o[0], "coc": o[0] / a[0],
                 "res_masc_co2": o[1], "res_masc_eur": o[2], "coc_co2": o[1] / a[1], "coc_eur": o[2] / a[2],
                 "v10_otra": ac[0], "res_otra": oc[0], "d_otra": oc[0] - ac[0],
                 "v10_todo": f_v10[0], "res_todo": of[0], "d_todo": of[0] - f_v10[0], "d_todo_vs_opt": of[0] - f_opt[0], "infr": infr})
Bt = pd.DataFrame(rows)
Bt.to_csv(OUT / f"fin_techo_mascaras_B_{win}.csv", index=False)
print(f"\nB) óptimo que solo mira la máscara ({len(Bt)} máscaras resueltas en {time.time() - T0:.0f} s)")
pd.set_option("display.width", 250)
print(Bt[~Bt.familia.str.startswith("azar")][["familia", "mascara", "v10_masc", "res_masc", "coc", "coc_co2", "coc_eur", "v10_otra", "res_otra",
                                             "d_otra", "res_todo", "d_todo"]].round(3).to_string(index=False), flush=True)
for fam, g in Bt.groupby("familia", sort=False):
    print(f"  {fam:28s} n={len(g):3d} cociente {g.coc.min():.3f}-{g.coc.max():.3f} (med {g.coc.median():.3f}) | >=1,16: {(g.coc >= 1.16).sum():3d} | "
          f"otra mitad {g.d_otra.min():+.2f} a {g.d_otra.max():+.2f} | episodio completo frente a v10 {g.d_todo.min():+.2f} a {g.d_todo.max():+.2f}", flush=True)
