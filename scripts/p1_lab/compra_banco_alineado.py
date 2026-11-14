"""Banco de escenarios con el día de la semana BIEN PUESTO. NO se empaqueta.

Owner: P1. Prueba complementaria de scripts/p1_banco.py para el candidato "compra".

Por qué hace falta. p1_banco.py toma para cada semana del test 168 horas del train que empiezan en un
día cualquiera y les pone las fechas del test. El precio y el CO2 de la red dependen mucho del día de la
semana (el valle del sábado y del domingo es un 18 % más barato que el de un laborable), así que en ese
banco el fin de semana "de los datos" cae en un sitio al azar de la semana, y no donde dice la fecha. En el
test real la semana de noviembre va de lunes 24 a domingo 30: el fin de semana está al final.

Para decidir CUÁNDO comprar en una semana sin datos eso lo cambia todo: esperar al último día es bueno si
el último día es domingo y malo si es un miércoles. Este banco construye los mismos episodios, pero cada
semana se toma solo de ventanas del train que empiezan el mismo día de la semana que la semana del test
(2 o 3 ventanas por mes). Los escenarios, las familias y las columnas son los de p1_banco.py.

    python scripts/p1_lab/compra_banco_alineado.py --suite dev                       # agente actual
    python scripts/p1_lab/compra_banco_alineado.py --suite dev --agent scripts/p1_lab/cand_compra.py \
        --ref results/p1_banco/compra_alineado_dev_actual.csv --out results/p1_banco/compra_alineado_dev.csv
"""
import argparse
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import p1_banco as B  # noqa: E402


def align_sources() -> dict:
    """Deja en cada mes solo los inicios que caen en el mismo día de la semana que su semana del test."""
    if B._CACHE.get("alineado"):
        return B._CACHE["src"]
    src = B._sources()
    out = {}
    for start in B.TEST_STARTS:
        month = start[:7]
        g, starts = src[month]
        dow = pd.Timestamp(start).dayofweek
        keep = [s for s in starts if g.timestamp[s].dayofweek == dow]
        out[month] = (g, keep or starts)
    for month in src:
        out.setdefault(month, src[month])
    B._CACHE["src"] = out
    B._CACHE["alineado"] = True
    return out


def _run_one(job):
    align_sources()
    return B._run_one(job)


def evaluate(agent_spec: str, suite_name: str, jobs: int = 2, only=None, with_oracle: bool = True) -> pd.DataFrame:
    eps = [e for e in B.suite(suite_name) if not only or e[2] in only]
    work = [(i, s, f, agent_spec, with_oracle) for i, s, f in eps]
    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            rows = list(ex.map(_run_one, work))
    else:
        rows = [_run_one(w) for w in work]
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suite", default="dev", choices=list(B.SUITE_SEEDS))
    ap.add_argument("--agent", default="actual", help="'actual' o ruta/cand.py[:funcion]")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--only", default="", help="familias separadas por comas")
    ap.add_argument("--ref", default="", help="CSV de otro resultado con el que comparar")
    ap.add_argument("--out", default="", help="CSV donde guardar el resultado")
    ap.add_argument("--no-oracle", action="store_true", help="no calcular el óptimo (más rápido)")
    ap.add_argument("--ventanas", action="store_true", help="solo listar las ventanas alineadas de cada mes")
    args = ap.parse_args()
    if args.ventanas:
        for month, (g, starts) in align_sources().items():
            if month in [s[:7] for s in B.TEST_STARTS]:
                print(month, [str(g.timestamp[s].date()) for s in starts])
        return 0
    only = [f for f in args.only.split(",") if f] or None
    t0 = time.perf_counter()
    df = evaluate(args.agent, args.suite, args.jobs, only, not args.no_oracle)
    ref = pd.read_csv(args.ref) if args.ref else None
    if ref is not None and "opt" not in df and "opt" in ref:
        df = df.merge(ref[["id", "opt", "opt_mitad1", "opt_mitad2"]], on="id", how="left")   # el óptimo no depende del agente
    print(f"banco alineado, suite {args.suite}, agente {args.agent}: {len(df)} episodios en {time.perf_counter() - t0:.0f} s")
    print(B.summary(df, ref))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(args.out, index=False)
        print(f"guardado en {args.out}")
    return 1 if int(df.infr.sum()) else 0


if __name__ == "__main__":
    sys.exit(main())
