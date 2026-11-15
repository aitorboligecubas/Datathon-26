"""Revisor del previsor de precio y CO2 (cierre): primera hora de las 12 semanas del test (¿camino con memoria y
todas las pistas?), nivel del perfil de septiembre frente al de agosto, y el cambio de hora."""
import sys, json, math
from pathlib import Path
import numpy as np, pandas as pd
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
from battery.hard_market import MarketCand, hour_index, NAMES, KNOWN_HOURS
from battery.hard import HardPolicy
from battery.obs import Obs
prior = json.load(open(REPO / "models" / "hard_market.json"))
pol = HardPolicy()
ONE = pd.Timedelta(hours=1)
starts = ["2025-09-24", "2025-10-25", "2025-11-24", "2025-12-25", "2026-01-25", "2026-02-22", "2026-03-25", "2026-04-24",
          "2026-05-25", "2026-06-24", "2026-07-25", "2026-08-25"]
m = MarketCand(prior)          # un solo previsor para las 12 semanas, como en el test
print("== Primera hora de cada semana (un solo previsor, sin pasar por las horas intermedias) ==")
for s in starts:
    t = pd.Timestamp(s)
    o = Obs(hour=0, weekday=t.dayofweek, soc_kwh=3000.0, price=np.zeros(3), co2=np.zeros(3), load_prev_kw=800.0, pv_prev_kw=0.0, timestamp=t)
    times = pol.horizon_times(o)
    o = o._replace(price=np.array([m.profile("price", x) * 1.2 for x in times[:3]]), co2=np.array([m.profile("co2", x) * 0.9 for x in times[:3]]))
    out = m.cand_forecast(o, times)
    i = hour_index(t) - m.h0
    sc = {n: m.scalars(n, i, 0) for n in NAMES}
    nan_sc = [n + ":" + k for n in NAMES for k, v in sc[n].items() if not math.isfinite(v)]
    ks = np.arange(3, 24)
    nan_y = {n: int((~np.isfinite(m.z[n][i + ks - 24])).sum() + (~np.isfinite(m.z[n][i + ks - 48])).sum()) for n in NAMES}
    seed_h = {n: int(np.isfinite(m.z[n][i - 168:i]).sum()) for n in NAMES}
    zlast = {n: float(np.nanmean(m.z[n][i - 24:i])) for n in NAMES}
    print("  %s camino=%s pistas NaN=%s zy/zy2 NaN=%s horas de semilla (7 d)=%s z medio ultimo dia=%s" % (s, "cand" if out is not None else "MADRE", nan_sc, nan_y, seed_h, {k: round(v, 3) for k, v in zlast.items()}))
print("rebase: h0 fijo =", m.h0)
print("== Perfil de septiembre (2025) frente al de agosto (2026), por tipo de dia ==")
for n in NAMES:
    p = np.asarray(prior[n])
    print("  %s: media sep/ago por tipo = %s ; corr. de forma (laborable) = %.3f ; jul/ago = %s" % (n, np.round(p[8].mean(axis=1) / p[7].mean(axis=1), 3), np.corrcoef(p[8][0] / p[8][0].mean(), p[7][0] / p[7][0].mean())[0, 1], np.round(p[6].mean(axis=1) / p[7].mean(axis=1), 3)))
    print("  %s: media oct/sep = %s ; ene/dic = %s ; mar/feb = %s" % (n, np.round(p[9].mean(axis=1) / p[8].mean(axis=1), 3), np.round(p[0].mean(axis=1) / p[11].mean(axis=1), 3), np.round(p[2].mean(axis=1) / p[1].mean(axis=1), 3)))
print("== Cambio de hora: fechas del plan alrededor ==")
for s in ("2025-10-26 00:00", "2026-03-29 00:00"):
    t = pd.Timestamp(s)
    o = Obs(hour=0, weekday=t.dayofweek, soc_kwh=3000.0, price=np.zeros(3), co2=np.zeros(3), load_prev_kw=800.0, pv_prev_kw=0.0, timestamp=t)
    print("  ", s, [x.strftime("%H") for x in pol.horizon_times(o)[:5]])
