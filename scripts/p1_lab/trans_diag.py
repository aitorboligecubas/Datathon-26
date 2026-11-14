"""Diagnóstico hora a hora de un episodio del banco (para el encargo de transiciones). NO se empaqueta.

    python scripts/p1_lab/trans_diag.py 1008 parcial                 # resumen por semanas
    python scripts/p1_lab/trans_diag.py 1008 parcial --win 170 260   # además, detalle de esas horas
    python scripts/p1_lab/trans_diag.py 1008 parcial --agents v2,v1,scripts/p1_lab/cand_trans.py

Para cada agente da, por semana del episodio, cuántos puntos de score pierde frente al óptimo (la suma
de las 12 semanas es la distancia al óptimo del episodio). Ojo: una semana puede "ganar" al óptimo si
llega a ella con más carga; lo que cuenta es la suma.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from p1_banco import WEEK, _oracle, load_factory, make_episode  # noqa: E402
from battery.sim import baseline_totals, simulate  # noqa: E402

ALIASES = {"v2": "actual", "v1": str(REPO / "scripts" / "p1_lab" / "antes.py")}


def run(df, spec):
    if spec == "opt":
        return simulate(_oracle(df), df).log
    return simulate(load_factory(ALIASES.get(spec, spec))(), df).log


def hourly_points(log, base):
    """Puntos de score que 'cuesta' cada hora (cuanto más alto, peor)."""
    return 70 * log.co2_kg.to_numpy() / base["co2_kg"] + 30 * log.cost_eur.to_numpy() / base["cost_eur"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("seed", type=int)
    ap.add_argument("familia")
    ap.add_argument("--agents", default="v2,v1")
    ap.add_argument("--win", type=int, nargs=2, default=None)
    args = ap.parse_args()
    df = make_episode(args.seed, args.familia)
    base = baseline_totals(df)
    names = ["opt"] + args.agents.split(",")
    logs = {n: run(df, n) for n in names}
    pts = {n: hourly_points(logs[n], base) for n in names}
    short = {n: Path(n).stem.replace("cand_", "") for n in names}
    zero = (df.load_kw.to_numpy() == 0)
    wgt = 70 * df.co2_kg_kwh.to_numpy() / base["co2_kg"] + 30 * df.price_eur_kwh.to_numpy() / base["cost_eur"]
    print(f"episodio seed={args.seed} familia={args.familia}: horas a 0 = {int(zero.sum())}")
    runs = []
    t = 0
    while t < len(df):
        if zero[t]:
            a = t
            while t < len(df) and zero[t]:
                t += 1
            runs.append((a, t))
        else:
            t += 1
    for a, b in runs:
        print(f"   tramo a 0: horas [{a}, {b}) = {b - a} h; semana {a // WEEK}, hora de la semana {a % WEEK}"
              f" a {(b - 1) % WEEK}; fechas {df.timestamp[a]} .. {df.timestamp[b - 1]}")
    head = f"{'sem':>3} {'inicio':>10} {'ceros':>5} {'consumo':>8}"
    for n in names[1:]:
        head += f" {short[n] + ' pierde':>14} {'vert':>6} {'soc fin':>7}"
    head += f" {'opt soc fin':>11}"
    print(head)
    tot = {n: 0.0 for n in names}
    for w in range(len(df) // WEEK):
        sl = slice(w * WEEK, (w + 1) * WEEK)
        ln = f"{w:>3} {str(df.timestamp[w * WEEK].date()):>10} {int(zero[sl].sum()):>5} {df.load_kw[sl].mean():>8.0f}"
        for n in names[1:]:
            d = pts[n][sl].sum() - pts["opt"][sl].sum()
            tot[n] += d
            ln += f" {d:>14.4f} {logs[n].export_kw[sl].sum():>6.0f} {logs[n].soc_kwh.iloc[sl.stop - 1]:>7.0f}"
        ln += f" {logs['opt'].soc_kwh.iloc[sl.stop - 1]:>11.0f}"
        print(ln)
    print("total perdido frente al óptimo: " + "  ".join(f"{short[n]} {tot[n]:.4f}" for n in names[1:]))
    if args.win:
        a, b = args.win
        cols = f"{'t':>5} {'fecha':>16} {'consumo':>8} {'peso':>7}"
        for n in names:
            cols += f" | {short[n][:6] + ' a':>9} {'soc':>5} {'vert':>4}"
        print(cols)
        for t in range(a, min(b, len(df))):
            ln = f"{t:>5} {str(df.timestamp[t])[5:16]:>16} {df.load_kw[t]:>8.0f} {1e4 * wgt[t]:>7.3f}"
            for n in names:
                lg = logs[n]
                ln += f" | {lg.action_kw[t]:>9.0f} {lg.soc_kwh[t]:>5.0f} {lg.export_kw[t]:>4.0f}"
            print(ln)


if __name__ == "__main__":
    main()
