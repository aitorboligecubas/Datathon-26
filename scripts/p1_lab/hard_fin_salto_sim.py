"""Revisor del SALTO ENTRE SEMANAS, 1.ª parte: simula con el CALENDARIO REAL el agente actual (v14) y el óptimo
(todo el futuro) y guarda el detalle hora a hora (carga incluida) para medir la frontera entre semanas.

    python scripts/p1_lab/hard_fin_salto_sim.py val [regla]     # también dev, 1-7
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
regla = sys.argv[2] if len(sys.argv) > 2 else ""
OUT = REPO / "results" / "p1_hard"
full = B.hard_table()
df = B.split_frame(full, win)
exclude = set(df.timestamp)
fit_df = full[~full.timestamp.isin(exclude)]
base = B.baseline_totals(df)
n = len(df)
ts = list(pd.DatetimeIndex(df.timestamp))
nxt = dict(zip(ts[:-1], ts[1:]))
res = {}
if not regla:
    W = B.score_weights(base["co2_kg"] / n, base["cost_eur"] / n)
    totals, log = B.simulate_hard(B.OracleAgent(df, *W, p=B.HARD_PARAMS), df)
    res["optimo"] = (B.score(totals, base), log)
    print(win, "optimo", round(res["optimo"][0]["score_raw"], 3), flush=True)
a = B.hard_agent(B.fit_market(exclude, fit_df), B.fit_solar(fit_df))
a.policy.__class__ = CalPolicy
a.policy.nxt = nxt
if regla:
    import hard_fin_salto_regla as R  # noqa: E402
    R.aplica(a, regla, nxt)
totals, log = B.simulate_hard(a, df)
name = "v14" + ("+" + regla if regla else "")
res[name] = (B.score(totals, base), log)
print(win, name, round(res[name][0]["score_raw"], 3), res[name][0], flush=True)
pickle.dump({"res": res, "df": df.reset_index(drop=True)}, open(REPO / "results" / "hourly" / f"fin_salto_sim_{win}{('_' + regla) if regla else ''}.pkl", "wb"))
