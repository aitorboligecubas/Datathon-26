"""¿Qué semanas forman el conjunto público? Referencias sin batería por mes (train) frente a las de la web.
Web, 1.008 h: estándar 71.816 kg y 118.746 EUR; difícil ~60.255 kg y ~94.985 EUR."""
import sys, warnings, itertools
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "results" / "hourly"
OUT.mkdir(parents=True, exist_ok=True)
warnings.filterwarnings("ignore")
sys.path.insert(0, str(REPO / "scripts")); sys.path.insert(0, str(REPO / "src"))
import numpy as np, pandas as pd
import p1_hard as B

full = B.hard_table()          # pv ya x12
full["pv_std"] = full.pv_kw / 12.0
full["imp_std"] = np.maximum(full.load_kw - full.pv_std, 0)
full["imp_hard"] = np.maximum(full.load_kw - full.pv_kw, 0)
for c in ("std", "hard"):
    full[f"co2_{c}"] = full[f"imp_{c}"] * full.co2_kg_kwh
    full[f"eur_{c}"] = full[f"imp_{c}"] * full.price_eur_kwh
full["ym"] = full.timestamp.dt.to_period("M")
# la última semana disponible de cada mes del train (lo más parecido a los días 25-31)
rows = []
for ym, g in full.groupby("ym"):
    last = g.sort_values("timestamp").tail(168)
    rows.append({"mes": str(ym), "h": len(last), "desde": last.timestamp.min().strftime("%d"), "hasta": last.timestamp.max().strftime("%d"),
                 "co2_std": last.co2_std.sum(), "eur_std": last.eur_std.sum(), "co2_hard": last.co2_hard.sum(), "eur_hard": last.eur_hard.sum(),
                 "load": last.load_kw.mean(), "pv12": last.pv_kw.mean()})
m = pd.DataFrame(rows)
m["red_co2_%"] = 100 * (1 - m.co2_hard / m.co2_std)
m["red_eur_%"] = 100 * (1 - m.eur_hard / m.eur_std)
print(m.round(1).to_string(index=False))
print("\nWEB público (1.008 h): estándar 71816 kg, 118746 EUR | difícil 60255 kg, 94985 EUR | reducción por la solar x12: 16.1 % CO2, 20.0 % EUR")
tot = m[["co2_std", "eur_std", "co2_hard", "eur_hard"]].sum()
print(f"12 meses del train (últimas 168 h de cada uno, {int(m.h.sum())} h): estándar {tot.co2_std:.0f} kg, {tot.eur_std:.0f} EUR | difícil {tot.co2_hard:.0f} kg, {tot.eur_hard:.0f} EUR | "
      f"reducción {100*(1-tot.co2_hard/tot.co2_std):.1f} % CO2, {100*(1-tot.eur_hard/tot.eur_std):.1f} % EUR")
# subconjuntos de 6 meses (noviembre cuenta como 0 si no tiene datos) que más se parecen a la web
target = np.array([71816.0, 118746.0, 60255.0, 94985.0])
vals = m[["co2_std", "eur_std", "co2_hard", "eur_hard"]].to_numpy()
names = m.mes.tolist()
best = []
for combo in itertools.combinations(range(len(names)), 6):
    s = vals[list(combo)].sum(axis=0)
    err = float(np.sqrt((((s - target) / target) ** 2).mean()))
    best.append((err, combo, s))
best.sort(key=lambda x: x[0])
print("\nSubconjuntos de 6 semanas del train que más se parecen a la web (error relativo medio):")
for err, combo, s in best[:8]:
    print(f"  {100*err:5.1f} %  {[names[i][2:] for i in combo]}  -> std {s[0]:.0f} kg {s[1]:.0f} EUR | hard {s[2]:.0f} kg {s[3]:.0f} EUR")
for label, combo in (("sep-feb", [i for i, n in enumerate(names) if n[-2:] in ("09", "10", "11", "12", "01", "02")]),
                     ("mar-ago", [i for i, n in enumerate(names) if n[-2:] in ("03", "04", "05", "06", "07", "08")]),
                     ("impares (sep,nov,ene,mar,may,jul)", [i for i, n in enumerate(names) if n[-2:] in ("09", "11", "01", "03", "05", "07")]),
                     ("pares (oct,dic,feb,abr,jun,ago)", [i for i, n in enumerate(names) if n[-2:] in ("10", "12", "02", "04", "06", "08")])):
    s = vals[combo].sum(axis=0)
    err = float(np.sqrt((((s - target) / target) ** 2).mean()))
    print(f"  {label:36s} error {100*err:5.1f} %  std {s[0]:.0f} kg {s[1]:.0f} EUR | hard {s[2]:.0f} kg {s[3]:.0f} EUR | red {100*(1-s[2]/s[0]):.1f} % / {100*(1-s[3]/s[1]):.1f} %")
