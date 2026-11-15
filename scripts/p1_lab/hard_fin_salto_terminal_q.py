"""Revisor del SALTO ENTRE SEMANAS, 7.ª parte (exploratoria, decidida DESPUÉS de ver que la regla con el cuantil 25 % no
cambia ninguna decisión): la misma regla con el cuantil que corresponde a "no hay recarga barata al otro lado": la carga
(5.700 kWh útiles) cubre las ~6 horas peores de las primeras 24 h de la semana siguiente -> cuantil 75 %. Y el 50 %.

    python scripts/p1_lab/hard_fin_salto_terminal_q.py val dev 1-7
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
from hard_fin_salto_terminal import JumpTerminal  # noqa: E402


class JumpTerminalQ(JumpTerminal):
    jump_q = 0.75

    def next_week_terminal(self, times):
        q0 = self.terminal_quantile
        try:
            self.terminal_quantile = self.jump_q
            return JumpTerminal.next_week_terminal(self, times)
        finally:
            self.terminal_quantile = q0


REF = {"val": 20.874315874128982, "dev": 20.28842214541881, "1-7": 21.234583119389836}
full = B.hard_table()
rows = []
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
    ends_ = [np.where(wk == j)[0][-1] for j in range(wk.max())]
    for q in (0.75, 0.5):
        a = B.hard_agent(market, solar)
        a.policy.__class__ = JumpTerminalQ
        a.policy.nxt = nxt
        a.policy.jump_q = q
        totals, log = B.simulate_hard(a, df)
        sc = B.score(totals, base)
        rows.append({"ventana": win, "cuantil_salto": q, "score": sc["score_raw"], "d_score": sc["score_raw"] - REF[win], "co2": sc["d_co2_pct"],
                     "coste": sc["d_cost_pct"], "infr": sc["infractions"], "soc_fin_semana_media": float(log.soc_kwh.to_numpy()[ends_].mean())})
        print(win, q, round(sc["score_raw"], 3), f"d {sc['score_raw'] - REF[win]:+.3f}", "soc fin semana:", np.round(log.soc_kwh.to_numpy()[ends_]).astype(int).tolist(), flush=True)
    pd.DataFrame(rows).to_csv(REPO / "results" / "p1_hard" / "fin_salto_terminal_q.csv", index=False)
