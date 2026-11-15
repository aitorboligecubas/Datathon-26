"""Revisor del previsor de consumo neto: cambio de hora en los datos, noches congeladas y primeras horas de cada semana."""
import json, math, sys, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from battery import hard_solar as hs
from battery.hard import HardBatteryAgent, HARD_PARAMS
import p1_hard
prior = json.loads((ROOT / "models" / "hard_solar.json").read_text())
c = prior["cand"]
hrs = np.arange(24)
print("centro de masa del cielo despejado (hora solar) por mes:", [round(float((np.array(r) * hrs).sum() / max(np.array(r).sum(), 1e-9)), 2) for r in c["pv_clear"]])
t = p1_hard.hard_table()
print("tabla:", t.shape, list(t.columns)[:8], t.timestamp.min(), t.timestamp.max())
ts = pd.DatetimeIndex(t.timestamp)
pv = t.pv_kw.to_numpy(float); lo = t.load_kw.to_numpy(float)
for mo in (3, 4, 10, 11):
    m = (ts.month == mo) & np.isfinite(pv)
    g = pd.Series(pv[m]).groupby(ts.hour[m]).mean()
    print("mes", mo, "centro de masa de la solar (hora de reloj):", round(float((g.index.values * g.values).sum() / g.values.sum()), 2), "dias:", sorted(set(ts.day[m]))[:1], sorted(set(ts.day[m]))[-1:])
# noches congeladas: lectura de la hora h igual a la de h-1
s = pd.Series(lo, index=ts)
prev = s.shift(1, freq="h").reindex(ts)
for h in (21, 22, 23, 0, 1, 2, 3, 4, 5, 6, 7):
    m = (ts.hour == h) & np.isfinite(lo) & np.isfinite(prev.to_numpy(float)) & (lo > 0)
    eq = np.abs(lo[m] - prev.to_numpy(float)[m]) < 1e-6
    print("hora", h, "n=", int(m.sum()), "igual a la anterior: %.3f" % (eq.mean() if m.sum() else float("nan")))
print("duplicados de fecha:", int(ts.duplicated().sum()), "nov load:", pd.Series(lo[ts.month == 11]).describe().to_dict() if (ts.month == 11).any() else None)
# Primeras horas de cada semana del test con el agente real (observaciones sinteticas con el perfil)
starts = ["2025-09-24", "2025-10-25", "2025-11-24", "2025-12-25", "2026-01-25", "2026-02-22", "2026-03-25", "2026-04-24", "2026-05-25", "2026-06-24", "2026-07-25", "2026-08-25"]
ag = HardBatteryAgent(); pol = ag.policy; nl = pol.netload
seed = pol.netload_seed
soc = 3000.0; exc = 0
for s0 in starts:
    t0 = pd.Timestamp(s0)
    for k in range(3):
        tt = t0 + pd.Timedelta(hours=k)
        last = seed.get(t0 - pd.Timedelta(hours=1))
        lp = (last[0] if last else 900.0) if k > 0 else 555.0     # k=0: lectura de hace un mes (se descarta)
        obs = {"timestamp": tt, "hour": tt.hour, "day_of_week": tt.dayofweek, "soc_kwh": soc, "soc_pct": soc / 6000, "soc_percent": soc / 60,
               "preu_actual": 0.12, "co2_actual": 0.1, "preus_properes_24h": [0.12, 0.11, 0.10], "co2_properes_24h": [0.1, 0.09, 0.08],
               "noves_dades_5min": {"ultim_consum_kw": lp, "ultima_solar_kw": 0.0, "irradiancia_wm2": 0.0, "temp_ambient_c": 15.0, "temp_panel_c": 15.0, "vent_ms": 2.0},
               "cap_max_kwh": 6000.0, "power_max_kw": 1500.0}
        try:
            a = float(ag.act(obs))
        except Exception as e:
            exc += 1; a = float("nan"); print("EXCEPCION", tt, repr(e))
        times = [tt + pd.Timedelta(hours=j) for j in range(3)]
        ld, pvv, mg = nl.scenarios(times)
        print(tt, "k=%d" % k, "accion=%8.1f" % a, "n_r_hist=%d" % len(nl.r_hist), "r1=%6.3f" % (nl.r_hist[-1] if nl.r_hist else float("nan")), "load_prev=%7.1f" % nl.load_prev,
              "prev_day_mean=%6.3f" % nl.prev_day_mean, "prev load[0:3]=", np.round(ld, 0), "margen0=%5.1f" % mg[0], "scen_used=", nl.scen_used, "mism=", pol.seed_mismatches, "perfil=%.0f" % nl.profile(tt))
print("excepciones:", exc)
