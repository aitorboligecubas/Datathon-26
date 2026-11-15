"""Revisor del previsor de consumo neto: el agente real en las noches del cambio de hora (hora repetida / hora que falta)."""
import sys, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from battery.hard import HardBatteryAgent
def run(name, stamps, frozen=900.0):
    ag = HardBatteryAgent(); nl = ag.policy.netload; soc = 3000.0; out = []
    for i, s in enumerate(stamps):
        now = pd.Timestamp(s)
        obs = {"timestamp": now, "hour": now.hour, "day_of_week": now.dayofweek, "soc_kwh": soc, "soc_pct": soc / 6000, "soc_percent": soc / 60,
               "preu_actual": 0.2, "co2_actual": 0.2, "preus_properes_24h": [0.2, 0.2, 0.2], "co2_properes_24h": [0.2, 0.2, 0.2],
               "noves_dades_5min": {"ultim_consum_kw": frozen, "ultima_solar_kw": 0.0}, "cap_max_kwh": 6000.0, "power_max_kw": 1500.0}
        try:
            a = float(ag.act(obs))
        except Exception as e:
            a = float("nan"); print("EXCEPCION", name, now, repr(e))
        if i > 0:
            soc = max(0.0, min(6000.0, soc + (a * 0.9487 if a > 0 else a / 0.9487)))
        out.append("%s a=%.0f n_hist=%d" % (now.strftime("%d %H"), a, len(nl.r_hist)))
    print(name, " | ".join(out), "| vertido si el consumo real es %.0f: ver acciones < -%.0f" % (frozen, frozen))
hrs = lambda a, b: [str(t) for t in pd.date_range(a, b, freq="h")]
base_oct = hrs("2025-10-25 00:00", "2025-10-26 06:00")
run("oct seguido  ", base_oct[20:])
dup = hrs("2025-10-25 20:00", "2025-10-26 02:00") + hrs("2025-10-26 02:00", "2025-10-26 06:00")
run("oct 02h doble", dup)
run("mar seguido  ", hrs("2026-03-28 20:00", "2026-03-29 06:00"))
run("mar sin 02h  ", hrs("2026-03-28 20:00", "2026-03-29 01:00") + hrs("2026-03-29 03:00", "2026-03-29 06:00"))
ag = HardBatteryAgent(); nl = ag.policy.netload
for s in ("2025-10-25", "2025-10-26", "2026-03-28", "2026-03-29", "2026-03-30"):
    row = [round(nl.sky_at(pd.Timestamp(s) + pd.Timedelta(hours=h))[0]) for h in range(6, 21)]
    print(s, "cielo despejado 6-20 h:", row, "max a las", 6 + int(np.argmax(row)), "h")
