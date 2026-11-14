"""Empaqueta el agente en un único dist/agent.py y genera dist/submission.zip.

Owner: INTEGRADOR.

Por qué: el servidor solo carga agent.py y no deja importar módulos hermanos
(ni sys, ni importlib, ni os). Así que juntamos los módulos del agente en un
solo fichero, quitando los imports relativos, y comprobamos:
  1. Que solo se importan librerías permitidas.
  2. Que dos módulos no definen el mismo nombre (se pisarían al concatenar).
  3. Que el ZIP (agent.py + artefactos de models/ en la raíz) pesa <= 25 MB.
  4. Que dist/agent.py, ejecutado aislado del repo, da las mismas acciones que src/,
     con los ficheros auxiliares del ZIP y también SIN ellos (el contenido de models/*.json va
     además incrustado en agent.py, por si el servidor no encontrara los ficheros).
  5. Que pasa oficial/starter_kit/check_submission.py (si tenéis el ZIP oficial descomprimido).

Uso:
    python scripts/build_submission.py            # genera y comprueba
    python scripts/build_submission.py --no-smoke # sin la prueba aislada
    python scripts/build_submission.py --hard     # el agente del HARD MODE, en dist/hard/
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
# El modo difícil (hard mode) añade sus módulos detrás y cambia la clase que carga el evaluador.
HARD_MODULES = ["hard_market", "hard_solar", "hard"]
HARD_FOOTER = """

# El evaluador carga `BatteryAgent`: en este fichero es el agente del modo difícil.
BatteryAgent = HardBatteryAgent
"""
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


def bundle(hard: bool = False) -> str:
    imports = {}        # nombre ligado -> sentencia de import
    import_lines = []   # en orden de aparición, sin duplicados
    defined = {}        # nombre -> módulo que lo define
    bodies = []
    modules = BUNDLE_MODULES + [m for m in HARD_MODULES if (SRC / (m + ".py")).exists()] if hard else BUNDLE_MODULES
    for mod in modules:
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

    code = (HARD_HEADER if hard else HEADER) + "\n".join(import_lines) + "\n\n\n" + "\n\n".join(bodies)
    if hard:
        code += HARD_FOOTER
    return embed_models(code)


HEADER = '''"""BatteryAgent — Reto UPC Sostenible, Datathon FME 2026. Equipo SanHackobos.

QUÉ HACE
    Cada hora decide cuánto carga (+) o descarga (-) la batería del campus, en kW.
    Funciona como un GPS: planifica las próximas 24 horas, ejecuta solo la primera y, una hora
    después, vuelve a planificar con la información nueva (control predictivo, MPC).

CÓMO DECIDE
    El plan de 24 horas es un problema de programación lineal (LP, solver HiGHS de scipy) que
    minimiza exactamente lo que puntúa el reto,
        suma de  compra_a_la_red(h) * ( 0,70 * CO2(h) / CO2_ref  +  0,30 * precio(h) / coste_ref ),
    con la física real de la batería: 2.000 kWh, 500 kW y rendimiento sqrt(0,9) en cada sentido.
    El precio y el CO2 de las próximas 24 horas los da el entorno; el consumo se prevé con un perfil
    por hora de la semana corregido con la última lectura. No hay parámetros ajustados a mano.

PROTECCIONES
    - Cero infracciones: toda acción se recorta a lo físicamente posible (safety.clip_action).
    - Avería del contador: si la última lectura de consumo es 0, no se descarga (sería tirar energía).
    - Final de los datos: cuando la previsión llega recortada, se gasta la carga que queda,
      porque la carga final no puntúa.
    - El agente nunca lanza una excepción: ante cualquier error devuelve una acción segura.

ESTRUCTURA DE ESTE FICHERO (un bloque por módulo de src/battery/)
    params      constantes del reto y de la batería
    obs         la observación en nuestro formato interno
    adapter     traduce el diccionario oficial `obs` a ese formato
    safety      límites físicos de la batería
    forecaster  previsión de consumo y de producción solar
    optimizer   el LP de 24 horas
    policy      el MPC y la clase BatteryAgent que llama el evaluador

FICHERO GENERADO por scripts/build_submission.py a partir de src/battery/.
No lo editéis a mano: cambiad src/battery/ y volved a generarlo.
Repositorio: https://github.com/aitorboligecubas/Datathon-26
"""
'''
HARD_HEADER = '''"""BatteryAgent (HARD MODE) — Reto UPC Sostenible, Datathon FME 2026. Equipo SanHackobos.

QUÉ CAMBIA EN EL MODO DIFÍCIL
    Batería de 6.000 kWh y 1.500 kW, 12 veces más solar (hay horas con excedente, que se vierte gratis)
    y solo 3 horas de precio y CO2 conocidas. El resto hay que preverlo.

QUÉ HACE
    Lo mismo que en el modo estándar: planifica 24 horas con un problema de programación lineal que
    minimiza lo que puntúa el reto (0,70 CO2 + 0,30 coste), ejecuta la primera hora y vuelve a planificar.
    La diferencia es de dónde sale la información:
      - precio y CO2: las 3 horas que da el entorno y, más allá, un perfil por mes, tipo de día y hora
        aprendido en el train, ajustado al nivel de los últimos días y a lo que pasó ayer a la misma hora;
      - solar y consumo: previsión propia con la lectura de la hora anterior;
      - final del test: por calendario (ya no se ve en la previsión).

PROTECCIONES
    Cero infracciones (toda acción se recorta a lo físicamente posible), nunca se descarga por encima de
    lo que el campus compró la hora anterior, y el agente nunca lanza una excepción.

FICHERO GENERADO por scripts/build_submission.py --hard a partir de src/battery/.
Repositorio: https://github.com/aitorboligecubas/Datathon-26
"""
'''
EMBED_MARK = "EMBEDDED_MODELS = {}"


def _finite(obj) -> bool:
    if isinstance(obj, dict):
        return all(_finite(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return all(_finite(v) for v in obj)
    if isinstance(obj, float):
        return obj == obj and abs(obj) != float("inf")
    return isinstance(obj, (int, str, bool)) or obj is None


def embed_models(code: str) -> str:
    """Copia models/*.json dentro de agent.py (EMBEDDED_MODELS), como respaldo de los ficheros."""
    if code.count(EMBED_MARK) != 1:
        raise BundleError(f"no encuentro la línea '{EMBED_MARK}' (una sola vez) para incrustar los modelos")
    models = {}
    for f in model_files():
        if f.suffix == ".json":
            data = json.loads(f.read_text(encoding="utf-8"))
            if not _finite(data):
                raise BundleError(f"{f.name} tiene valores no finitos: no se puede incrustar")
            models[f.name] = data
    lines = ["EMBEDDED_MODELS = {"]
    for name, data in models.items():
        lines.append(f"    {name!r}: {data!r},")
    lines.append("}")
    return code.replace(EMBED_MARK, "\n".join(lines))


HARD_BUILD = False   # lo activa main() con --hard


def model_files() -> list:
    """Artefactos de models/. Los que empiezan por "hard_" son solo del modo difícil."""
    if not MODELS.exists():
        return []
    return sorted(f for f in MODELS.iterdir()
                  if f.suffix in MODEL_SUFFIXES and (HARD_BUILD or not f.name.startswith("hard_")))


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
        for label in ("con los ficheros del ZIP", "sin ficheros auxiliares"):
            if label.startswith("sin"):
                for f in Path(tmp).iterdir():
                    if f.name not in ("agent.py", "obs.pkl"):
                        f.unlink()
            out = subprocess.run([sys.executable, "-I", "-c", SMOKE_CHILD], cwd=tmp,
                                 capture_output=True, text=True, timeout=120)
            if out.returncode != 0:
                raise BundleError(f"dist/agent.py falla ejecutado aislado ({label}):\n" + out.stderr[-3000:])
            got = json.loads(out.stdout.strip().splitlines()[-1])
            diff = max(abs(a - b) for a, b in zip(got, ref))
            if diff > 1e-6:
                raise BundleError(f"dist/agent.py {label} no da las mismas acciones que src/ "
                                  f"(dif. máx. {diff:.3g})")
            print(f"  prueba aislada OK {label}: {n} pasos, mismas acciones que src/ (dif. máx. {diff:.1e})")


def smoke_test_hard(zip_path: Path, n: int = 96) -> None:
    """Como smoke_test, con observaciones del modo difícil (3 horas de previsión, solar x12 y meteo)."""
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "scripts"))
    import p1_hard
    from battery.data import validation_split
    from battery.hard import HardBatteryAgent

    df = validation_split(p1_hard.hard_table()).iloc[:n].reset_index(drop=True)
    obs_list = []

    class Recorder:
        def __init__(self):
            self.agent = HardBatteryAgent()

        def act(self, obs):
            obs_list.append(obs)
            return self.agent.act(obs)

    _, log = p1_hard.simulate_hard(Recorder(), df)
    ref = [float(a) for a in log.action_kw]
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmp)
        with open(Path(tmp, "obs.pkl"), "wb") as fh:
            pickle.dump(obs_list, fh)
        for label in ("con los ficheros del ZIP", "sin ficheros auxiliares"):
            if label.startswith("sin"):
                for f in Path(tmp).iterdir():
                    if f.name not in ("agent.py", "obs.pkl"):
                        f.unlink()
            out = subprocess.run([sys.executable, "-I", "-c", SMOKE_CHILD], cwd=tmp,
                                 capture_output=True, text=True, timeout=180)
            if out.returncode != 0:
                raise BundleError(f"dist/hard/agent.py falla ejecutado aislado ({label}):\n" + out.stderr[-3000:])
            got = json.loads(out.stdout.strip().splitlines()[-1])
            diff = max(abs(a - b) for a, b in zip(got, ref))
            if diff > 1e-6:
                raise BundleError(f"dist/hard/agent.py {label} no da las mismas acciones que src/ (dif. máx. {diff:.3g})")
            print(f"  prueba aislada OK {label}: {n} pasos, mismas acciones que src/ (dif. máx. {diff:.1e})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-smoke", action="store_true", help="no ejecutar la prueba aislada")
    ap.add_argument("--hard", action="store_true", help="empaquetar el agente del modo difícil en dist/hard/")
    args = ap.parse_args()
    global HARD_BUILD
    HARD_BUILD = bool(args.hard)
    try:
        code = bundle(args.hard)
        out_dir = DIST / "hard" if args.hard else DIST
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "agent.py").write_text(code, encoding="utf-8")
        for f in model_files():  # también junto a agent.py, para `eval.py --agent dist`
            (out_dir / f.name).write_bytes(f.read_bytes())
        zip_path = out_dir / "submission.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(out_dir / "agent.py", "agent.py")
            for f in model_files():
                z.write(f, f.name)
        size_mb = zip_path.stat().st_size / 1e6
        print(f"{zip_path.relative_to(REPO)}: {len(code.splitlines())} líneas de agent.py, {size_mb:.2f} MB, "
              f"artefactos: {[f.name for f in model_files()] or 'ninguno'}")
        if size_mb > MAX_ZIP_MB:
            raise BundleError(f"el ZIP pesa {size_mb:.1f} MB (> {MAX_ZIP_MB} MB)")
        if not args.no_smoke:
            (smoke_test_hard if args.hard else smoke_test)(zip_path)
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
    print(f"Listo para subir: {zip_path.relative_to(REPO)} (apuntad el envío en docs/envios.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
