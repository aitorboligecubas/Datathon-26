"""Diferencias entre variantes mes a mes (CO2 y EUR ahorrados, por 1.000 h), para compararlas con las de la web.
Web (1.008 h): margen 1,0 - 1,4: -13 kg, +196 EUR | v12 - v10: +6 kg, -155 EUR | semilla: +34 kg, +26 EUR."""
import sys, warnings, pickle
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "results" / "hourly"
OUT.mkdir(parents=True, exist_ok=True)
warnings.filterwarnings("ignore")
sys.path.insert(0, str(REPO / "scripts")); sys.path.insert(0, str(REPO / "src"))
import numpy as np, pandas as pd
import p1_hard as B

win = sys.argv[1]
full = B.hard_table()
df = B.split_frame(full, win)
exclude = set(df.timestamp)
fit_df = full[~full.timestamp.isin(exclude)]
prior = B.fit_market(exclude, fit_df)
solar = B.fit_solar(fit_df)

def z14(pol):
    pol.use_scenarios = False
    pol.netload.z = pol.netload.z_plan = pol.netload.z_default = 1.4
def z10(pol):
    pol.use_scenarios = False
def noseed(pol):
    pol.use_scenarios = False
    pol.use_seed = False
VARS = {"z14": z14, "z10": z10, "z10_sin_semilla": noseed, "v12": lambda pol: None}
base_imp = np.maximum(df.load_kw - df.pv_kw, 0).to_numpy(float)
out = {}
for name, setup in VARS.items():
    a = B.hard_agent(prior, solar)
    setup(a.policy)
    totals, log = B.simulate_hard(a, df)
    sav_co2 = (base_imp - log.import_kw.to_numpy()) * df.co2_kg_kwh.to_numpy()
    sav_eur = (base_imp - log.import_kw.to_numpy()) * df.price_eur_kwh.to_numpy()
    out[name] = pd.DataFrame({"timestamp": df.timestamp, "co2": sav_co2, "eur": sav_eur, "action": log.action_kw.to_numpy(),
                              "export": log.export_kw.to_numpy(), "soc": log.soc_kwh.to_numpy()})
base = pd.DataFrame({"timestamp": df.timestamp, "co2": base_imp * df.co2_kg_kwh.to_numpy(), "eur": base_imp * df.price_eur_kwh.to_numpy()})
pickle.dump({"out": out, "base": base, "df": df}, open(str(OUT / f"publico_por_mes_{win}.pkl"), "wb"))
mes = df.timestamp.dt.month.to_numpy()
rows = []
for m in sorted(set(mes)):
    sel = mes == m
    n = sel.sum()
    r = {"ventana": win, "mes": m, "h": int(n), "base_kg_h": base.co2[sel].sum() / n, "base_eur_h": base.eur[sel].sum() / n}
    for name in VARS:
        r[f"{name}_co2%"] = 100 * out[name].co2[sel].sum() / base.co2[sel].sum()
        r[f"{name}_eur%"] = 100 * out[name].eur[sel].sum() / base.eur[sel].sum()
    # diferencias por 1.000 h
    k = 1000.0 / n
    r["z10-z14 kg"] = k * (out["z10"].co2[sel].sum() - out["z14"].co2[sel].sum()); r["z10-z14 eur"] = k * (out["z10"].eur[sel].sum() - out["z14"].eur[sel].sum())
    r["v12-z10 kg"] = k * (out["v12"].co2[sel].sum() - out["z10"].co2[sel].sum()); r["v12-z10 eur"] = k * (out["v12"].eur[sel].sum() - out["z10"].eur[sel].sum())
    r["semilla kg"] = k * (out["z10"].co2[sel].sum() - out["z10_sin_semilla"].co2[sel].sum()); r["semilla eur"] = k * (out["z10"].eur[sel].sum() - out["z10_sin_semilla"].eur[sel].sum())
    rows.append(r)
t = pd.DataFrame(rows)
print(t[["ventana", "mes", "h", "base_kg_h", "base_eur_h", "z10_co2%", "z10_eur%", "v12_co2%", "v12_eur%", "z10-z14 kg", "z10-z14 eur", "v12-z10 kg", "v12-z10 eur", "semilla kg", "semilla eur"]].round(1).to_string(index=False))
n = len(df); k = 1000.0 / n
print(f"TOTAL {win} por 1.000 h: z10-z14 {k*(out['z10'].co2.sum()-out['z14'].co2.sum()):+.0f} kg {k*(out['z10'].eur.sum()-out['z14'].eur.sum()):+.0f} EUR | "
      f"v12-z10 {k*(out['v12'].co2.sum()-out['z10'].co2.sum()):+.0f} kg {k*(out['v12'].eur.sum()-out['z10'].eur.sum()):+.0f} EUR | "
      f"semilla {k*(out['z10'].co2.sum()-out['z10_sin_semilla'].co2.sum()):+.0f} kg {k*(out['z10'].eur.sum()-out['z10_sin_semilla'].eur.sum()):+.0f} EUR")
