"""Único comando de evaluación del equipo. Nadie dice "me mejora" sin pasar por aquí.

Owner: INTEGRADOR.

Evalúa sobre la validación (últimas 168 h de cada mes del train, seguidas, como
el test oficial) con el simulador local (src/battery/sim.py).

    python eval.py                     # agente actual (src/) contra la referencia
    python eval.py --agent all         # nothing, greedy, mpc y oracle (techo teórico)
    python eval.py --agent dist        # el dist/agent.py empaquetado
    python eval.py --fc-noise 0.1      # previsiones de precio/CO2 con ruido
    python eval.py --quick             # solo 2 semanas (CI, pruebas rápidas)
    python eval.py --log "nota"        # añade una fila a results/experiments.csv
    python eval.py --save-hourly       # guarda el log hora a hora en results/hourly/
    python eval.py --strict            # sale con error si hay infracciones o se pasa de tiempo
"""
import argparse
import csv
import importlib.util
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "src"))

from battery.baselines import GreedyAgent, NothingAgent, OracleAgent  # noqa: E402
from battery.data import is_synthetic, load, validation_split  # noqa: E402
from battery.optimizer import score_weights  # noqa: E402
from battery.params import TIME_BUDGET_S, TIME_LIMIT_S  # noqa: E402
from battery.sim import baseline_totals, score, simulate  # noqa: E402

EXPERIMENTS = REPO / "results" / "experiments.csv"
EXP_COLUMNS = ["fecha_utc", "rama", "commit", "agente", "datos", "fc_noise", "pasos", "score",
               "d_co2_pct", "d_cost_pct", "infracciones", "runtime_s", "nota"]


def load_dist_agent():
    path = REPO / "dist" / "agent.py"
    if not path.exists():
        sys.exit("No existe dist/agent.py: ejecuta antes  python scripts/build_submission.py")
    spec = importlib.util.spec_from_file_location("dist_agent", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.BatteryAgent()


def make_agent(name: str, df):
    if name == "nothing":
        return NothingAgent()
    if name == "greedy":
        return GreedyAgent()
    if name == "mpc":
        from battery.policy import BatteryAgent
        return BatteryAgent()
    if name == "dist":
        return load_dist_agent()
    if name == "oracle":
        base = baseline_totals(df)
        n = len(df)
        return OracleAgent(df, *score_weights(base["co2_kg"] / n, base["cost_eur"] / n))
    raise ValueError(name)


def git(*args) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True,
                              timeout=5).stdout.strip()
    except Exception:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--agent", default="mpc", choices=["mpc", "dist", "greedy", "nothing", "oracle", "all"])
    ap.add_argument("--fc-noise", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--log", metavar="NOTA", help="añade el resultado a results/experiments.csv")
    ap.add_argument("--save-hourly", action="store_true")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    df = validation_split(load())
    if args.quick:
        df = df.iloc[:336].reset_index(drop=True)
    data_kind = "sintéticos" if is_synthetic() else "oficiales"
    base = baseline_totals(df)
    names = ["nothing", "greedy", "mpc", "oracle"] if args.agent == "all" else [args.agent]

    print(f"Datos {data_kind}: {len(df)} h de validación ({df.timestamp.iloc[0]:%Y-%m-%d} → "
          f"{df.timestamp.iloc[-1]:%Y-%m-%d}), fc_noise={args.fc_noise}")
    if data_kind == "sintéticos":
        print("  (OJO: datos sintéticos; sirven para probar el circuito, no para decidir)")
    print(f"{'agente':<8} {'score':>7} {'ΔCO2%':>7} {'ΔCoste%':>8} {'infr.':>6} {'tiempo':>8}")

    failed = False
    for name in names:
        t0 = time.perf_counter()
        agent = make_agent(name, df)
        init_s = time.perf_counter() - t0
        res = simulate(agent, df, fc_noise=args.fc_noise, seed=args.seed, init_s=init_s)
        sc = score(res.totals, base)
        rt = res.totals["runtime_s"]
        flag = " ⚠ tiempo" if rt > TIME_BUDGET_S else ""
        print(f"{name:<8} {sc['score']:>7.2f} {sc['d_co2_pct']:>7.2f} {sc['d_cost_pct']:>8.2f} "
              f"{sc['infractions']:>6d} {rt:>7.1f}s{flag}")

        if name in ("mpc", "dist"):
            # El runtime escala con las horas: lo proyectamos a las 2.016 del test.
            projected = rt * 2016 / len(df)
            if projected > TIME_BUDGET_S:
                print(f"  ⚠ proyectado a 2.016 h: {projected:.1f} s (límite interno {TIME_BUDGET_S:.0f} s, "
                      f"oficial {TIME_LIMIT_S:.0f} s)")
                failed = True
            if sc["infractions"] > 0:
                failed = True

        if args.save_hourly:
            out = REPO / "results" / "hourly" / f"{name}.csv"
            out.parent.mkdir(parents=True, exist_ok=True)
            res.log.to_csv(out, index=False)
            print(f"  log hora a hora: {out.relative_to(REPO)}")

        if args.log is not None:
            new = not EXPERIMENTS.exists()
            EXPERIMENTS.parent.mkdir(parents=True, exist_ok=True)
            with open(EXPERIMENTS, "a", newline="") as fh:
                w = csv.writer(fh)
                if new:
                    w.writerow(EXP_COLUMNS)
                w.writerow([datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
                            git("rev-parse", "--abbrev-ref", "HEAD"), git("rev-parse", "--short", "HEAD"),
                            name, data_kind, args.fc_noise, len(df), f"{sc['score']:.3f}",
                            f"{sc['d_co2_pct']:.3f}", f"{sc['d_cost_pct']:.3f}", sc["infractions"],
                            f"{rt:.2f}", args.log])

    if args.log is not None:
        print(f"Resultado añadido a {EXPERIMENTS.relative_to(REPO)}")
    if args.strict and failed:
        print("FALLO (--strict): infracciones o tiempo por encima del límite interno.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
