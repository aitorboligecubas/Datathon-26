"""Medida independiente del arreglo de la otra sesión (rama `revision-decision`): en la v10, el tope de la descarga lo
pone la previsión de esta hora y no lo comprado la hora anterior. Con el calendario real del episodio.

    python scripts/p1_lab/hard_revision_tope.py val      # también dev, 1-7
"""
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
REPO = Path(__file__).resolve().parents[2]
for extra in (str(REPO / "src"), str(REPO / "scripts"), str(REPO / "scripts" / "p1_lab")):
    if extra not in sys.path:
        sys.path.insert(0, extra)
import pandas as pd  # noqa: E402

import p1_hard as B  # noqa: E402
from hard_rev_perdidas_salto import CalPolicy  # noqa: E402


class TopeArreglado(CalPolicy):
    def cap_discharge(self, action_kw, obs):
        nl = getattr(self, "netload", None)
        if getattr(nl, "fresh", False) and getattr(nl, "uncap", False):
            return action_kw
        return super().cap_discharge(action_kw, obs)


win = sys.argv[1]
full = B.hard_table()
df = B.split_frame(full, win)
exclude = set(df.timestamp)
fit_df = full[~full.timestamp.isin(exclude)]
old_market = B.fit_market(exclude, fit_df, blend=False, weekend=False)
solar = B.fit_solar(fit_df)
base = B.baseline_totals(df)
ts = list(pd.DatetimeIndex(df.timestamp))
nxt = dict(zip(ts[:-1], ts[1:]))
for name, cls in (("v10", CalPolicy), ("v10 + tope por la previsión", TopeArreglado)):
    a = B.hard_agent(old_market, solar, use_scenarios=False)
    a.policy.__class__ = cls
    a.policy.nxt = nxt
    totals, log = B.simulate_hard(a, df)
    co2 = 100 * (base["co2_kg"] - totals["co2_kg"]) / base["co2_kg"]
    eur = 100 * (base["cost_eur"] - totals["cost_eur"]) / base["cost_eur"]
    print(f"{win:5s} {name:28s} score {0.7 * co2 + 0.3 * eur:.3f} (CO2 {co2:.2f} coste {eur:.2f}) infr {totals['infractions']} vertido {totals['export_kwh']:.0f} kWh", flush=True)
