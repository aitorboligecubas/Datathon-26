"""Banco rápido de la rama `mejora-score-hard`: varias configuraciones en varias ventanas, en paralelo. NO se empaqueta.

Para cada ventana se ajusta todo SIN sus horas (como scripts/p1_hard.py) y se simula cada candidato.
Imprime el score de cada candidato y su diferencia con "base" (el agente actual) en cada ventana.

    python scripts/p1_lab/mejora_grid.py scripts/p1_lab/mejora_cands.py --windows val,1-7,8-14,15-21
"""
import argparse
import importlib.util
import os
import sys
from multiprocessing import Pool
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import p1_hard as bench  # noqa: E402
from battery.sim import baseline_totals, score  # noqa: E402

STATE = {}


def load_module(path):
    spec = importlib.util.spec_from_file_location("cands_" + Path(path).stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def prepare(window: str):
    full = bench.hard_table()
    df = bench.split_frame(full, window)
    exclude = set(df.timestamp)
    fit_df = full[~full.timestamp.isin(exclude)]
    return df, bench.fit_market(exclude, fit_df), bench.fit_solar(fit_df), exclude


def run_one(args):
    window, name = args
    df, prior, solar_prior, exclude = STATE[window]
    factory = STATE["cands"][name]
    ag = factory(prior, solar_prior, exclude)
    totals, log = bench.simulate_hard(ag, df)
    sc = score(totals, baseline_totals(df))
    return window, name, sc["score_raw"], sc["infractions"], totals["export_kwh"], totals["runtime_s"] / len(df) * 1000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cands", help="fichero .py con un dict CANDS = {nombre: fábrica(prior, solar_prior, exclude)}")
    ap.add_argument("--windows", default="val,1-7,8-14,15-21")
    ap.add_argument("--only", default="", help="candidatos separados por comas (base siempre entra)")
    ap.add_argument("--procs", type=int, default=os.cpu_count() or 2)
    args = ap.parse_args()
    mod = load_module(args.cands)
    cands = dict(mod.CANDS)
    if args.only:
        keep = set(args.only.split(",")) | {"base"}
        cands = {k: v for k, v in cands.items() if k in keep}
    windows = args.windows.split(",")
    STATE["cands"] = cands
    for w in windows:
        STATE[w] = prepare(w)
    jobs = [(w, n) for w in windows for n in cands]
    with Pool(args.procs) as pool:        # fork: los hijos heredan STATE
        res = pool.map(run_one, jobs)
    t = pd.DataFrame(res, columns=["ventana", "cand", "score", "infr", "vertido", "ms"])
    piv = t.pivot(index="cand", columns="ventana", values="score")[windows]
    diff = piv.sub(piv.loc["base"], axis=1)
    diff["media"] = diff.mean(axis=1)
    diff["peor"] = diff[windows].min(axis=1)
    out = piv.round(3).astype(str) + " (" + diff[windows].round(3).map(lambda v: f"{v:+.3f}") + ")"
    out["media"] = diff["media"].map(lambda v: f"{v:+.3f}")
    out["peor"] = diff["peor"].map(lambda v: f"{v:+.3f}")
    out["infr"] = t.groupby("cand").infr.sum()
    out["ms"] = t.groupby("cand").ms.max().round(1)
    print(out.sort_values("media", key=lambda s: s.str.replace("+", "").astype(float), ascending=False).to_string())


if __name__ == "__main__":
    main()
