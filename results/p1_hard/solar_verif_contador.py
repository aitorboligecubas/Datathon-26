"""Verificación independiente del candidato 'solar' (HARD MODE): escenarios sintéticos sobre val con el contador a 0
(con la solar viva y sin ella), para el agente de partida, el candidato y la copia de src.

    python results/p1_hard/solar_verif_contador.py

No se empaqueta. No toca nada del repo.
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "scripts"))
import p1_hard as bench
from battery.sim import baseline_totals, score
make = bench.load_factory(str(REPO / "scripts/p1_lab/hard_solar_cand.py") + ":make")
full = bench.hard_table()
real = bench.split_frame(full, "val")
exclude = set(real.timestamp)
fit_df = full[~full.timestamp.isin(exclude)]
prior = bench.fit_market(exclude, fit_df); solar_prior = bench.fit_solar(fit_df)
simple = {k: v for k, v in solar_prior.items() if k != "cand"}
ts = pd.DatetimeIndex(real.timestamp)
scen = {}
a = real.copy(); a.loc[(ts.year == 2026) & (ts.month == 5), "load_kw"] = 0.0
scen["semana de mayo con el contador a 0 y la solar viva"] = a
b = real.copy(); b.loc[(ts.hour >= 10) & (ts.hour <= 15) & (ts.day == 20), "load_kw"] = 0.0
scen["día 20 de cada mes, de 10 a 15 h, contador a 0 y solar viva"] = b
c = real.copy(); m = (ts.hour >= 10) & (ts.hour <= 15) & (ts.day == 20); c.loc[m, "load_kw"] = 0.0; c.loc[m, "pv_kw"] = 0.0
scen["día 20 de cada mes, de 10 a 15 h, contador y solar a 0 (como la avería del train)"] = c
def cand(**o):
    ag = bench.hard_agent(prior, solar_prior); ag.policy.netload = make(exclude, ag.policy.forecaster, **o); return ag
agents = {"partida (v6)": lambda: bench.hard_agent(prior, simple), "CANDIDATO (z=1,0)": cand,
          "candidato con z=1,4": lambda: cand(z=1.4), "copia de src (v8, z=1,4 + regla solar viva)": lambda: bench.hard_agent(prior, solar_prior)}
for name, df in scen.items():
    base = baseline_totals(df)
    print(f"\n{name}")
    for an, fac in agents.items():
        tot, log = bench.simulate_hard(fac(), df)
        ex = log[log.export_kw > 1e-6]
        zero = df.load_kw.to_numpy() == 0
        chg_zero = float(np.clip(log.action_kw.to_numpy()[zero], 0, None).sum())
        imp_zero = float(log.import_kw.to_numpy()[zero].sum())
        print(f"   {an:45s} score {score(tot, base)['score_raw']:.4f} | infr {tot['infractions']} | vertido total {tot['export_kwh']:.0f} kWh | en las horas a 0: carga {chg_zero:.0f} kWh, compra a la red {imp_zero:.0f} kWh")
