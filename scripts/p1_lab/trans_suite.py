"""Suite privada del encargo de transiciones (semillas propias: ni las de dev ni las de test). NO se empaqueta.

Mide un candidato contra v1 y v2 en episodios del banco con más peso de las familias del encargo.
Guarda en caché el resultado de cada (agente, semilla, familia) para no repetir simulaciones.

    python scripts/p1_lab/trans_suite.py scripts/p1_lab/cand_trans.py --tag base
    python scripts/p1_lab/trans_suite.py scripts/p1_lab/cand_trans.py:solo_A --tag solo_A --fam dos_ceros,nov0
"""
import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from p1_banco import load_factory, make_episode, masked_score  # noqa: E402
from battery.sim import baseline_totals, score, simulate  # noqa: E402

CACHE = REPO / "results" / "p1_banco" / "trans_cache"
CYCLE = ["nov0", "parcial", "nov0", "parcial", "dos_ceros", "nov0", "averia", "parcial", "cero_otra", "nov0",
         "parcial", "nov0"]
REFS = {"v2": "actual", "v1": str(REPO / "scripts" / "p1_lab" / "antes.py")}


def episodes(n, base=3000):
    return [(base + i, CYCLE[i % len(CYCLE)]) for i in range(n)]


def make_custom(seed, fam):
    """Familias densas propias: varios sucesos por episodio, para medir una pieza con más muestra.

    averia_x   una avería en 6 semanas distintas, de 1, 3, 6, 14, 30 y 60 h (orden y posición al azar)
    parcial_x  4 semanas que empiezan a 0 y recuperan el consumo entre la hora 24 y la 120
    cae_x      4 semanas en las que el contador cae entre la hora 30 y la 140 y ya no vuelve
    """
    df = make_episode(seed, "normal")
    rng = np.random.default_rng(100000 + seed)
    week = 168

    def zero(i, a, b):
        df.loc[i * week + a:i * week + b - 1, ["load_kw", "pv_kw"]] = 0.0

    if fam == "averia_x":
        lengths = rng.permutation([1, 3, 6, 14, 30, 60])
        for i, length in zip([0, 2, 4, 6, 8, 10], lengths):
            a = int(rng.integers(1, week - int(length)))
            zero(i, a, a + int(length))
    elif fam == "parcial_x":
        for i in [1, 4, 7, 10]:
            zero(i, 0, int(rng.integers(24, 121)))
    elif fam == "cae_x":
        for i in [1, 4, 7, 10]:
            zero(i, int(rng.integers(30, 141)), week)
    else:
        raise ValueError(fam)
    return df


def _run(job):
    tag, spec, seed, fam = job
    f = CACHE / f"{tag}_{seed}_{fam}.json"
    if f.exists():
        return json.loads(f.read_text())
    df = make_custom(seed, fam) if fam.endswith("_x") else make_episode(seed, fam)
    half = np.arange(len(df)) < len(df) // 2
    base = baseline_totals(df)
    if spec.startswith("informado"):      # cota superior: conoce la duración de cada tramo a 0
        sys.path.insert(0, str(REPO / "scripts" / "p1_lab"))
        from trans_informado import InformedAgent
        agent = InformedAgent(df, know_exit=spec.endswith("salida"))
    elif spec == "optimo":
        from p1_banco import _oracle
        agent = _oracle(df)
    else:
        agent = load_factory(spec)()
    res = simulate(agent, df)
    sc = score(res.totals, base)
    row = dict(tag=tag, seed=seed, familia=fam, score=sc["score_raw"], mitad1=masked_score(res.log, df, half),
               mitad2=masked_score(res.log, df, ~half), infr=sc["infractions"], vertido=res.totals["export_kwh"],
               tiempo_s=res.totals["runtime_s"])
    f.write_text(json.dumps(row))
    return row


def run(tag, spec, eps, jobs=2):
    CACHE.mkdir(parents=True, exist_ok=True)
    work = [(tag, spec, s, f) for s, f in eps]
    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            rows = list(ex.map(_run, work))
    else:
        rows = [_run(w) for w in work]
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("agent")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--n", type=int, default=36)
    ap.add_argument("--base", type=int, default=3000)
    ap.add_argument("--fam", default="")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--detail", action="store_true")
    args = ap.parse_args()
    fams = [f for f in args.fam.split(",") if f]
    if fams and all(f.endswith("_x") for f in fams):      # familias densas propias: n episodios de cada una
        eps = [(args.base + i, f) for f in fams for i in range(args.n)]
    else:
        eps = [e for e in episodes(args.n, args.base) if not fams or e[1] in fams]
    t0 = time.perf_counter()
    refs = {k: run(k, v, eps, args.jobs) for k, v in REFS.items()}
    cand = run(args.tag, args.agent, eps, args.jobs)
    print(f"{args.tag}: {len(eps)} episodios en {time.perf_counter() - t0:.0f} s; infracciones {int(cand.infr.sum())}; "
          f"t máx {cand.tiempo_s.max():.1f} s")
    m = cand.merge(refs["v2"], on=["seed", "familia"], suffixes=("", "_v2")).merge(
        refs["v1"], on=["seed", "familia"], suffixes=("", "_v1"))
    print(f"{'familia':<10} {'n':>3} {'score':>8} | {'vs v2':>8} {'mín':>8} {'máx':>8} {'m1 vs v2':>9} | {'vs v1':>8} {'mín':>8} {'máx':>8} {'m1 vs v1':>9} | {'vertido':>7}")
    for fam, x in list(m.groupby("familia")) + [("TODOS", m)]:
        d2, d1 = x.score - x.score_v2, x.score - x.score_v1
        print(f"{fam:<10} {len(x):>3} {x.score.mean():>8.4f} | {d2.mean():>+8.4f} {d2.min():>+8.4f} {d2.max():>+8.4f} "
              f"{(x.mitad1 - x.mitad1_v2).mean():>+9.4f} | {d1.mean():>+8.4f} {d1.min():>+8.4f} {d1.max():>+8.4f} "
              f"{(x.mitad1 - x.mitad1_v1).mean():>+9.4f} | {x.vertido.mean():>7.0f}")
    if args.detail:
        m["d_v2"], m["d_v1"] = m.score - m.score_v2, m.score - m.score_v1
        print(m[["seed", "familia", "score", "score_v2", "score_v1", "d_v2", "d_v1", "vertido", "vertido_v2"]].round(4).to_string())


if __name__ == "__main__":
    main()
