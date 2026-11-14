"""¿De dónde viene la distancia al óptimo en las semanas normales con poco consumo? NO se empaqueta.

    python scripts/p1_lab/bajo_diag.py                 # familia normal de la suite dev
    python scripts/p1_lab/bajo_diag.py --seeds 8000:8012 --jobs 2

Para cada episodio mide el agente actual (v2) y variantes que hacen trampa a propósito, cada una con UNA
información que el agente real no tiene, para saber cuánto vale cada cosa:
    R real          los pesos CO2/coste del episodio en vez de los del train
    1.ª hora        en la primera hora de cada semana conoce el consumo de esa hora
    hora actual     conoce el consumo real de la hora actual (previsión y tope de descarga)
    24 h            conoce el consumo real de las próximas 24 h
    24 h + R        las dos cosas: lo que queda hasta el óptimo es ver más allá de 24 h
Y reparte la distancia de v2 entre las 12 semanas (exacto: con "el óptimo a partir de aquí").
"""
import argparse
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "p1_lab"))

import p1_banco as B  # noqa: E402
from bajo_lab import LabPolicy, Wrap, hourly_weights, regret_by_week  # noqa: E402
from battery.sim import baseline_totals, score, simulate  # noqa: E402

VARIANTS = {
    "v2": dict(),
    "R real": dict(true_w=True),
    "1.ª hora": dict(first="true"),
    "hora actual": dict(perfect_fc="now", cap="true"),
    "24 h": dict(perfect_fc="all", cap="none"),
    "24 h + R": dict(perfect_fc="all", cap="none", true_w=True),
}


def one(job):
    seed, familia, with_weeks = job
    df = B.make_episode(seed, familia)
    half = np.arange(len(df)) < len(df) // 2
    base = baseline_totals(df)
    row = {"seed": seed, "familia": familia}
    ores = simulate(B._oracle(df), df)
    row["opt"] = score(ores.totals, base)["score_raw"]
    row["opt_m1"] = B.masked_score(ores.log, df, half)
    row["opt_m2"] = B.masked_score(ores.log, df, ~half)
    weeks = None
    for name, kw in VARIANTS.items():
        res = simulate(Wrap(LabPolicy(df=df, **kw)), df)
        row[name] = score(res.totals, base)["score_raw"]
        row[name + " m1"] = B.masked_score(res.log, df, half)
        row[name + " m2"] = B.masked_score(res.log, df, ~half)
        row[name + " infr"] = res.totals["infractions"]
        if name == "v2" and with_weeks:
            weeks = regret_by_week(res.log, df)
    net = (df.load_kw - df.pv_kw).to_numpy().reshape(12, B.WEEK)
    row["xmas_kw"] = net[B.XMAS].mean()
    row["h<500"] = int((net < 500).sum())
    return row, weeks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="", help="a:b (familia normal); por defecto, los normal de dev")
    ap.add_argument("--familia", default="normal")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--no-weeks", action="store_true")
    args = ap.parse_args()
    if args.seeds:
        a, b = (int(x) for x in args.seeds.split(":"))
        jobs = [(s, args.familia, not args.no_weeks) for s in range(a, b)]
    else:
        jobs = [(s, f, not args.no_weeks) for _, s, f in B.suite("dev") if f == args.familia]
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.jobs) as ex:
        out = list(ex.map(one, jobs))
    rows = pd.DataFrame([r for r, _ in out])
    pd.set_option("display.width", 250)
    print(f"{len(rows)} episodios en {time.perf_counter() - t0:.0f} s")
    names = list(VARIANTS)
    print("\nDistancia al óptimo (score completo) de cada variante:")
    tab = pd.DataFrame({"seed": rows.seed, "Navidad kW": rows.xmas_kw.round(0), "h<500": rows["h<500"]})
    for n in names:
        tab[n] = (rows.opt - rows[n]).round(4)
    print(tab.to_string(index=False))
    print("media".ljust(28) + "  ".join(f"{n}: {(rows.opt - rows[n]).mean():.4f}" for n in names))
    print("\nDistancia al óptimo en la mitad 1 / mitad 2 (medias):")
    for n in names:
        print(f"  {n:<12} m1 {(rows.opt_m1 - rows[n + ' m1']).mean():+.4f}   m2 {(rows.opt_m2 - rows[n + ' m2']).mean():+.4f}"
              f"   infr {int(rows[n + ' infr'].sum())}")
    if not args.no_weeks:
        print("\nDistancia de v2 generada en cada semana (sep ... ago):")
        for (r, wk) in out:
            print(f"  {r['seed']}: " + " ".join(f"{x:7.4f}" for x in wk) + f"   suma {wk.sum():.4f}")
        allw = np.array([wk for _, wk in out])
        print("  media: " + " ".join(f"{x:7.4f}" for x in allw.mean(0)) + f"   suma {allw.mean(0).sum():.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
