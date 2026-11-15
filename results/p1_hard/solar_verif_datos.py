"""Verificación independiente del candidato 'solar' (HARD MODE): lo que el candidato da por hecho de los datos
(contador congelado de 23 a 5 h, fechas en hora local, horas con el contador a 0) y si sus tablas son finitas.

    python results/p1_hard/solar_verif_datos.py

No se empaqueta. No toca nada del repo.
"""
import sys, json, math
from pathlib import Path
import numpy as np, pandas as pd
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "scripts"))
import p1_hard as bench
from battery.data import validation_mask
t = bench.hard_table().sort_values("timestamp").reset_index(drop=True)
ts = pd.DatetimeIndex(t.timestamp)
val = validation_mask(t).to_numpy()
print("horas:", len(t), "| meses:", sorted(set(ts.to_period("M").astype(str))))
print("días por mes (min-max):", {str(k): (int(v.min()), int(v.max())) for k, v in pd.Series(ts.day, index=ts).groupby(ts.to_period("M"))})
# 1. contador congelado: load[t] == load[t-1] en horas 23, 0..5 (horas seguidas)
prev_ok = np.r_[False, (ts[1:] - ts[:-1]) == pd.Timedelta(hours=1)]
d = t.load_kw.to_numpy() - np.r_[np.nan, t.load_kw.to_numpy()[:-1]]
print("\n1. CONTADOR CONGELADO (consumo de la hora = consumo de la hora anterior)")
for h in (22, 23, 0, 1, 2, 3, 4, 5, 6):
    m = prev_ok & (ts.hour == h) & (t.load_kw.to_numpy() > 0)
    for name, mm in (("todo", m), ("sin val", m & ~val), ("solo val", m & val)):
        x = np.abs(d[mm])
        print(f"   hora {h:2d} {name:8s}: n={mm.sum():3d} | idéntico (<0,01 kW) {100*(x<0.01).mean():5.1f} % | <5 kW {100*(x<5).mean():5.1f} % | dif. media {x.mean():6.1f} | máx {x.max():7.1f}")
# peores noches: diferencia máxima entre la lectura de las 22 h y el consumo de 23..5
print("\n   Peores casos en horas 23 y 0-5 (|dif| > 5 kW):")
m = prev_ok & np.isin(ts.hour, [23, 0, 1, 2, 3, 4, 5]) & (np.abs(d) > 5)
print(pd.DataFrame({"ts": ts[m], "load": t.load_kw[m].round(1).to_numpy(), "dif": d[m].round(1), "val": val[m]}).to_string(index=False)[:1500])
# 2. hora local: centro de la curva solar por mes
print("\n2. CENTRO DE LA CURVA SOLAR POR MES (hora media ponderada por la solar, etiqueta de inicio de hora)")
c = (t.pv_kw * ts.hour).groupby(ts.to_period("M")).sum() / t.pv_kw.groupby(ts.to_period("M")).sum()
print("   " + " | ".join(f"{k}: {v:.2f}" for k, v in c.items()))
# 3. ceros del contador y lecturas raras
z = t.load_kw.to_numpy() == 0
print(f"\n3. Horas con consumo 0 exacto: {int(z.sum())} | en val {int((z & val).sum())} | en dev (días 8-14) {int((z & (ts.day>=8) & (ts.day<=14)).sum())}")
if z.any():
    print("   fechas:", ts[z].min(), "a", ts[z].max(), "| solar x12 en esas horas: máx", round(float(t.pv_kw[z].max()),1))
print("   consumo: min>0 %.1f, p1 %.1f, mediana %.1f, p99 %.1f, máx %.1f" % (t.load_kw[t.load_kw>0].min(), t.load_kw.quantile(.01), t.load_kw.median(), t.load_kw.quantile(.99), t.load_kw.max()))
# 4. tablas finitas
def finite(o):
    if isinstance(o, dict): return all(finite(v) for v in o.values())
    if isinstance(o, (list, tuple)): return all(finite(v) for v in o)
    if isinstance(o, bool) or o is None: return True
    if isinstance(o, (int, float)): return math.isfinite(o)
    return True
make = bench.load_factory(str(REPO / "scripts/p1_lab/hard_solar_cand.py") + ":make")
G = make.__globals__
print("\n4. TABLAS")
for name, ex in (("todo el train", None), ("sin dev", set(bench.split_frame(t, "dev").timestamp)), ("sin val", set(bench.split_frame(t, "val").timestamp))):
    G["PRIOR_CACHE"].clear()
    p = G["to_prior"](ex)
    lo = np.array(p["load_lo"]); up = p["pv_up"]
    print(f"   {name}: todo finito = {finite(p)} | pv_day (centro de los datos) {np.round(p['pv_day'],1).tolist()} | pv_c {p['pv_c']:.2f} | pv_a[0..3] {np.round(p['pv_a'][:4],2).tolist()} | pv_b[0..3] {np.round(p['pv_b'][:4],2).tolist()}")
    print(f"      load_lo por hora (% del perfil): {np.round(100*lo,1).tolist()}")
    print(f"      load_lo0 (sin lectura): {np.round(100*np.array(p['load_lo0']),1).tolist()} | pv_up por tramo: {np.round(up,3).tolist()}")
    print(f"      tamaño JSON: {len(json.dumps(p))/1024:.0f} KB")
