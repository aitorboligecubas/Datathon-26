"""Revisor del TECHO, 2.ª parte: ¿qué familias de máscara premian "llegar llena" o "acabar vacía" en el salto de semana?

Simula con el calendario real la v10 con dos comportamientos que no saben qué horas son públicas y solo conocen el
calendario (dónde acaba cada semana del test):
  - "llega llena": en las 5 últimas horas de cada semana carga todo lo que cabe (como hard_publico_llegar_lleno.py);
  - "acaba vacía": en las 5 últimas horas de cada semana descarga todo lo que el campus consume (cerrar cada semana
    como si fuera el final del test).
y los puntúa en las mismas 420 máscaras que hard_fin_techo_mascaras.py. Es para leer el ranking, no para diseñar.

    python scripts/p1_lab/hard_fin_techo_lleno_mascaras.py val
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
from hard_rev_perdidas_salto import CalPolicy  # noqa: E402

win = sys.argv[1]
which = sys.argv[2].split(",") if len(sys.argv) > 2 else ["llena", "vacia"]
OUT = REPO / "results" / "p1_hard"
full = B.hard_table()
df = B.split_frame(full, win).reset_index(drop=True)
exclude = set(df.timestamp)
fit_df = full[~full.timestamp.isin(exclude)]
old_market = B.fit_market(exclude, fit_df, blend=False, weekend=False)
solar = B.fit_solar(fit_df)
tsl = list(pd.DatetimeIndex(df.timestamp))
nxt = dict(zip(tsl[:-1], tsl[1:]))
n = len(df)
ts = pd.DatetimeIndex(df.timestamp)
ETA = 0.9 ** 0.5
co2, eur = df.co2_kg_kwh.to_numpy(float), df.price_eur_kwh.to_numpy(float)
base_imp = np.maximum(df.load_kw - df.pv_kw, 0).to_numpy(float)
b_co2, b_eur = base_imp * co2, base_imp * eur
key = (ts.year * 12 + ts.month).to_numpy()
wk = np.concatenate([[0], np.cumsum(key[1:] != key[:-1])])
start = pd.Series(ts).groupby(wk).transform("min")
hw = ((pd.Series(ts) - start).dt.total_seconds() // 3600).to_numpy(int)
day = hw // 24
nw = wk.max() + 1
last = np.zeros(n, int)                       # horas que faltan para acabar la semana (0 = última)
for w in range(nw):
    idx = np.flatnonzero(wk == w)
    last[idx] = np.arange(len(idx))[::-1]

cal = pickle.load(open(REPO / "results" / "hourly" / f"calcal_{win}.pkl", "rb"))
v10_co2, v10_eur = np.asarray(cal["out"]["v10"]["co2"], float), np.asarray(cal["out"]["v10"]["eur"], float)


def v10():
    a = B.hard_agent(old_market, solar, use_scenarios=False)
    a.policy.__class__ = CalPolicy
    a.policy.nxt = nxt
    return a


class Borde:
    """La v10, salvo en las `k` últimas horas de cada semana: `modo` 'llena' carga todo lo que cabe; 'vacia' descarga
    lo que consumió el campus la hora anterior (sin verter), hasta dejar la batería a cero."""

    def __init__(self, inner, modo, k=5):
        self.inner, self.modo, self.k, self.t = inner, modo, k, 0

    def act(self, obs):
        a = float(self.inner.act(obs))
        t = self.t
        self.t += 1
        if last[t] < self.k:
            pmax, soc = float(obs["power_max_kw"]), float(obs["soc_kwh"])
            if self.modo == "llena":
                room = (float(obs["cap_max_kwh"]) - soc) / ETA
                return float(min(pmax, max(room - 1e-6, 0.0)))
            rec = obs["noves_dades_5min"]
            net = max(float(rec["ultim_consum_kw"]) - float(rec["ultima_solar_kw"]), 0.0)
            return -float(min(pmax, max(soc * ETA - 1e-6, 0.0), 0.9 * net))
        return a


def nota(s_co2, s_eur, m):
    dc = 100 * s_co2[m].sum() / b_co2[m].sum()
    de = 100 * s_eur[m].sum() / b_eur[m].sum()
    return 0.7 * dc + 0.3 * de, dc, de


rng = np.random.default_rng(20261115)       # mismas máscaras que hard_fin_techo_mascaras.py
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
f_v10 = nota(v10_co2, v10_eur, ALL)
pd.set_option("display.width", 250)
for modo in which:
    totals, log = B.simulate_hard(Borde(v10(), modo), df)
    imp = log.import_kw.to_numpy(float)
    s_co2, s_eur = (base_imp - imp) * co2, (base_imp - imp) * eur
    pickle.dump({"co2": s_co2, "eur": s_eur, "soc": log.soc_kwh.to_numpy(float)}, open(OUT / f"fin_techo_borde_{modo}_{win}.pkl", "wb"))
    f = nota(s_co2, s_eur, ALL)
    print(f"\n{win} v10 + {modo} (5 últimas horas de cada semana): infr {totals['infractions']} | episodio completo {f[0]:.3f} "
          f"(CO2 {f[1]:.2f} coste {f[2]:.2f}) frente a v10 {f_v10[0]:.3f}: {f[0] - f_v10[0]:+.3f}", flush=True)
    rows = []
    for name, m in M.items():
        fam, var = name.split("|")
        a, o = nota(v10_co2, v10_eur, m), nota(s_co2, s_eur, m)
        ac, oc = nota(v10_co2, v10_eur, ~m), nota(s_co2, s_eur, ~m)
        rows.append({"ventana": win, "modo": modo, "familia": fam, "mascara": var, "v10": a[0], "var": o[0], "coc": o[0] / a[0],
                     "coc_co2": o[1] / a[1], "coc_eur": o[2] / a[2], "d_masc": o[0] - a[0], "d_otra": oc[0] - ac[0], "d_todo": f[0] - f_v10[0]})
    R = pd.DataFrame(rows)
    R.to_csv(OUT / f"fin_techo_borde_{modo}_{win}.csv", index=False)
    print(R[~R.familia.str.startswith("azar")][["familia", "mascara", "v10", "var", "coc", "coc_co2", "coc_eur", "d_masc", "d_otra"]].round(3).to_string(index=False))
    for fam, g in R.groupby("familia", sort=False):
        print(f"  {fam:28s} n={len(g):3d} cociente {g.coc.min():.3f}-{g.coc.max():.3f} (med {g.coc.median():.3f}) | >=1,16: {(g.coc >= 1.16).sum():3d} | "
              f"en la máscara {g.d_masc.min():+.2f} a {g.d_masc.max():+.2f} | en la otra {g.d_otra.min():+.2f} a {g.d_otra.max():+.2f}", flush=True)
