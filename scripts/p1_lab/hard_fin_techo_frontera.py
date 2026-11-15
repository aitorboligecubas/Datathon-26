"""Revisor del TECHO, 3.ª parte: la frontera de "mover el coste a la otra mitad" con todo el futuro conocido.

El óptimo que solo mira la máscara (peso 0 fuera) es indiferente a lo que pasa fuera y puede derrochar: sus pérdidas
fuera no dicen nada. Aquí lo de fuera pesa `lam` (1 = óptimo honrado, 0,01 = solo desempata): por cada `lam`, cuánto
sube la mitad que se mira y cuánto bajan la otra y el episodio completo. Es para leer el ranking, no para diseñar.

    python scripts/p1_lab/hard_fin_techo_frontera.py val      # también dev, 1-7
"""
import pickle
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
REPO = Path(__file__).resolve().parents[2]
for extra in (str(REPO / "src"), str(REPO / "scripts"), str(REPO / "scripts" / "p1_lab")):
    if extra not in sys.path:
        sys.path.insert(0, extra)
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import p1_hard as B  # noqa: E402

win = sys.argv[1]
OUT = REPO / "results" / "p1_hard"
df = B.split_frame(B.hard_table(), win).reset_index(drop=True)
n = len(df)
ts = pd.DatetimeIndex(df.timestamp)
co2, eur = df.co2_kg_kwh.to_numpy(float), df.price_eur_kwh.to_numpy(float)
base_imp = np.maximum(df.load_kw - df.pv_kw, 0).to_numpy(float)
b_co2, b_eur = base_imp * co2, base_imp * eur
key = (ts.year * 12 + ts.month).to_numpy()
wk = np.concatenate([[0], np.cumsum(key[1:] != key[:-1])])
start = pd.Series(ts).groupby(wk).transform("min")
hw = ((pd.Series(ts) - start).dt.total_seconds() // 3600).to_numpy(int)
cal = pickle.load(open(REPO / "results" / "hourly" / f"calcal_{win}.pkl", "rb"))
v_co2, v_eur = np.asarray(cal["out"]["v10"]["co2"], float), np.asarray(cal["out"]["v10"]["eur"], float)
base = B.baseline_totals(df)
W = B.score_weights(base["co2_kg"] / n, base["cost_eur"] / n)
ALL = np.ones(n, bool)


def nota(s_co2, s_eur, m):
    return 0.7 * 100 * s_co2[m].sum() / b_co2[m].sum() + 0.3 * 100 * s_eur[m].sum() / b_eur[m].sum()


def oracle(keep, lam):
    d = df.copy()
    d.loc[~keep, ["price_eur_kwh", "co2_kg_kwh"]] *= lam
    totals, log = B.simulate_hard(B.OracleAgent(d, *W, p=B.HARD_PARAMS), df)
    imp = log.import_kw.to_numpy(float)
    return (base_imp - imp) * co2, (base_imp - imp) * eur


MASKS = {"1.ª mitad": hw < 84, "2.ª mitad": hw >= 84, "días alternos pares": (hw // 24) % 2 == 0, "días alternos impares": (hw // 24) % 2 == 1,
         "tardes (h 12-23)": (hw // 12) % 2 == 1, "mañanas (h 0-11)": (hw // 12) % 2 == 0, "horas pares": hw % 2 == 0}
rows = []
for name, m in MASKS.items():
    lams = (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.3, 0.1, 0.01) if "mitad" in name else (1.0, 0.9, 0.7, 0.5, 0.01)
    for lam in lams:
        s1, s2 = oracle(m, lam)
        rows.append({"ventana": win, "mascara": name, "lam": lam, "v10_masc": nota(v_co2, v_eur, m), "masc": nota(s1, s2, m),
                     "v10_otra": nota(v_co2, v_eur, ~m), "otra": nota(s1, s2, ~m), "v10_todo": nota(v_co2, v_eur, ALL), "todo": nota(s1, s2, ALL)})
R = pd.DataFrame(rows)
R["coc_v10"] = R.masc / R.v10_masc
for c in ("masc", "otra", "todo"):
    R["d_" + c] = R[c] - R.groupby("mascara")[c].transform("first")      # frente al óptimo honrado (lam = 1)
R["coc_opt"] = R.masc / R.groupby("mascara").masc.transform("first")
R.to_csv(OUT / f"fin_techo_frontera_{win}.csv", index=False)
pd.set_option("display.width", 250)
print(R[["ventana", "mascara", "lam", "v10_masc", "masc", "coc_v10", "coc_opt", "d_masc", "d_otra", "d_todo", "todo", "v10_todo"]].round(3).to_string(index=False))
