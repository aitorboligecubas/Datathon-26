"""Empaqueta el agente en un único dist/agent.py y genera dist/submission.zip.

Owner: INTEGRADOR.

Por qué: el servidor solo carga agent.py y no deja importar módulos hermanos
(ni sys, ni importlib, ni os). Así que juntamos los módulos del agente en un
solo fichero, quitando los imports relativos, y comprobamos:
  1. Que solo se importan librerías permitidas.
  2. Que dos módulos no definen el mismo nombre (se pisarían al concatenar).
  3. Que el ZIP (agent.py + artefactos de models/ en la raíz) pesa <= 25 MB.
  4. Que dist/agent.py, ejecutado aislado del repo, da las mismas acciones que src/.
  5. Que pasa oficial/starter_kit/check_submission.py (si tenéis el ZIP oficial descomprimido).

Uso:
    python scripts/build_submission.py            # genera y comprueba
    python scripts/build_submission.py --no-smoke # sin la prueba aislada
"""
import argparse
import ast
import json
import pickle
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "battery"
MODELS = REPO / "models"
DIST = REPO / "dist"

# Orden de concatenación: cada módulo solo puede usar los anteriores.
BUNDLE_MODULES = ["params", "obs", "adapter", "safety", "forecaster", "optimizer", "policy"]
# Permitidas según oficial/docs/ENUNCIAT.md (somos más estrictos que check_submission.py,
# que solo veta una lista negra).
ALLOWED_IMPORTS = {
    "numpy", "pandas", "scipy", "sklearn", "joblib", "xgboost", "lightgbm",
    "math", "random", "datetime", "collections", "itertools", "json", "pathlib", "typing",
    "dataclasses", "functools", "heapq", "bisect", "re", "copy", "pickle",
}
# Llamadas, builtins y atributos que veta el escáner AST oficial (check_submission.py).
FORBIDDEN_CALLS = {"system", "popen", "spawn", "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv",
                   "spawnve", "spawnvp", "spawnvpe", "rmtree", "get_objects", "currentframe", "stack"}
FORBIDDEN_BUILTINS = {"eval", "exec", "__import__", "compile", "breakpoint", "globals", "locals", "vars"}
FORBIDDEN_ATTRS = {"f_back", "f_locals", "f_globals", "__subclasses__", "__builtins__", "__globals__",
                   "__code__"}
OFFICIAL_CHECKER = REPO / "oficial" / "starter_kit" / "check_submission.py"
MODEL_SUFFIXES = {".json", ".pkl", ".joblib", ".npy", ".npz"}
MAX_ZIP_MB = 25.0


class BundleError(Exception):
    pass


def _top_names(tree: ast.Module) -> set:
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                for n in ast.walk(tgt):
                    if isinstance(n, ast.Name):
                        names.add(n.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def bundle() -> str:
    imports = {}        # nombre ligado -> sentencia de import
    import_lines = []   # en orden de aparición, sin duplicados
    defined = {}        # nombre -> módulo que lo define
    bodies = []
    for mod in BUNDLE_MODULES:
        path = SRC / (mod + ".py")
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        lines = src.splitlines()
        drop = set()

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.level > 0:
                    continue
                roots = ([a.name for a in node.names] if isinstance(node, ast.Import)
                         else [node.module or ""])
                for r in roots:
                    if r.split(".")[0] not in ALLOWED_IMPORTS:
                        raise BundleError(f"{mod}.py:{node.lineno} importa '{r}', que no está permitido")
            elif isinstance(node, ast.Call):
                f = node.func
                if ((isinstance(f, ast.Attribute) and f.attr in FORBIDDEN_CALLS)
                        or (isinstance(f, ast.Name) and f.id in FORBIDDEN_BUILTINS)):
                    name = f.attr if isinstance(f, ast.Attribute) else f.id
                    raise BundleError(f"{mod}.py:{node.lineno} llama a '{name}()', que el servidor rechaza "
                                      "(ojo: también np.stack o df.stack)")
            elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRS:
                raise BundleError(f"{mod}.py:{node.lineno} usa '{node.attr}', que el servidor rechaza")

        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                drop.update(range(node.lineno - 1, node.end_lineno))
                if isinstance(node, ast.ImportFrom) and node.level > 0:
                    continue  # import relativo: el nombre ya está en el fichero concatenado
                stmt = ast.get_source_segment(src, node).strip()
                for a in node.names:
                    bound = a.asname or a.name.split(".")[0]
                    origin = (f"{node.module}.{a.name}" if isinstance(node, ast.ImportFrom)
                              else (a.name if a.asname else a.name.split(".")[0]))
                    if bound in imports and imports[bound] != origin:
                        raise BundleError(f"'{bound}' apunta a '{imports[bound]}' y a '{origin}' "
                                          f"({mod}.py): usad el mismo import en todos los módulos")
                    imports[bound] = origin
                if stmt not in import_lines:
                    import_lines.append(stmt)
            elif (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                  and isinstance(node.value.value, str) and node is tree.body[0]):
                drop.update(range(node.lineno - 1, node.end_lineno))  # docstring del módulo

        for name in _top_names(tree):
            if name in defined:
                raise BundleError(f"'{name}' está definido en {defined[name]}.py y en {mod}.py")
            defined[name] = mod

        body = "\n".join(l for i, l in enumerate(lines) if i not in drop).strip("\n")
        bodies.append(f"# {'=' * 70}\n# {mod}.py\n# {'=' * 70}\n{body}\n")

    header = ('"""BatteryAgent — Datathon FME 2026, reto UPC Sostenible.\n\n'
              "FICHERO GENERADO por scripts/build_submission.py a partir de src/battery/.\n"
              'No lo editéis a mano: cambiad src/battery/ y volved a generarlo.\n"""\n')
    return header + "\n".join(import_lines) + "\n\n\n" + "\n\n".join(bodies)


def model_files() -> list:
    if not MODELS.exists():
        return []
    return sorted(f for f in MODELS.iterdir() if f.suffix in MODEL_SUFFIXES)


SMOKE_CHILD = r"""
import json, pickle, runpy
g = runpy.run_path("agent.py")
agent = g["BatteryAgent"]()
obs = pickle.load(open("obs.pkl", "rb"))
print(json.dumps([float(agent.act(o)) for o in obs]))
"""


def smoke_test(zip_path: Path, n: int = 72) -> None:
    sys.path.insert(0, str(REPO / "src"))
    from battery.adapter import make_official_obs
    from battery.data import load, validation_split
    from battery.policy import BatteryAgent

    df = validation_split(load()).iloc[:n]
    ref_agent = BatteryAgent()
    soc = ref_agent.policy.p.soc_init_kwh
    obs_list, ref = [], []
    from battery.safety import soc_after
    for t in range(n):
        idx = list(range(t, min(t + 24, n)))
        o = make_official_obs(df.timestamp[t], soc,
                              df.price_eur_kwh.to_numpy()[idx], df.co2_kg_kwh.to_numpy()[idx],
                              df.load_kw[t - 1] if t else float("nan"),
                              df.pv_kw[t - 1] if t else float("nan"))
        a = ref_agent.act(o)
        obs_list.append(o)
        ref.append(a)
        soc = soc_after(soc, a, ref_agent.policy.p)

    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmp)
        with open(Path(tmp, "obs.pkl"), "wb") as fh:
            pickle.dump(obs_list, fh)
        out = subprocess.run([sys.executable, "-I", "-c", SMOKE_CHILD], cwd=tmp,
                             capture_output=True, text=True, timeout=120)
        if out.returncode != 0:
            raise BundleError("dist/agent.py falla ejecutado aislado:\n" + out.stderr[-3000:])
        got = json.loads(out.stdout.strip().splitlines()[-1])
    diff = max(abs(a - b) for a, b in zip(got, ref))
    if diff > 1e-6:
        raise BundleError(f"dist/agent.py no da las mismas acciones que src/ (dif. máx. {diff:.3g})")
    print(f"  prueba aislada OK: {n} pasos, mismas acciones que src/ (dif. máx. {diff:.1e})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-smoke", action="store_true", help="no ejecutar la prueba aislada")
    args = ap.parse_args()
    try:
        code = bundle()
        DIST.mkdir(exist_ok=True)
        (DIST / "agent.py").write_text(code, encoding="utf-8")
        for f in model_files():  # también junto a dist/agent.py, para `eval.py --agent dist`
            (DIST / f.name).write_bytes(f.read_bytes())
        zip_path = DIST / "submission.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(DIST / "agent.py", "agent.py")
            for f in model_files():
                z.write(f, f.name)
        size_mb = zip_path.stat().st_size / 1e6
        print(f"dist/agent.py: {len(code.splitlines())} líneas, módulos {', '.join(BUNDLE_MODULES)}")
        print(f"dist/submission.zip: {size_mb:.2f} MB, artefactos: "
              f"{[f.name for f in model_files()] or 'ninguno'}")
        if size_mb > MAX_ZIP_MB:
            raise BundleError(f"el ZIP pesa {size_mb:.1f} MB (> {MAX_ZIP_MB} MB)")
        if not args.no_smoke:
            smoke_test(zip_path)
        sys.path.insert(0, str(REPO / "src"))
        from battery.data import ensure_official
        ensure_official()
        if OFFICIAL_CHECKER.exists():
            out = subprocess.run([sys.executable, str(OFFICIAL_CHECKER), str(zip_path)],
                                 cwd=OFFICIAL_CHECKER.parent, capture_output=True, text=True, timeout=120)
            if out.returncode != 0 or "VÀLIDA" not in out.stdout:
                raise BundleError("check_submission.py oficial lo rechaza:\n" + out.stdout[-2000:])
            print("  check_submission.py oficial: VÁLIDA")
        else:
            print("  (sin oficial/: no se ha pasado check_submission.py oficial)")
    except BundleError as e:
        print("ERROR:", e, file=sys.stderr)
        return 1
    print("Listo para subir: dist/submission.zip (apuntad el envío en docs/envios.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
