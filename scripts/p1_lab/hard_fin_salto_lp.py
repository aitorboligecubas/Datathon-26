"""Revisor del SALTO ENTRE SEMANAS, 5.ª parte: cuánto vale COMO MUCHO la carga con la que se cruza el salto.

LP del episodio completo con todo el futuro conocido (el mismo problema que el óptimo): (a) libre; (b) obligado a cruzar
cada salto con la carga con la que lo cruza el agente actual (v14, calendario real). La diferencia (a) - (b) es el valor
máximo de "llegar con la carga buena" a todas las fronteras, con todo lo demás perfecto. Es una cota, no un candidato.

    python scripts/p1_lab/hard_fin_salto_lp.py val dev 1-7      # necesita results/p1_hard/fin_salto_sim_<ventana>.pkl
"""
import math
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import lil_matrix

REPO = Path(__file__).resolve().parents[2]
CAP, PMAX, SOC0 = 6000.0, 1500.0, 3000.0
ETA = math.sqrt(0.9)


def solve(net, w, fixed=None, soc_end_free=True):
    n = len(net)                      # variables: c[0:n], d[n:2n], imp[2n:3n], soc[3n:4n]
    cost = np.concatenate([np.zeros(2 * n), w, np.zeros(n)])
    A_ub = lil_matrix((n, 4 * n)); b_ub = -net.copy()          # c - d - imp <= -net
    A_eq = lil_matrix((n, 4 * n)); b_eq = np.zeros(n)
    for t in range(n):
        A_ub[t, t], A_ub[t, n + t], A_ub[t, 2 * n + t] = 1.0, -1.0, -1.0
        A_eq[t, 3 * n + t], A_eq[t, t], A_eq[t, n + t] = 1.0, -ETA, 1.0 / ETA
        if t > 0:
            A_eq[t, 3 * n + t - 1] = -1.0
        else:
            b_eq[t] = SOC0
    bounds = [(0, PMAX)] * (2 * n) + [(0, None)] * n + [(0, CAP)] * n
    if fixed:
        for t, v in fixed.items():
            bounds[3 * n + t] = (max(v - 1e-6, 0.0), min(v + 1e-6, CAP))
    r = linprog(cost, A_ub=A_ub.tocsr(), b_ub=b_ub, A_eq=A_eq.tocsr(), b_eq=b_eq, bounds=bounds, method="highs")
    assert r.status == 0, r.message
    return r.x[2 * n:3 * n], r.x[3 * n:]


for win in sys.argv[1:]:
    d = pickle.load(open(REPO / "results" / "p1_hard" / f"fin_salto_sim_{win}.pkl", "rb"))
    df, res = d["df"], d["res"]
    n = len(df)
    ts = pd.DatetimeIndex(df.timestamp)
    key = (ts.year * 12 + ts.month).to_numpy()
    wk = np.concatenate([[0], np.cumsum(key[1:] != key[:-1])])
    ends = [int(np.where(wk == j)[0][-1]) for j in range(wk.max())]
    co2, eur = df.co2_kg_kwh.to_numpy(float), df.price_eur_kwh.to_numpy(float)
    net = (df.load_kw - df.pv_kw).to_numpy(float)
    base_imp = np.maximum(net, 0)
    w = 0.7 * 100 * co2 / (base_imp * co2).sum() + 0.3 * 100 * eur / (base_imp * eur).sum()
    nota = lambda imp: float((w * (base_imp - imp)).sum())  # noqa: E731
    v14 = res["v14"][1]
    s14 = v14.soc_kwh.to_numpy(float)
    imp_free, soc_free = solve(net, w)
    imp_fix, soc_fix = solve(net, w, {t: s14[t] for t in ends})
    # al revés: el agente no se toca; cuánto ganaría el óptimo de cada semana si arrancara con la carga del óptimo libre
    print(f"\n=== {win}: v14 {nota(v14.import_kw.to_numpy(float)):.3f} | óptimo libre {nota(imp_free):.3f} (banco: {res['optimo'][0]['score_raw']:.3f}) | "
          f"óptimo obligado a cruzar cada salto con la carga de v14 {nota(imp_fix):.3f} | VALOR MÁXIMO DE LA CARGA EN LOS SALTOS {nota(imp_free) - nota(imp_fix):.3f}")
    print("carga al cruzar: óptimo libre", np.round(soc_free[ends]).astype(int).tolist(), "| v14", np.round(s14[ends]).astype(int).tolist(),
          f"| medias {soc_free[ends].mean():.0f} y {s14[ends].mean():.0f}")
    # por salto: se suelta UNA frontera cada vez (las demás, con la carga de v14)
    one = []
    for j, t in enumerate(ends):
        fx = {u: s14[u] for u in ends if u != t}
        one.append(nota(solve(net, w, fx)[0]) - nota(imp_fix))
    print("valor de soltar cada salto por separado:", np.round(one, 3).tolist(), "suma", round(float(np.sum(one)), 3))
    pd.DataFrame({"ventana": win, "salto": [f"{ts[t].strftime('%Y-%m-%d')}" for t in ends], "soc_optimo": soc_free[ends], "soc_v14": s14[ends],
                  "valor_soltar": one}).to_csv(REPO / "results" / "p1_hard" / f"fin_salto_lp_{win}.csv", index=False)
