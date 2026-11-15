"""Como hard_fin_reglas_mascara.py (apartados 1 y 1 bis), pero con las semanas sacadas de la fecha (mes a mes),
para ventanas cuyas semanas no tienen todas 168 h (días 1-7). Sin simular: usa results/hourly/.

    python scripts/p1_lab/hard_fin_reglas_mascara_grupos.py [1-7|val|dev]
"""
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OBJ = 27.98 / 24.15


def main() -> int:
    win = sys.argv[1] if len(sys.argv) > 1 else "1-7"
    d = pickle.load(open(REPO / "results" / "hourly" / f"calcal_{win}.pkl", "rb"))
    b_co2, b_eur = np.asarray(d["base_co2"], float), np.asarray(d["base_eur"], float)
    o = pd.read_csv(REPO / "results" / "hourly" / f"hard_{win}_óptimo__todo_el_futuro.csv", parse_dates=["timestamp"])
    base = np.maximum(o["load_kw"] - o["pv_kw"], 0.0).to_numpy(float)
    assert len(base) == len(b_co2) and abs((base * o["co2_kg_kwh"]).sum() - b_co2.sum()) < 1e-3 * b_co2.sum()
    sav = (base - o["import_kw"].to_numpy(float))
    orc = {"co2": sav * o["co2_kg_kwh"].to_numpy(float), "eur": sav * o["price_eur_kwh"].to_numpy(float)}
    v10 = d["out"]["v10"]
    grp = (o["timestamp"].dt.year * 12 + o["timestamp"].dt.month).to_numpy()
    idx = [np.flatnonzero(grp == g) for g in pd.unique(grp)]
    n = len(base)

    def sc(a, ms):
        return 70.0 * (ms @ a["co2"]) / (ms @ b_co2) + 30.0 * (ms @ a["eur"]) / (ms @ b_eur)

    cont = np.zeros((28, n), bool)
    for j, k in enumerate(range(0, 168, 6)):
        for ix in idx:
            L = len(ix)
            cont[j, ix[((np.arange(L) - k) % L) < L // 2]] = True
    rng = np.random.default_rng(3)
    rnd = np.zeros((3000, n), bool)
    for i in range(3000):
        for ix in idx:
            rnd[i, rng.choice(ix, len(ix) // 2, replace=False)] = True
    full = np.ones((1, n), bool)
    print(f"== Ventana {win}: {n} h, {len(idx)} semanas | entero: v10 {sc(v10, full)[0]:.2f}, óptimo {sc(orc, full)[0]:.2f} ==")
    for name, ms in (("mitad seguida, inicio variable (28)", cont), ("mitad de las horas al azar (3.000)", rnd)):
        sv = sc(v10, ms)
        for lam in (0.5, 0.75, 1.0):
            mix = {k: v10[k] + lam * (orc[k] - v10[k]) for k in ("co2", "eur")}
            rr = sc(mix, ms) / sv
            print(f"  {name:36s} {int(lam * 100):3d} % del camino al óptimo: público/v10 de x{rr.min():.3f} a x{rr.max():.3f} "
                  f"(mediana x{np.median(rr):.3f}); llegan a x{OBJ:.3f}: {100 * (rr >= OBJ).mean():.1f} %")
        print(f"  {name:36s} la v10 en esa mitad: de {sv.min():.2f} a {sv.max():.2f} (desv. típica {sv.std():.2f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
