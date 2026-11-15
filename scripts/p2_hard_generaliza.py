"""¿Qué versión del modo difícil aguanta mejor datos distintos de los del train? Owner: P2. NO se empaqueta.

    python scripts/p2_hard_generaliza.py <escenario>     # base, otro_ano, precios, solar_mitad, consumo, mezcla

Los modelos se ajustan con el train SIN la ventana (últimas 168 h de cada mes) y se evalúan en la ventana deformada:
otro año (fechas +364 días: ni semilla del train ni festivos casan), precio x1,5 y CO2 x0,7, solar a la mitad,
consumo x1,3, y todo a la vez. Banco normal (scripts/p1_hard.py).
"""
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "scripts"))
import pandas as pd  # noqa: E402

import p1_hard as B  # noqa: E402

esc = sys.argv[1]
full = B.hard_table()
df = B.split_frame(full, "val")
exclude = set(df.timestamp)
fit_df = full[~full.timestamp.isin(exclude)]
old_market = B.fit_market(exclude, fit_df, blend=False, weekend=False)
new_market = B.fit_market(exclude, fit_df)
solar = B.fit_solar(fit_df)
df = df.copy()
if esc in ("otro_ano", "mezcla"):
    df["timestamp"] = df["timestamp"] + pd.Timedelta(days=364)       # mismo día de la semana, un año después
if esc in ("precios", "mezcla"):
    df["price_eur_kwh"] *= 1.5
    df["co2_kg_kwh"] *= 0.7
if esc in ("solar_mitad", "mezcla"):
    df["pv_kw"] *= 0.5
    if "irradiancia_wm2" in df:
        df["irradiancia_wm2"] *= 0.5
if esc in ("consumo", "mezcla"):
    df["load_kw"] *= 1.3
base = B.baseline_totals(df)


def build(market, scen=True):
    return B.hard_agent(market, solar, use_scenarios=scen)


VARS = {"v10": lambda: build(old_market, scen=False), "v12": lambda: build(old_market), "v14": lambda: build(new_market)}
out = []
for name, mk in VARS.items():
    totals, _ = B.simulate_hard(mk(), df)
    sc = B.score(totals, base)
    out.append(f"{name} {sc['score_raw']:.3f} (infr {sc['infractions']})")
try:
    oracle = B.OracleAgent(df, *B.score_weights(base["co2_kg"] / len(df), base["cost_eur"] / len(df)), B.HARD_PARAMS)
    t2, _ = B.simulate_hard(oracle, df)
    out.append(f"óptimo {B.score(t2, base)['score_raw']:.3f}")
except Exception as e:
    out.append("óptimo n/d")
print(f"{esc:<12} | " + " | ".join(out), flush=True)
