"""Revisor del SALTO ENTRE SEMANAS, 4.ª parte: TECHOS no causales de la frontera con el plan de 24 h del agente (v14,
calendario real). En las horas del plan de DESPUÉS del salto se le da la verdad: (a) el consumo y la solar reales,
(b) además el precio y el CO2 reales. Lo que suba es lo máximo que puede dar CUALQUIER regla que mejore lo que el
agente cree de la semana siguiente antes de cruzar el salto. No es un candidato: es una cota.

    python scripts/p1_lab/hard_fin_salto_techo_neto.py val dev 1-7
"""
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
from battery.hard_market import hour_index  # noqa: E402
from hard_fin_salto_regla import MarketLevel, MarketTrueJump  # noqa: E402
from hard_rev_perdidas_salto import CalPolicy  # noqa: E402

pd.set_option("display.width", 250)
full = B.hard_table()
for win in sys.argv[1:]:
    df = B.split_frame(full, win)
    exclude = set(df.timestamp)
    fit_df = full[~full.timestamp.isin(exclude)]
    market, solar = B.fit_market(exclude, fit_df), B.fit_solar(fit_df)
    base = B.baseline_totals(df)
    ts = list(pd.DatetimeIndex(df.timestamp))
    nxt = dict(zip(ts[:-1], ts[1:]))
    key = np.array([t.year * 12 + t.month for t in ts])
    wk = np.concatenate([[0], np.cumsum(key[1:] != key[:-1])])
    ends = [np.where(wk == j)[0][-1] for j in range(wk.max())]
    MarketTrueJump.true = {t: (float(p), float(c)) for t, p, c in zip(ts, df.price_eur_kwh, df.co2_kg_kwh)}
    true_nl = {t: (float(l), float(s)) for t, l, s in zip(ts, df.load_kw, df.pv_kw)}

    def true_netload(a, shrink=0.0):
        orig = a.policy.netload.scenarios
        cnt = [0]

        def scen(times):
            load, pv, margin = orig(times)
            load, pv, margin = np.array(load, dtype=float), np.array(pv, dtype=float), np.array(margin, dtype=float)
            keys = [hour_index(t) for t in times]
            for k in range(len(times)):
                if keys[k] - keys[0] != k:
                    v = true_nl.get(times[k])
                    if v is not None:
                        load[k], pv[k] = v
                        margin[k] = margin[k] * shrink
                        cnt[0] += 1
            return load, pv, margin
        a.policy.netload.scenarios = scen
        return cnt

    rows = []
    for name, mcls, nl in (("v14", None, False), ("TECHO: consumo y solar reales tras el salto", None, True),
                           ("TECHO: mercado + consumo y solar reales tras el salto", MarketTrueJump, True)):
        a = B.hard_agent(market, solar)
        a.policy.__class__ = CalPolicy
        a.policy.nxt = nxt
        if mcls is not None:
            a.policy.market.__class__ = mcls
        cnt = true_netload(a) if nl else [0]
        totals, log = B.simulate_hard(a, df)
        sc = B.score(totals, base)
        rows.append({"ventana": win, "agente": name, "score": sc["score_raw"], "co2": sc["d_co2_pct"], "coste": sc["d_cost_pct"],
                     "infr": sc["infractions"], "soc_fin_semana_media": float(log.soc_kwh.to_numpy()[ends].mean()), "n_horas_verdad": cnt[0],
                     "n_scen": getattr(a.policy, "n_scen", -1)})
        print(win, name, round(sc["score_raw"], 3), "soc fin semana:", np.round(log.soc_kwh.to_numpy()[ends]).astype(int).tolist(), flush=True)
    R = pd.DataFrame(rows)
    R["d_score"] = R.score - R.score.iloc[0]
    R.to_csv(REPO / "results" / "p1_hard" / f"fin_salto_techo_neto_{win}.csv", index=False)
    print(R.round(3).to_string(index=False), flush=True)
