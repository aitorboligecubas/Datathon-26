"""Revisor del previsor de precio y CO2 (cierre): qué camino sigue el previsor en las horas 20-23 del último día
de cada mes del test (salto de semana) y qué nivel aplica a las horas de la semana siguiente."""
import sys, json, math
from pathlib import Path
import numpy as np, pandas as pd
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
from battery.hard_market import MarketCand, month_blend, market_day_type, hour_index
from battery.hard import HardPolicy
from battery.obs import Obs

prior = json.load(open(REPO / "models" / "hard_market.json"))
pol = HardPolicy()
ONE = pd.Timedelta(hours=1)

def run_week(start, level_p, level_c, hours=168, show=(164, 165, 166, 167), jump_days=None):
    """Recorre una semana del test con precio y CO2 = perfil x nivel y enseña la previsión al final."""
    m = MarketCand(prior)
    ts = pd.Timestamp(start)
    # serie "real": la semana y la primera hora de la siguiente (lo que el entorno da como hora conocida)
    def real(name, t, lvl):
        return m.profile(name, t) * lvl
    rows = []
    for h in range(hours):
        t = ts + h * ONE
        o = Obs(hour=t.hour, weekday=t.dayofweek, soc_kwh=3000.0, price=np.zeros(3), co2=np.zeros(3),
                load_prev_kw=800.0, pv_prev_kw=0.0, timestamp=t)
        times = pol.horizon_times(o)
        pr = np.array([real("price", x, level_p) for x in times[:3]])
        co = np.array([real("co2", x, level_c) for x in times[:3]])
        o = o._replace(price=pr, co2=co)
        cand = None
        try:
            cand = m.cand_forecast(o, times)
        except Exception as e:
            cand = "EXC %r" % (e,)
        p, c = m.forecast(o, times)
        if h in show:
            basep = np.array([m.profile("price", x) for x in times])
            other = [k for k in range(len(times)) if times[k].month != times[0].month and k >= 3]
            same = [k for k in range(len(times)) if times[k].month == times[0].month and k >= 3]
            rows.append((str(t), "cand" if isinstance(cand, tuple) else "MADRE(%s)" % (cand,), len(times),
                         float(np.mean(p[other] / basep[other])) if other else float("nan"),
                         float(np.mean(p[same] / basep[same])) if same else float("nan")))
    return rows

print("== Camino y nivel aplicado a las horas de la semana siguiente (precio real = perfil x 1,5) ==")
for start in ("2025-09-24", "2025-12-25", "2026-02-22", "2026-07-25", "2026-08-25"):
    for r in run_week(start, 1.5, 1.5):
        print("  %s  camino=%-12s H=%2d  previsto/perfil semana siguiente=%.3f  mismo mes=%.3f" % r)
print("== Igual con nivel 0,6 ==")
for r in run_week("2025-09-24", 0.6, 0.6):
    print("  %s  camino=%-12s H=%2d  previsto/perfil semana siguiente=%.3f  mismo mes=%.3f" % r)

print("== month_blend en los días del test ==")
cen = prior["day_center"]
for (y, mo, d) in ((2025, 9, 24), (2025, 9, 30), (2025, 12, 25), (2025, 12, 31), (2026, 2, 22), (2026, 2, 28), (2026, 8, 25), (2026, 8, 31), (2026, 1, 25)):
    o, w = month_blend(mo, d, cen)
    print("  %04d-%02d-%02d -> mes vecino %d, peso %.3f, tipo %d" % (y, mo, d, o + 1, w, market_day_type(pd.Timestamp(y, mo, d))))

print("== Valores conocidos a 0, negativos, NaN ==")
for bad in (0.0, -0.05, float("nan"), float("inf")):
    m = MarketCand(prior)
    t = pd.Timestamp("2025-10-25 12:00")
    o = Obs(hour=12, weekday=t.dayofweek, soc_kwh=3000.0, price=np.array([bad, 0.1, 0.1]), co2=np.array([0.1, bad, 0.1]),
            load_prev_kw=800.0, pv_prev_kw=0.0, timestamp=t)
    times = pol.horizon_times(o)
    p, c = m.forecast(o, times)
    print("  conocido=%r -> precio finito=%s min=%.4f max=%.4f | co2 finito=%s min=%.4f max=%.4f" % (bad, np.isfinite(p).all(), p.min(), p.max(), np.isfinite(c).all(), c.min(), c.max()))
