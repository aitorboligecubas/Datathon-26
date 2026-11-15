"""Revisor del previsor de consumo neto: a las 23 h el previsor da por exacta la lectura de las 22 h (margen 0)."""
import json, sys, warnings, glob
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import p1_hard
from battery.hard import HardBatteryAgent
t = p1_hard.hard_table()
ts = pd.DatetimeIndex(t.timestamp); lo = pd.Series(t.load_kw.to_numpy(float), index=ts)
l23 = lo[ts.hour == 23]; l22 = lo.reindex(l23.index - pd.Timedelta(hours=1)).to_numpy(float)
d = l22 - l23.to_numpy(float)          # > 0: a las 23 h se consume menos que la lectura de las 22 h
ok = np.isfinite(d) & (l23.to_numpy(float) > 0) & (l22 > 0)
d = d[ok]
print("noches:", len(d), "media(l22-l23)=%.1f kW" % d.mean(), "mediana=%.1f" % np.median(d), "p10=%.1f p90=%.1f" % (np.quantile(d, .1), np.quantile(d, .9)),
      "frac l23<l22: %.2f" % (d > 1e-6).mean(), "media de max(l22-l23,0)=%.1f kW" % np.maximum(d, 0).mean())
# Qué prevé el previsor real a las 23 h: lectura de las 22 h, margen 0
ag = HardBatteryAgent(); nl = ag.policy.netload
tt = pd.Timestamp("2025-09-25 22:00")
for k, lp in enumerate((1000.0, 1100.0)):
    now = tt + pd.Timedelta(hours=k)
    obs = {"timestamp": now, "hour": now.hour, "day_of_week": now.dayofweek, "soc_kwh": 3000.0, "soc_pct": .5, "soc_percent": 50.0,
           "preu_actual": 0.2, "co2_actual": 0.2, "preus_properes_24h": [0.2, 0.05, 0.05], "co2_properes_24h": [0.2, 0.03, 0.03],
           "noves_dades_5min": {"ultim_consum_kw": lp, "ultima_solar_kw": 0.0}, "cap_max_kwh": 6000.0, "power_max_kw": 1500.0}
    a = ag.act(obs)
    ld, pv, mg = nl.scenarios([now + pd.Timedelta(hours=j) for j in range(4)])
    print(now, "lectura anterior=%.0f" % lp, "accion=%.1f" % a, "prevision consumo=", np.round(ld, 1), "margen=", np.round(mg, 1), "perfil=%.0f" % nl.profile(now))
print("l_lo[22], l_lo[23], l_lo[0]:", nl.l_lo[22], nl.l_lo[23], nl.l_lo[0], " reg1[23][0]=", nl.reg1[23][0])
# Vertido a las 23 h en los registros hora a hora del banco, si los hay
for f in sorted(glob.glob(str(ROOT / "results" / "hourly" / "*.csv")))[-40:]:
    try:
        g = pd.read_csv(f, parse_dates=["timestamp"])
        if "export_kw" not in g or "action_kw" not in g or g.action_kw.abs().max() <= 500.5:
            continue
        h = g.timestamp.dt.hour
        night = g.pv_kw < 1.0
        print(Path(f).name, "n=%d" % len(g), "vertido total=%.0f kWh" % g.export_kw.sum(), "vertido sin sol=%.0f" % g.export_kw[night].sum(),
              "vertido a las 23 h=%.0f kWh en %d noches (descarga a las 23 h en %d)" % (g.export_kw[h == 23].sum(), int((g.export_kw[h == 23] > 1e-6).sum()), int((g.action_kw[h == 23] < -1).sum())),
              "compra total=%.0f" % g.import_kw.sum())
    except Exception as e:
        pass
