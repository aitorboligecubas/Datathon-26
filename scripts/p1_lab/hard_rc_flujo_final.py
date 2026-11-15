"""Revisor del FLUJO (repaso de cierre). NO se empaqueta. Owner: P1.
Qué mide: (1) el final del test con el calendario esperado (25-31/08) y (2) qué pasa si la última semana del test
es la que sigue al train de agosto (el train acaba el 16/08 a las 22:00 -> 16/08 23:00 a 23/08 22:00).
(3) observaciones a mano con cargas en el borde: ¿alguna acción sería infracción con la regla oficial?"""
import json, math, sys, time
from pathlib import Path
import numpy as np, pandas as pd
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "scripts"))
import p1_hard
from battery.hard import HardBatteryAgent, HARD_PARAMS

t = p1_hard.hard_table()
ts = pd.DatetimeIndex(t["timestamp"])
H1 = pd.Timedelta(hours=1)

def week(src_start, dst_start, n=168):
    s = pd.Timestamp(src_start)
    m = (ts >= s) & (ts < s + n * H1)
    w = t[m].copy()
    w["timestamp"] = w["timestamp"] + (pd.Timestamp(dst_start) - s)
    return w

def run(df, end_known=None):
    ag = HardBatteryAgent()
    if end_known is not None:
        orig = ag.policy.horizon_times
        ag.policy.horizon_times = lambda obs: [x for x in orig(obs) if x <= end_known]
    tot, log = p1_hard.simulate_hard(ag, df)
    return tot, log, ag

prior = json.load(open(REPO / "models" / "hard_market.json"))
co2_ref, cost_ref = float(prior["co2_ref_kg_per_h"]) * 2016, float(prior["cost_ref_eur_per_h"]) * 2016

def pts(a, b):
    return 100 * (0.7 * (a["co2_kg"] - b["co2_kg"]) / co2_ref + 0.3 * (a["cost_eur"] - b["cost_eur"]) / cost_ref)

jul = week("2026-07-18 00:00", "2026-07-25 00:00")
out = []
# (1) calendario esperado: 25-31/08 (datos del train de julio 14-20 llevados 42 días)
aug_exp = week("2026-07-14 00:00", "2026-08-25 00:00")
df1 = pd.concat([jul, aug_exp], ignore_index=True)
tot1, log1, ag1 = run(df1)
out.append(f"(1) final 31/08 23:00: horas={len(df1)} infr={tot1['infractions']} soc_final={tot1['final_soc_kwh']:.1f} "
           f"vertido={tot1['export_kwh']:.0f} kWh  t/paso={1000*tot1['runtime_s']/len(df1):.1f} ms -> 2016 h: {tot1['runtime_s']/len(df1)*2016:.1f} s "
           f"n_scen={ag1.policy.n_scen} fallbacks={ag1.policy.n_fallbacks}")
out.append(log1.tail(6).round(1).to_string())
# (2) última semana = 16/08 23:00 a 23/08 22:00 (datos del train de julio 12 23:00 llevados 35 días)
aug_alt = week("2026-07-12 23:00", "2026-08-16 23:00")
df2 = pd.concat([jul, aug_alt], ignore_index=True)
end = pd.Timestamp(df2["timestamp"].iloc[-1])
totA, logA, agA = run(df2)
totB, logB, agB = run(df2, end_known=end)
out.append(f"(2) final {end}: REAL  infr={totA['infractions']} soc_final={totA['final_soc_kwh']:.1f} n_scen={agA.policy.n_scen}")
out.append(f"    final {end}: SABE  infr={totB['infractions']} soc_final={totB['final_soc_kwh']:.1f}")
out.append(f"    pérdida del agente real frente al que sabe el final: {pts(totA, totB):.3f} puntos (sobre la referencia de 2.016 h)")
out.append(logA.tail(5).round(1).to_string())
# (3) bordes del recorte con la regla oficial
p = HARD_PARAMS
eta = 0.9 ** 0.5
bad = 0; n = 0
row = aug_exp.iloc[-1]
for when, k in (("2026-08-31 23:00", 1), ("2026-08-31 22:00", 2), ("2026-08-31 12:00", 3), ("2025-09-24 00:00", 3), ("2025-09-30 23:00", 3), ("2026-02-28 23:00", 3)):
    for soc in (0.0, 1e-9, 1e-5, 1e-4, 2e-4, 0.5, 1422.9, 3000.0, 4577.1, 5999.5, 5999.9998, 5999.9999, 5999.99999, 6000.0 - 1e-9, 6000.0):
        for load, pv in ((900.0, 0.0), (300.0, 2500.0), (0.0, 0.0), (1300.0, 100.0)):
            w = pd.Timestamp(when)
            obs = {"timestamp": w, "hour": w.hour, "day_of_week": w.dayofweek, "soc_kwh": soc, "soc_pct": soc / 6000, "soc_percent": soc / 60,
                   "preu_actual": 0.12, "co2_actual": 0.15, "preus_properes_24h": [0.12, 0.05, 0.2][:k], "co2_properes_24h": [0.15, 0.03, 0.25][:k],
                   "noves_dades_5min": {"ultim_consum_kw": load, "ultima_solar_kw": pv, "irradiancia_wm2": 500.0 if pv else 0.0, "temp_ambient_c": 20.0, "temp_panel_c": 25.0, "vent_ms": 2.0},
                   "cap_max_kwh": 6000.0, "power_max_kw": 1500.0}
            ag = HardBatteryAgent()
            for first in (True, False):       # primera hora de semana y hora siguiente
                o = dict(obs)
                if not first:
                    o["timestamp"] = w + H1 if k == 3 else w
                a = float(ag.act(o)); n += 1
                infr = (abs(a) > 1500.0) or (a > 0 and min(a, max(0.0, (6000.0 - soc) / eta)) < a) or (a < 0 and -min(-a, max(0.0, soc * eta)) > a) or not math.isfinite(a)
                if infr:
                    bad += 1; out.append(f"    INFRACCIÓN: {when} soc={soc!r} load={load} pv={pv} first={first} a={a!r}")
out.append(f"(3) observaciones a mano: {n}; infracciones con la regla oficial: {bad}")
txt = "\n".join(out)
print(txt)
(REPO / "results" / "p1_hard" / "rc_flujo_final.txt").write_text(txt + "\n")
