"""Calibración del banco frente a la web: las 7 versiones enviadas (v6, v7, v8, v9, v10, v12, v14), simuladas en una
ventana del banco, con el detalle hora a hora. Después, scripts/p1_lab/hard_publico_mascaras.py compara, para varias
máscaras de "50 % de cada semana", lo que predice el banco con lo que salió en la web.

    python scripts/p1_lab/hard_publico_calibra.py val      # también dev, 1-7, 15-21...
"""
import pickle
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
REPO = Path(__file__).resolve().parents[2]
for extra in (str(REPO / "src"), str(REPO / "scripts")):
    if extra not in sys.path:
        sys.path.insert(0, extra)
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import p1_hard as B  # noqa: E402

OUT = REPO / "results" / "hourly"
OUT.mkdir(parents=True, exist_ok=True)
win = sys.argv[1]
full = B.hard_table()
df = B.split_frame(full, win)
exclude = set(df.timestamp)
fit_df = full[~full.timestamp.isin(exclude)]
old_market = B.fit_market(exclude, fit_df, blend=False, weekend=False)      # mercado de v5 a v12
new_market = B.fit_market(exclude, fit_df)                                   # v14: perfil interpolado y fines de semana
solar = B.fit_solar(fit_df)
simple = {k: v for k, v in solar.items() if k not in ("cand", "scen", "seed")}


def setz(pol, z):
    pol.netload.z = pol.netload.z_plan = pol.netload.z_default = z


VERSIONS = {
    "v6": lambda: B.hard_agent(old_market, simple, use_scenarios=False, use_seed=False),
    "v7": lambda: B.hard_agent(old_market, solar, use_scenarios=False, use_seed=False),
    "v8": lambda: B.hard_agent(old_market, solar, use_scenarios=False, use_seed=False),
    "v9": lambda: B.hard_agent(old_market, solar, use_scenarios=False),
    "v10": lambda: B.hard_agent(old_market, solar, use_scenarios=False),
    "v12": lambda: B.hard_agent(old_market, solar),
    "v14": lambda: B.hard_agent(new_market, solar),
}
Z = {"v8": 1.4, "v9": 1.4}
base_imp = np.maximum(df.load_kw - df.pv_kw, 0).to_numpy(float)
co2, eur = df.co2_kg_kwh.to_numpy(float), df.price_eur_kwh.to_numpy(float)
out = {}
for name, make in VERSIONS.items():
    a = make()
    if name in Z:
        setz(a.policy, Z[name])
    totals, log = B.simulate_hard(a, df)
    imp = log.import_kw.to_numpy(float)
    out[name] = {"co2": (base_imp - imp) * co2, "eur": (base_imp - imp) * eur, "action": log.action_kw.to_numpy(float), "infr": totals["infractions"]}
    sc = 70 * out[name]["co2"].sum() / (base_imp * co2).sum() + 30 * out[name]["eur"].sum() / (base_imp * eur).sum()
    print(f"{win:6s} {name:4s} score {sc:.3f} infr {totals['infractions']}", flush=True)
pickle.dump({"out": out, "base_co2": base_imp * co2, "base_eur": base_imp * eur, "timestamp": df.timestamp.to_numpy()},
            open(OUT / f"calibra_{win}.pkl", "wb"))
