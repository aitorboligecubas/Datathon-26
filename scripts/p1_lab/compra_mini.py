"""Mini-episodios para la compra en una semana sin datos, con el agente real (LP cada hora). NO se empaqueta.

    python scripts/p1_lab/compra_mini.py --alineado actual scripts/p1_lab/antes.py scripts/p1_lab/cand_compra.py
    python scripts/p1_lab/compra_mini.py actual scripts/p1_lab/cand_compra.py:sin_dia_semana

El banco solo pone a cero noviembre (y tres episodios con otra semana). Aquí la semana a cero recorre los
meses de octubre a julio: cada mini-episodio son las semanas del test de los dos meses anteriores (la
historia que tendría el agente), la semana a cero y la del mes siguiente (donde se usa lo comprado), con
sus fechas del test y datos del train de esos meses. Con `--alineado`, cada semana sale solo de ventanas del
train que empiezan el mismo día de la semana que su semana del test.

La pérdida frente al óptimo (el LP con todo conocido) se da en puntos de score de un episodio de 12
semanas, con las referencias medias del train. El primer agente de la lista es la referencia.
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

import p1_banco as B  # noqa: E402
from battery.optimizer import plan, score_weights  # noqa: E402
from battery.sim import simulate  # noqa: E402

CO2_REF, COST_REF = 93.19721939496067, 156.32105608412144    # models/objective_refs.json
HOURS = 2016 - 168                                            # horas con consumo de un episodio con una semana a cero
MONTHS = [s[:7] for s in B.TEST_STARTS]


def build(mi: int, seed: int, aligned: bool) -> pd.DataFrame:
    """Mini-episodio con la semana a cero en el mes MONTHS[mi]."""
    rng = np.random.default_rng(seed)
    src = B._sources()
    idxs = [i for i in (mi - 2, mi - 1, mi, mi + 1) if 0 <= i < 12]
    weeks = []
    for i in idxs:
        g, starts = src[MONTHS[i]]
        if aligned:
            dow = pd.Timestamp(B.TEST_STARTS[i]).dayofweek
            starts = [s for s in starts if g.timestamp[s].dayofweek == dow] or starts
        s = int(rng.choice(starts))
        w = g.iloc[s:s + 168].reset_index(drop=True).copy()
        w["timestamp"] = pd.date_range(B.TEST_STARTS[i], periods=168, freq="h")
        weeks.append(w)
    for j, i in enumerate(idxs):
        if i == B.NOV:       # noviembre no tiene contador: se copia el consumo de una semana vecina, como en el banco
            k = j - 1 if j > 0 else j + 1
            weeks[j]["load_kw"], weeks[j]["pv_kw"] = weeks[k]["load_kw"].to_numpy(), weeks[k]["pv_kw"].to_numpy()
        if i == B.XMAS:      # Navidad: campus cerrado
            weeks[j]["load_kw"] = weeks[j]["load_kw"] * float(rng.choice([0.45, 0.55, 0.65, 0.8]))
    weeks[idxs.index(mi)][["load_kw", "pv_kw"]] = 0.0
    return pd.concat(weeks, ignore_index=True)


def run(job):
    mi, seed, spec, aligned = job
    df = build(mi, seed, aligned)
    w = 100 * (0.7 * df.co2_kg_kwh / (CO2_REF * HOURS) + 0.3 * df.price_eur_kwh / (COST_REF * HOURS)).to_numpy()
    if spec == "opt":
        wc, wk = score_weights(CO2_REF, COST_REF)
        a = plan(1000.0, df.load_kw.to_numpy(), df.pv_kw.to_numpy(), df.price_eur_kwh.to_numpy(), df.co2_kg_kwh.to_numpy(), wc, wk, 0.0)
        return mi, seed, spec, float((np.maximum(df.load_kw.to_numpy() - df.pv_kw.to_numpy() + a, 0.0) * w).sum()), 0
    res = simulate(B.load_factory(spec)(), df)
    return mi, seed, spec, float((res.log.import_kw.to_numpy() * w).sum()), int(res.totals["infractions"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("agents", nargs="+", help="'actual' o ruta/cand.py[:funcion]; el primero es la referencia")
    ap.add_argument("--n", type=int, default=6, help="sorteos por mes")
    ap.add_argument("--alineado", action="store_true", help="respetar el día de la semana del test")
    ap.add_argument("--jobs", type=int, default=2)
    args = ap.parse_args()
    jobs = [(mi, 7000 + 100 * mi + k, spec, args.alineado) for mi in range(1, 11) for k in range(args.n) for spec in args.agents + ["opt"]]
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.jobs) as ex:
        rows = list(ex.map(run, jobs, chunksize=4))
    t = pd.DataFrame(rows, columns=["mi", "seed", "spec", "cost", "infr"])
    t["name"] = t.spec.map(lambda s: s.split(":")[-1] if ":" in s else Path(s).stem)
    cost = t.pivot_table(index=["mi", "seed"], columns="name", values="cost")
    names = [n for n in dict.fromkeys(t.name) if n != "opt"]
    gap = cost[names].sub(cost["opt"], axis=0)
    by_month = gap.groupby(level=0).mean()
    by_month.index = [MONTHS[i] for i in by_month.index]
    pd.set_option("display.width", 200)
    print(f"{len(gap)} mini-episodios ({'día de la semana del test' if args.alineado else 'día de la semana al azar'}) en {time.perf_counter() - t0:.0f} s")
    print("pérdida media frente al óptimo, por mes de la semana a cero (puntos de score):")
    print(by_month.round(4).to_string())
    print("todos   " + "  ".join(f"{n} {gap[n].mean():.4f}" for n in names))
    for n in names[1:]:
        d = gap[names[0]] - gap[n]
        print(f"{n} frente a {names[0]}: {d.mean():+.4f} ± {d.std(ddof=1) / np.sqrt(len(d)):.4f}  "
              f"mejor en {int((d > 1e-4).sum())}, peor en {int((d < -1e-4).sum())} de {len(d)}  [{d.min():+.4f}, {d.max():+.4f}]")
    print("infracciones:", int(t.infr.sum()))
    return 1 if int(t.infr.sum()) else 0


if __name__ == "__main__":
    sys.exit(main())
