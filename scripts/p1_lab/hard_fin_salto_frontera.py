"""Revisor del SALTO ENTRE SEMANAS, 2.ª parte: cuántos puntos del episodio completo separan al agente (v14, calendario
real) del óptimo (todo el futuro) SOLO en las últimas 24 h y las primeras 24 h de cada semana. Sin simular el MPC:
usa results/hourly/calcal_<ventana>.pkl (ahorro hora a hora con calendario real) y simula solo el óptimo (un LP).

    python scripts/p1_lab/hard_fin_salto_frontera.py val dev 1-7
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

pd.set_option("display.width", 250)
full = B.hard_table()
for win in sys.argv[1:]:
    df = B.split_frame(full, win).reset_index(drop=True)
    n = len(df)
    ts = pd.DatetimeIndex(df.timestamp)
    co2, eur = df.co2_kg_kwh.to_numpy(float), df.price_eur_kwh.to_numpy(float)
    base_imp = np.maximum(df.load_kw - df.pv_kw, 0).to_numpy(float)
    b_co2, b_eur = base_imp * co2, base_imp * eur
    key = (ts.year * 12 + ts.month).to_numpy()
    wk = np.concatenate([[0], np.cumsum(key[1:] != key[:-1])])
    start = pd.Series(ts).groupby(wk).transform("min")
    hw = ((pd.Series(ts) - start).dt.total_seconds() // 3600).to_numpy(int)
    nw = wk.max() + 1
    cal = pickle.load(open(REPO / "results" / "hourly" / f"calcal_{win}.pkl", "rb"))
    base = B.baseline_totals(df)
    W = B.score_weights(base["co2_kg"] / n, base["cost_eur"] / n)
    totals, log = B.simulate_hard(B.OracleAgent(df, *W, p=B.HARD_PARAMS), df)
    imp = log.import_kw.to_numpy(float)
    o_co2, o_eur = (base_imp - imp) * co2, (base_imp - imp) * eur

    def pts(s_co2, s_eur):      # puntos del episodio completo que aporta cada hora
        return 0.7 * 100 * s_co2 / b_co2.sum() + 0.3 * 100 * s_eur / b_eur.sum()

    po = pts(o_co2, o_eur)
    print(f"\n=== {win}: {nw} semanas, {n} h. Óptimo {po.sum():.3f}")
    last24 = hw >= 144
    first24 = hw < 24
    # solo cuentan las fronteras reales: últimas 24 h de las semanas 0..nw-2 y primeras 24 h de las semanas 1..nw-1
    fr_last = last24 & (wk < nw - 1)
    fr_first = first24 & (wk > 0)
    ext = (first24 & (wk == 0)) | (last24 & (wk == nw - 1))        # arranque y final del episodio (no son salto)
    mid = ~(last24 | first24)
    for v in ("v10", "v12", "v14"):
        pv = pts(np.asarray(cal["out"][v]["co2"], float), np.asarray(cal["out"][v]["eur"], float))
        g = po - pv
        print(f"{v}: nota {pv.sum():.3f} | hueco total {g.sum():.3f} = últimas 24 h antes del salto {g[fr_last].sum():.3f} + primeras 24 h tras el salto "
              f"{g[fr_first].sum():.3f} + arranque/final del episodio {g[ext].sum():.3f} + resto (horas 24-143) {g[mid].sum():.3f}"
              f" | por hora: frontera {g[fr_last | fr_first].mean() * 1000:.2f} mpt/h, resto {g[mid].mean() * 1000:.2f} mpt/h")
        if v == "v14":
            rows = []
            for j in range(nw - 1):
                a = fr_last & (wk == j)
                b = fr_first & (wk == j + 1)
                rows.append({"salto": f"{ts[wk == j][0].strftime('%Y-%m')}->{ts[wk == j + 1][0].strftime('%Y-%m')}",
                             "hueco_ult24": g[a].sum(), "hueco_pri24": g[b].sum(), "hueco_48h": g[a].sum() + g[b].sum(),
                             "soc_fin_optimo": float(log.soc_kwh.to_numpy()[np.where(wk == j)[0][-1]])})
            R = pd.DataFrame(rows)
            R["ventana"] = win
            R.to_csv(REPO / "results" / "p1_hard" / f"fin_salto_frontera_{win}.csv", index=False)
            print(R.round(3).to_string(index=False))
            # perfil del hueco por hora de la semana (bloques de 24 h), para ver si la frontera destaca
            day = hw // 24
            print("hueco v14 por día de la semana (0..6), suma de todas las semanas:", np.round([g[day == d].sum() for d in range(7)], 3))
