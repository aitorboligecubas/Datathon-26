"""El público es "el 50 % de cada semana de test" (FAQ de la web). ¿Qué mitad? Con los registros hora a hora del
banco (python scripts/p1_lab/hard_publico_por_mes.py <ventana>), diferencia entre variantes en varias máscaras
posibles dentro de cada semana, para compararla con la de la web:
    web: margen 1,0 - 1,4 = +0,045 | v12 - v10 = -0,04 | semilla = +0,04
"""
import pickle
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "results" / "hourly"
rng = np.random.default_rng(1)
PAIRS = (("z10", "z14"), ("v12", "z10"), ("z10", "z10_sin_semilla"))
tot = {}
for win in ("val", "dev", "1-7"):
    f = OUT / f"publico_por_mes_{win}.pkl"
    if not f.exists():
        continue
    d = pickle.load(open(f, "rb"))
    out, base, df = d["out"], d["base"], d["df"]
    n = len(df)
    hw = np.arange(n) % 168                      # hora dentro de la semana (cada ventana son semanas de 168 h seguidas)
    day = hw // 24

    def score(name, mask):
        return (70 * out[name].co2.to_numpy()[mask].sum() / base.co2.to_numpy()[mask].sum()
                + 30 * out[name].eur.to_numpy()[mask].sum() / base.eur.to_numpy()[mask].sum())

    masks = {"todo": np.ones(n, bool), "primera mitad (h 0-83)": hw < 84, "segunda mitad (h 84-167)": hw >= 84,
             "días pares (0,2,4,6)": day % 2 == 0, "días impares (1,3,5)": day % 2 == 1,
             "horas pares": hw % 2 == 0, "horas impares": hw % 2 == 1}
    print(f"== {win}")
    for label, m in masks.items():
        row = "  ".join(f"{a}-{b} {score(a, m) - score(b, m):+.3f}" for a, b in PAIRS)
        print(f"   {label:26s} score v12 {score('v12', m):6.3f} | {row}")
        for a, b in PAIRS:
            tot.setdefault((label, a, b), []).append(score(a, m) - score(b, m))
print("== media de las ventanas")
for label in ("todo", "primera mitad (h 0-83)", "segunda mitad (h 84-167)", "días pares (0,2,4,6)", "días impares (1,3,5)", "horas pares", "horas impares"):
    print(f"   {label:26s} " + "  ".join(f"{a}-{b} {np.mean(tot[(label, a, b)]):+.3f}" for a, b in PAIRS))
