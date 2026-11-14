"""Ganancia por mes de una variante frente a otra (rama mejora-score-hard). NO se empaqueta.
El score es lineal en lo que se compra: la contribución de cada hora es -compra * peso, con los pesos de la ventana."""
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
for extra in (str(REPO / "src"), str(REPO / "scripts"), str(REPO / "scripts" / "p1_lab")):
    sys.path.insert(0, extra)
import p1_hard as bench  # noqa: E402
import mejora_grid as g  # noqa: E402
from battery.sim import baseline_totals  # noqa: E402

STATE = {}


def zf(z, zp=None):
    def f(prior, sp, ex):
        a = bench.hard_agent(prior, sp)
        a.policy.netload.z = z
        a.policy.netload.z_plan = z if zp is None else zp
        return a
    return f


VARS = {"z1.4": zf(1.4), "z1.0": zf(1.0), "z0.7": zf(0.7), "z1.2": zf(1.2)}


def run(args):
    w, name = args
    df, prior, sp, ex = STATE[w]
    tot, log = bench.simulate_hard(VARS[name](prior, sp, ex), df)
    b = baseline_totals(df)
    wt = 100 * (0.7 * df.co2_kg_kwh / b["co2_kg"] + 0.3 * df.price_eur_kwh / b["cost_eur"])
    contrib = -(log.import_kw * wt) + (np.maximum(df.load_kw - df.pv_kw, 0) * wt)
    return w, name, pd.Series(contrib.to_numpy(), index=df.timestamp.dt.month.to_numpy()).groupby(level=0).sum()


if __name__ == "__main__":
    windows = sys.argv[1].split(",") if len(sys.argv) > 1 else ["val", "3-9", "8-14", "15-21"]
    for w in windows:
        STATE[w] = g.prepare(w)
    with Pool(4) as p:
        res = p.map(run, [(w, n) for w in windows for n in VARS])
    tab = {}
    for w, n, s in res:
        tab[(w, n)] = s
    for n in VARS:
        if n == "z1.4":
            continue
        d = pd.DataFrame({w: tab[(w, n)] - tab[(w, "z1.4")] for w in windows})
        d["media"] = d.mean(axis=1)
        print(f"\n{n} - z1.4 por mes (puntos de score de la ventana)")
        print(d.round(3).to_string())
        inv = d.loc[[m for m in d.index if m in (9, 10, 11, 12, 1, 2)]].sum()
        ver = d.loc[[m for m in d.index if m in (3, 4, 5, 6, 7, 8)]].sum()
        print("  invierno (sep-feb):", inv.round(3).to_dict())
        print("  verano (mar-ago):  ", ver.round(3).to_dict())
