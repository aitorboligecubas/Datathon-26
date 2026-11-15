"""Las versiones enviadas, medidas con el CALENDARIO REAL del episodio: tras la última hora de una semana viene otra
semana un mes después, como en el test. El banco normal no lo ejercita (el agente cree que la semana sigue).

    python scripts/p1_lab/hard_calendario_versiones.py val      # también dev, 1-7, 3-9, 12-18, 15-21
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
from hard_rev_perdidas_salto import CalPolicy, MarketJump  # noqa: E402

win = sys.argv[1]
full = B.hard_table()
df = B.split_frame(full, win)
exclude = set(df.timestamp)
fit_df = full[~full.timestamp.isin(exclude)]
old_market = B.fit_market(exclude, fit_df, blend=False, weekend=False)
new_market = B.fit_market(exclude, fit_df)
solar = B.fit_solar(fit_df)
base = B.baseline_totals(df)
ts = list(pd.DatetimeIndex(df.timestamp))
nxt = dict(zip(ts[:-1], ts[1:]))


def build(market, z=None, scen=True, jump=False, cal=True):
    a = B.hard_agent(market, solar, use_scenarios=scen)
    if z is not None:
        a.policy.netload.z = a.policy.netload.z_plan = a.policy.netload.z_default = z
    if cal:
        a.policy.__class__ = CalPolicy
        a.policy.nxt = nxt
    if jump:
        a.policy.market.__class__ = MarketJump
    return a


VARS = {
    "v10 (margen 1,0)": lambda cal: build(old_market, scen=False, cal=cal),
    "v10b (margen 0,8)": lambda cal: build(old_market, z=0.8, scen=False, cal=cal),
    "v9 (margen 1,4)": lambda cal: build(old_market, z=1.4, scen=False, cal=cal),
    "v12": lambda cal: build(old_market, cal=cal),
    "v14": lambda cal: build(new_market, cal=cal),
    "v14 + puente": lambda cal: build(new_market, jump=True, cal=cal),
}
rows = []
for name, mk in VARS.items():
    r = {"ventana": win, "version": name}
    for label, cal in (("banco normal", False), ("calendario real", True)):
        if label == "banco normal" and name == "v14 + puente":
            r[label] = float("nan")
            continue
        totals, log = B.simulate_hard(mk(cal), df)
        sc = B.score(totals, base)
        r[label] = sc["score_raw"]
        if cal:
            r["co2"], r["coste"], r["infr"] = sc["d_co2_pct"], sc["d_cost_pct"], sc["infractions"]
    rows.append(r)
    print(f"{win:6s} {name:20s} banco normal {r['banco normal']:.3f} | calendario real {r['calendario real']:.3f} (co2 {r['co2']:.2f} coste {r['coste']:.2f} infr {r['infr']})", flush=True)
pd.DataFrame(rows).to_csv(REPO / "results" / "p1_hard" / f"calendario_versiones_{win}.csv", index=False)
