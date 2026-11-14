"""Verificación independiente del candidato 'solar' (HARD MODE): el candidato con todo apagado, con z = 1,4 y la copia
de src, en dev y val (¿la copia integrada decide igual que el candidato?).

    python results/p1_hard/solar_verif_variantes.py

No se empaqueta. No toca nada del repo.
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "scripts"))
import p1_hard as bench
from battery.sim import baseline_totals, score
import battery.hard_solar as hs
make = bench.load_factory(str(REPO / "scripts/p1_lab/hard_solar_cand.py") + ":make")
full = bench.hard_table()
print("Z_SOLAR en src:", getattr(hs, "Z_SOLAR", None))
for split in ("dev", "val"):
    df = bench.split_frame(full, split)
    exclude = set(df.timestamp)
    fit_df = full[~full.timestamp.isin(exclude)]
    prior = bench.fit_market(exclude, fit_df); solar_prior = bench.fit_solar(fit_df)
    simple = {k: v for k, v in solar_prior.items() if k != "cand"}
    base = baseline_totals(df)
    def cand(**o):
        a = bench.hard_agent(prior, solar_prior); a.policy.netload = make(exclude, a.policy.forecaster, **o); return a
    off = dict(reg=False, freeze=False, quant=False, uncap=False, pvreg=False, shade_now=False, sky=False)
    agents = {"partida (v6)": lambda: bench.hard_agent(prior, simple),
              "candidato, todo apagado": lambda: cand(**off),
              "CANDIDATO (z=1,0)": cand,
              "candidato con z=1,4": lambda: cand(z=1.4),
              "agente actual de src (v8)": lambda: bench.hard_agent(prior, solar_prior)}
    for name, fac in agents.items():
        tot, log = bench.simulate_hard(fac(), df)
        ex = log[log.export_kw > 1e-6]
        print(f"{split} | {name:28s} {score(tot, base)['score_raw']!r:22} infr {tot['infractions']} | vert_descarga {ex[ex.action_kw < -1e-6].export_kw.sum():7.0f} | vert_solar {ex[ex.action_kw >= -1e-6].export_kw.sum():7.0f}")
