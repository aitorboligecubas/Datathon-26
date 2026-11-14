"""Banco de escenarios con el calendario del test oficial. NO se empaqueta.

Owner: P1 (optimización y robustez).

Mide cualquier agente contra muchos episodios de 2.016 h construidos como el test: 12 semanas (los
últimos 7 días de cada mes, de septiembre de 2025 a agosto de 2026) puestas una detrás de otra. Los
datos de cada semana son 168 horas seguidas del train de ese mismo mes, elegidas al azar.

Familias de escenarios (columna `familia`):
    normal     todas las semanas con datos; Navidad con el consumo reducido
    nov0       noviembre con el contador a 0 toda la semana (en el train, noviembre no tiene contador)
    cero_otra  la semana a 0 es otra (incluidas la primera y la última)
    parcial    semana a 0 solo en parte (los primeros días, o desde mitad de semana)
    averia     avería corta a mitad de semana (de 1 a 60 horas con el contador a 0)
    dos_ceros  dos semanas seguidas a 0

Para cada episodio se guarda el score completo y el de cada mitad (primeras y últimas 1.008 h, como el
ranking público y el privado), el del óptimo con información perfecta, infracciones, vertido y tiempo.

    python scripts/p1_banco.py --suite dev                         # agente actual de src/
    python scripts/p1_banco.py --suite dev --agent ruta/cand.py    # un candidato (define make_agent())
    python scripts/p1_banco.py --suite test --agent ruta/cand.py --ref results/p1_banco/test_actual.csv
    python scripts/p1_banco.py --suite dev --only nov0,averia      # solo algunas familias

`--ref` compara episodio a episodio con otro resultado guardado. Suites: `dev` para desarrollar y
`test` (otras semillas) para juzgar sin haber mirado; `mini` es una prueba rápida.
"""
import argparse
import importlib.util
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from battery.baselines import OracleAgent  # noqa: E402
from battery.data import TRAIN_DIR, ensure_official, load  # noqa: E402
from battery.optimizer import score_weights  # noqa: E402
from battery.sim import baseline_totals, score, simulate  # noqa: E402

OUT_DIR = REPO / "results" / "p1_banco"
WEEK = 168
TEST_STARTS = ["2025-09-24", "2025-10-25", "2025-11-24", "2025-12-25", "2026-01-25", "2026-02-22",
               "2026-03-25", "2026-04-24", "2026-05-25", "2026-06-24", "2026-07-25", "2026-08-25"]
NOV = 2      # índice de la semana de noviembre
XMAS = 3     # índice de la semana de Navidad
SUITE_SEEDS = {"mini": (900, 6), "dev": (1000, 36), "test": (5000, 60)}
FAMILY_CYCLE = ["nov0", "nov0", "nov0", "normal", "normal", "averia", "averia", "cero_otra", "parcial",
                "nov0", "averia", "dos_ceros"]


# ------------------------------------------------------------------------- datos de partida
_CACHE = {}


def _sources():
    """Por mes: tabla horaria del train y lista de inicios válidos (168 h seguidas desde las 00:00)."""
    if "src" in _CACHE:
        return _CACHE["src"]
    ensure_official()
    full = load()
    out = {}
    for m, g in full.groupby(full.timestamp.dt.to_period("M")):
        g = g.reset_index(drop=True)
        ts = g.timestamp
        starts = [s for s in range(len(g) - WEEK + 1)
                  if ts[s].hour == 0 and ts[s + WEEK - 1] - ts[s] == pd.Timedelta(hours=WEEK - 1)]
        out[str(m)] = (g, starts)
    pr = pd.read_csv(TRAIN_DIR / "precio_pvpc.csv", parse_dates=["Fecha"]).set_index("Fecha")
    co = pd.read_csv(TRAIN_DIR / "co2_red.csv", parse_dates=["Fecha"]).set_index("Fecha")
    hours = pd.date_range("2025-11-01", "2025-11-23 23:00", freq="h")
    nov = pd.DataFrame({"timestamp": hours, "load_kw": np.nan, "pv_kw": np.nan,
                        "price_eur_kwh": pr.precio_eur_per_kwh.reindex(hours).to_numpy(),
                        "co2_kg_kwh": co.co2_kg_per_kwh.reindex(hours).to_numpy()})
    out["2025-11"] = (nov, [s for s in range(0, len(nov) - WEEK + 1, 24)])
    _CACHE["src"] = out
    return out


def make_episode(seed: int, familia: str) -> pd.DataFrame:
    """Un episodio de 2.016 h con las fechas del test. Determinista dado (seed, familia)."""
    rng = np.random.default_rng(seed)
    src = _sources()
    weeks = []
    for start in TEST_STARTS:
        g, starts = src[start[:7]]
        s = int(rng.choice(starts))
        w = g.iloc[s:s + WEEK].reset_index(drop=True).copy()
        w["timestamp"] = pd.date_range(start, periods=WEEK, freq="h")
        weeks.append(w)
    # Noviembre no tiene contador: por defecto copia el consumo de la semana de octubre elegida.
    weeks[NOV]["load_kw"] = weeks[1]["load_kw"].to_numpy()
    weeks[NOV]["pv_kw"] = weeks[1]["pv_kw"].to_numpy()
    # Navidad: campus cerrado.
    weeks[XMAS]["load_kw"] = weeks[XMAS]["load_kw"] * float(rng.choice([0.45, 0.55, 0.65, 0.8]))

    def zero(i, a=0, b=WEEK):
        weeks[i].loc[a:b - 1, ["load_kw", "pv_kw"]] = 0.0

    if familia == "nov0":
        zero(NOV)
    elif familia == "cero_otra":
        zero(int(rng.choice([0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11])))
    elif familia == "parcial":
        i = int(rng.choice([1, 2, 4, 6, 8, 10]))
        if rng.random() < 0.5:
            zero(i, 0, int(rng.integers(24, 120)))            # sin datos los primeros días
        else:
            zero(i, int(rng.integers(30, 140)), WEEK)         # se cae a mitad de semana y no vuelve
    elif familia == "averia":
        for _ in range(int(rng.integers(1, 4))):
            i = int(rng.integers(0, 12))
            length = int(rng.choice([1, 1, 3, 6, 14, 30, 60]))
            a = int(rng.integers(1, WEEK - length))
            zero(i, a, a + length)
    elif familia == "dos_ceros":
        i = int(rng.choice([1, 2, 5, 8]))
        zero(i)
        zero(i + 1)
    elif familia != "normal":
        raise ValueError(familia)
    return pd.concat(weeks, ignore_index=True)


def suite(name: str) -> list:
    """Lista de (id, seed, familia) de una suite."""
    base, n = SUITE_SEEDS[name]
    return [(f"{name}-{i:02d}", base + i, FAMILY_CYCLE[i % len(FAMILY_CYCLE)]) for i in range(n)]


# ------------------------------------------------------------------------------ evaluación
def masked_score(log, df, mask):
    """Como evaluate_results(mask=...) del simulador oficial: solo cuentan las horas de la máscara."""
    base = np.maximum((df.load_kw - df.pv_kw).to_numpy(), 0.0)
    co2b = (base * df.co2_kg_kwh.to_numpy())[mask].sum()
    costb = (base * df.price_eur_kwh.to_numpy())[mask].sum()
    co2 = log.co2_kg.to_numpy()[mask].sum()
    cost = log.cost_eur.to_numpy()[mask].sum()
    return 70 * (1 - co2 / co2b) + 30 * (1 - cost / costb)


def load_factory(spec: str):
    """'actual' -> BatteryAgent de src/; 'ruta.py' o 'ruta.py:func' -> func() (por defecto make_agent)."""
    if spec in ("actual", "", None):
        from battery.policy import BatteryAgent
        return BatteryAgent
    path, _, func = spec.partition(":")
    mod_spec = importlib.util.spec_from_file_location("candidato_" + Path(path).stem, path)
    mod = importlib.util.module_from_spec(mod_spec)
    mod_spec.loader.exec_module(mod)
    return getattr(mod, func or "make_agent")


def _oracle(df):
    b = baseline_totals(df)
    return OracleAgent(df, *score_weights(b["co2_kg"] / len(df), b["cost_eur"] / len(df)))


def _run_one(job):
    ep_id, seed, familia, agent_spec, with_oracle = job
    df = make_episode(seed, familia)
    half = np.arange(len(df)) < len(df) // 2
    base = baseline_totals(df)
    row = {"id": ep_id, "seed": seed, "familia": familia}
    t0 = time.perf_counter()
    agent = load_factory(agent_spec)()
    res = simulate(agent, df, init_s=time.perf_counter() - t0)
    sc = score(res.totals, base)
    row.update(score=sc["score_raw"], mitad1=masked_score(res.log, df, half), mitad2=masked_score(res.log, df, ~half),
               infr=sc["infractions"], vertido=res.totals["export_kwh"], tiempo_s=res.totals["runtime_s"])
    if with_oracle:
        ores = simulate(_oracle(df), df)
        osc = score(ores.totals, base)
        row.update(opt=osc["score_raw"], opt_mitad1=masked_score(ores.log, df, half),
                   opt_mitad2=masked_score(ores.log, df, ~half))
    return row


def evaluate(agent_spec: str, suite_name: str, jobs: int = 2, only=None, with_oracle: bool = True) -> pd.DataFrame:
    eps = [e for e in suite(suite_name) if not only or e[2] in only]
    work = [(i, s, f, agent_spec, with_oracle) for i, s, f in eps]
    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            rows = list(ex.map(_run_one, work))
    else:
        rows = [_run_one(w) for w in work]
    return pd.DataFrame(rows)


def summary(df: pd.DataFrame, ref: pd.DataFrame = None) -> str:
    lines = []
    cols = ["score", "mitad1", "mitad2"]
    g = df.groupby("familia")
    head = f"{'familia':<10} {'n':>3} {'score':>8} {'mitad1':>8} {'mitad2':>8}"
    if "opt" in df:
        head += f" {'a óptimo':>9} {'m1 a ópt':>9} {'m2 a ópt':>9}"
    head += f" {'infr':>5} {'vertido':>8} {'t máx':>6}"
    lines.append(head)
    for fam, x in list(g) + [("TODOS", df)]:
        ln = f"{fam:<10} {len(x):>3} " + " ".join(f"{x[c].mean():>8.4f}" for c in cols)
        if "opt" in x:
            ln += (f" {(x.opt - x.score).mean():>9.4f} {(x.opt_mitad1 - x.mitad1).mean():>9.4f}"
                   f" {(x.opt_mitad2 - x.mitad2).mean():>9.4f}")
        ln += f" {int(x.infr.sum()):>5d} {x.vertido.mean():>8.0f} {x.tiempo_s.max():>6.1f}"
        lines.append(ln)
    if ref is not None:
        m = df.merge(ref, on=["id", "seed", "familia"], suffixes=("", "_ref"))
        lines.append("")
        lines.append(f"Diferencia con la referencia, episodio a episodio ({len(m)} comunes): media [mín, máx]")
        for fam, x in list(m.groupby("familia")) + [("TODOS", m)]:
            parts = []
            for c in cols:
                d = x[c] - x[c + "_ref"]
                parts.append(f"{c} {d.mean():+.4f} [{d.min():+.4f}, {d.max():+.4f}]")
            lines.append(f"{fam:<10} " + "   ".join(parts))
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suite", default="dev", choices=list(SUITE_SEEDS))
    ap.add_argument("--agent", default="actual", help="'actual' o ruta/cand.py[:funcion]")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--only", default="", help="familias separadas por comas")
    ap.add_argument("--ref", default="", help="CSV de otro resultado con el que comparar")
    ap.add_argument("--out", default="", help="CSV donde guardar el resultado")
    ap.add_argument("--no-oracle", action="store_true", help="no calcular el óptimo (más rápido)")
    args = ap.parse_args()
    only = [f for f in args.only.split(",") if f] or None
    t0 = time.perf_counter()
    df = evaluate(args.agent, args.suite, args.jobs, only, not args.no_oracle)
    ref = pd.read_csv(args.ref) if args.ref else None
    print(f"suite {args.suite}, agente {args.agent}: {len(df)} episodios en {time.perf_counter() - t0:.0f} s")
    print(summary(df, ref))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(args.out, index=False)
        print(f"guardado en {args.out}")
    return 1 if int(df.infr.sum()) else 0


if __name__ == "__main__":
    sys.exit(main())
