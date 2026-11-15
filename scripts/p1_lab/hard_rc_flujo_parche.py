"""Revisor del FLUJO: ¿el arreglo "en agosto, la semana dura 168 h desde que empieza" cambia algo con el calendario
esperado (25-31/08)? ¿Y recupera lo perdido si la última semana es 16/08 23:00 - 23/08 22:00? NO se empaqueta."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "scripts"))
import p1_hard
from battery.hard import HardBatteryAgent, LAST_MONTHS
t = p1_hard.hard_table(); ts = pd.DatetimeIndex(t["timestamp"]); H1 = pd.Timedelta(hours=1)
def week(src, dst, n=168):
    s = pd.Timestamp(src); w = t[(ts >= s) & (ts < s + n * H1)].copy()
    w["timestamp"] = w["timestamp"] + (pd.Timestamp(dst) - s); return w
def run(df, patch):
    ag = HardBatteryAgent(); pol = ag.policy
    if patch:
        orig = pol.horizon_times
        def ht(obs):
            times = orig(obs)
            if obs.timestamp is not None and (obs.timestamp.year, obs.timestamp.month) in LAST_MONTHS:
                times = times[:max(168 - pol.block_hours, 1)]
            return times
        pol.horizon_times = ht
    return p1_hard.simulate_hard(ag, df)
prior = json.load(open(REPO / "models" / "hard_market.json"))
c2, ce = float(prior["co2_ref_kg_per_h"]) * 2016, float(prior["cost_ref_eur_per_h"]) * 2016
seed = json.load(open(REPO / "models" / "hard_solar.json")).get("seed") or []
out = ["semilla (inicio, horas): " + ", ".join(f"{s['start']}+{len(s['load'])}" for s in seed[-3:])]
jul = week("2026-07-18 00:00", "2026-07-25 00:00")
for name, aug in (("esperado 25-31/08", week("2026-07-14 00:00", "2026-08-25 00:00")), ("alternativo 16/08 23h-23/08 22h", week("2026-07-12 23:00", "2026-08-16 23:00"))):
    df = pd.concat([jul, aug], ignore_index=True)
    (ta, la), (tb, lb) = run(df, False), run(df, True)
    d = 100 * (0.7 * (ta["co2_kg"] - tb["co2_kg"]) / c2 + 0.3 * (ta["cost_eur"] - tb["cost_eur"]) / ce)
    out.append(f"{name}: sin arreglo soc_final={ta['final_soc_kwh']:.1f} infr={ta['infractions']} | con arreglo soc_final={tb['final_soc_kwh']:.1f} infr={tb['infractions']} | "
               f"acciones distintas={int((np.abs(la['action_kw'] - lb['action_kw']) > 1e-9).sum())} | ganancia del arreglo={d:.3f} puntos")
txt = "\n".join(out); print(txt)
(REPO / "results" / "p1_hard" / "rc_flujo_parche.txt").write_text(txt + "\n")
