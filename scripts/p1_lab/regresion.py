"""Comprueba que un candidato no cambia nada donde no debe. NO se empaqueta.

    python scripts/p1_lab/regresion.py scripts/p1_lab/cand_X.py

Compara el candidato con el agente actual de src/ en los datos estándar (validación, train e histórico
completo, sin semanas inventadas): score con 5 decimales, infracciones y tiempo. También comprueba que
es determinista (dos ejecuciones dan las mismas acciones) y qué importa el fichero.
"""
import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from p1_banco import load_factory  # noqa: E402
from battery.data import load, train_split, validation_split  # noqa: E402
from battery.sim import baseline_totals, score, simulate  # noqa: E402

ALLOWED = {"numpy", "pandas", "scipy", "sklearn", "joblib", "xgboost", "lightgbm", "math", "random", "datetime",
           "collections", "itertools", "json", "pathlib", "typing", "dataclasses", "functools", "heapq", "bisect",
           "re", "copy", "pickle", "battery", "sys"}


def main() -> int:
    spec = sys.argv[1]
    path = spec.partition(":")[0]
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    bad = sorted(mods - ALLOWED)
    print("imports:", sorted(mods), "| NO permitidos:" if bad else "| todos permitidos", bad or "")
    full = load()
    cand, ref = load_factory(spec), load_factory("actual")
    worst = 0.0
    for name, df in (("validación", validation_split(full)), ("train", train_split(full)), ("todo", full)):
        base = baseline_totals(df)
        rc, rr = simulate(cand(), df), simulate(ref(), df)
        sc, sr = score(rc.totals, base), score(rr.totals, base)
        d = sc["score_raw"] - sr["score_raw"]
        worst = min(worst, d)
        print(f"{name:<11} candidato {sc['score_raw']:.5f}  actual {sr['score_raw']:.5f}  dif {d:+.5f}  "
              f"infr {sc['infractions']}  tiempo {rc.totals['runtime_s']:.1f} s ({1000 * rc.totals['runtime_s'] / len(df):.2f} ms/paso)")
        if name == "validación":
            again = simulate(cand(), df)
            same = (again.log.action_req_kw.to_numpy() == rc.log.action_req_kw.to_numpy()).all()
            print(f"{'':<11} determinista: {'sí' if same else 'NO'}")
    print("peor diferencia en datos estándar:", f"{worst:+.5f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
