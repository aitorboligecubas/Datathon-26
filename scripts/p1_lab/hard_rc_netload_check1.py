"""Revisor del previsor de consumo neto: comprobaciones rapidas de la semilla, los escenarios, el cambio de hora y el cielo."""
import json, math, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from battery import hard_solar as hs
from battery.hard import netload_seed_dict, HardBatteryAgent
prior = json.loads((ROOT / "models" / "hard_solar.json").read_text())
print("claves:", sorted(prior.keys()))
print("claves cand:", sorted(prior.get("cand", {}).keys()))
seed = netload_seed_dict(prior)
print("segmentos de semilla:", len(prior.get("seed") or []))
for seg in prior.get("seed") or []:
    lo = np.array(seg["load"], float); pv = np.array(seg["pv"], float)
    print("  ", seg["start"], "n=", len(lo), "nan load=", int(np.isnan(lo).sum()), "ceros load=", int((lo == 0).sum()), "ult load=", lo[-1], "ult pv=", pv[-1], "max pv=", np.nanmax(pv))
starts = ["2025-09-24", "2025-10-25", "2025-11-24", "2025-12-25", "2026-01-25", "2026-02-22", "2026-03-25", "2026-04-24",
          "2026-05-25", "2026-06-24", "2026-07-25", "2026-08-25"]
for s in starts:
    t = pd.Timestamp(s)
    last = seed.get(t - pd.Timedelta(hours=1))
    n, h = 0, t - pd.Timedelta(hours=2)
    while h in seed and n < 48:
        n += 1; h -= pd.Timedelta(hours=1)
    print(s, "ultima lectura:", last, "horas previas:", n)
sc = prior.get("scen")
print("scen:", sc)
if sc:
    a = sc["alphas"]; u = sc["u"]
    tail, head = hs.scen_probs(a)
    print("K=", len(a), "u ordenado:", all(u[i] <= u[i+1] for i in range(len(u)-1)), "alphas ordenado:", all(a[i] < a[i+1] for i in range(len(a)-1)))
    print("tail:", np.round(tail, 4)); print("head:", np.round(head, 4))
    print("tail[0]=", tail[0], "head[-1]=", head[-1], "head[0]=", head[0])
# cambio de hora
for s in ["2025-10-26 01:00", "2025-10-26 02:00", "2025-10-26 03:00", "2025-10-26 04:00", "2026-03-29 01:00", "2026-03-29 02:00", "2026-03-29 03:00", "2026-03-28 12:00", "2026-03-29 12:00", "2025-10-25 12:00", "2025-10-27 12:00"]:
    print(s, "verano:", hs.summer_time(pd.Timestamp(s)))
c = prior["cand"]
print("centers:", np.round(c["pv_day"], 2), "sky:", c["sky"])
for mo in range(1, 13):
    for d in (22, 25, 28, 31):
        o, w = hs.neighbour_month(mo, d, c["pv_day"])
        if d == 25: print("mes", mo, "dia", d, "vecino", o + 1, "w=", round(w, 3))
print("load_how nan:", int(np.isnan(np.array(c["load_how"], float)).sum()), "min:", np.nanmin(c["load_how"]))
print("reg3 forma:", np.array(c["load_reg3"]).shape, "reg1:", np.array(c["load_reg1"]).shape, "nan reg3:", int(np.isnan(np.array(c["load_reg3"], float)).sum()), "nan reg1:", int(np.isnan(np.array(c["load_reg1"], float)).sum()))
print("pv_a:", len(c["pv_a"]), "pv_b:", len(c["pv_b"]), "pv_up:", c["pv_up"], "pv_c:", c["pv_c"])
print("l_lo:", np.round(c["load_lo"], 3)); print("l_lo0:", np.round(c["load_lo0"], 3))
ag = HardBatteryAgent()
nl = ag.policy.netload
print("tipo previsor:", type(nl).__name__, "ok:", nl.ok, "scen_ok:", nl.scen_ok, "z:", nl.z, "z_plan:", nl.z_plan)
