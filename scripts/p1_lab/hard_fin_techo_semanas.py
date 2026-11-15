"""Revisor del TECHO, 5.ª parte: ¿el hueco entre la v10 y el óptimo está repartido o concentrado en alguna semana?

Si en el test hubiera más semanas "difíciles" que en casa, el techo podría estar más lejos. Nota por semana (mes) de
la v10 y del óptimo con todo el futuro, con el calendario real.

    python scripts/p1_lab/hard_fin_techo_semanas.py
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

full = B.hard_table()
for win in ("val", "dev", "1-7"):
    df = B.split_frame(full, win).reset_index(drop=True)
    n = len(df)
    ts = pd.DatetimeIndex(df.timestamp)
    co2, eur = df.co2_kg_kwh.to_numpy(float), df.price_eur_kwh.to_numpy(float)
    base_imp = np.maximum(df.load_kw - df.pv_kw, 0).to_numpy(float)
    b_co2, b_eur = base_imp * co2, base_imp * eur
    key = (ts.year * 12 + ts.month).to_numpy()
    wk = np.concatenate([[0], np.cumsum(key[1:] != key[:-1])])
    cal = pickle.load(open(REPO / "results" / "hourly" / f"calcal_{win}.pkl", "rb"))
    v_co2, v_eur = np.asarray(cal["out"]["v10"]["co2"], float), np.asarray(cal["out"]["v10"]["eur"], float)
    base = B.baseline_totals(df)
    W = B.score_weights(base["co2_kg"] / n, base["cost_eur"] / n)
    totals, log = B.simulate_hard(B.OracleAgent(df, *W, p=B.HARD_PARAMS), df)
    imp = log.import_kw.to_numpy(float)
    o_co2, o_eur = (base_imp - imp) * co2, (base_imp - imp) * eur
    out = []
    for w in range(wk.max() + 1):
        m = wk == w
        a = 0.7 * 100 * v_co2[m].sum() / b_co2[m].sum() + 0.3 * 100 * v_eur[m].sum() / b_eur[m].sum()
        o = 0.7 * 100 * o_co2[m].sum() / b_co2[m].sum() + 0.3 * 100 * o_eur[m].sum() / b_eur[m].sum()
        out.append((ts[m][0].strftime("%Y-%m"), a, o, o / a, b_co2[m].sum() / b_co2.sum()))
    print(win, " | ".join(f"{d}: v10 {a:.1f} ópt {o:.1f} x{r:.2f} (peso {100 * p:.0f} %)" for d, a, o, r, p in out))
    r = np.array([x[3] for x in out])
    print(f"   cociente por semana: min {r.min():.3f} mediana {np.median(r):.3f} max {r.max():.3f}", flush=True)
