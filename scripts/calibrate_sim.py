"""Comprueba que src/battery/sim.py da lo mismo que el simulador oficial.

Owner: P3 (relato e integración).

    python scripts/calibrate_sim.py              # nuestro agente + la plantilla oficial
    python scripts/calibrate_sim.py --hours 336  # más rápido

Ejecuta cada agente en oficial/starter_kit/environment.py y en nuestro sim.py con los
mismos datos de validación y compara el score, el CO2, el coste y las infracciones.
"""
import argparse
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from battery.data import load, validation_split  # noqa: E402
from battery.sim import baseline_totals, score, simulate, to_env_frame  # noqa: E402

KIT = REPO / "oficial" / "starter_kit"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def compare(make_agent, df) -> dict:
    env_mod = load_module("official_env", KIT / "environment.py")
    off = env_mod.run_agent_simulation(make_agent(), to_env_frame(df))
    res = simulate(make_agent(), df)
    ours = score(res.totals, baseline_totals(df))
    return {
        "score": (off["score"], round(ours["score"], 2)),
        "co2%": (off["co2_estalviat_pct"], round(ours["d_co2_pct"], 2)),
        "cost%": (off["cost_estalviat_pct"], round(ours["d_cost_pct"], 2)),
        "infr": (off["infraccions"], ours["infractions"]),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=0, help="usar solo las primeras N horas")
    args = ap.parse_args()
    if not (KIT / "environment.py").exists():
        sys.exit("Falta oficial/starter_kit/environment.py: descomprimid el ZIP oficial en oficial/")
    df = validation_split(load())
    if args.hours:
        df = df.iloc[:args.hours].reset_index(drop=True)

    from battery.policy import BatteryAgent
    template = load_module("official_agent", KIT / "agent.py").BatteryAgent
    ok = True
    print(f"{len(df)} h de validación. (oficial, nuestro)")
    for name, factory in [("plantilla", template), ("mpc", BatteryAgent)]:
        cmp = compare(factory, df)
        same = all(abs(a - b) <= 0.011 for a, b in cmp.values())
        ok &= same
        print(f"  {name:<10} {'OK ' if same else 'DIFERENTE'} {cmp}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
