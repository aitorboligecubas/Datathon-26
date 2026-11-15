"""Revisión del PAQUETE ENTREGADO del HARD MODE, segunda parte. NO se empaqueta. Owner: P1 (revisión de cierre).

    python scripts/p1_lab/hard_rc_paquete_extra.py <carpeta con agent.py del ZIP>

1. Escáner por AST del agent.py: imports y llamadas prohibidas (CLAUDE.md, sección 7).
2. Simulador oficial SIN cap_max_kwh ni power_max_kw en la observación: mismas acciones y 0 infracciones.
3. Simulador oficial en las dos últimas semanas del test (jul y ago): final del test, listas de 2 y 1 valores.
"""
import ast
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hard_ataque_comun as c  # noqa: E402
import hard_rc_paquete_zip as z  # noqa: E402

PERMITIDAS = {"numpy", "pandas", "scipy", "sklearn", "joblib", "xgboost", "lightgbm", "math", "random", "datetime",
              "collections", "itertools", "json", "pathlib", "typing", "dataclasses", "functools", "heapq", "bisect",
              "re", "copy", "pickle"}
MALAS = {"eval", "exec", "compile", "globals", "locals", "vars", "__import__", "print", "input", "breakpoint",
         "setattr", "delattr"}
ATRIB = {"stack", "write", "write_text", "write_bytes", "to_csv", "to_json", "to_pickle", "dump", "save", "savez",
         "savetxt", "mkdir", "unlink", "system", "popen", "touch", "rename", "tofile"}


def main() -> int:
    zipdir = Path(sys.argv[1])
    src = (zipdir / "agent.py").read_text()
    tree = ast.parse(src)
    malos, opens = [], []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            malos += [(n.lineno, "import " + a.name) for a in n.names if a.name.split(".")[0] not in PERMITIDAS]
        elif isinstance(n, ast.ImportFrom):
            if (n.module or "").split(".")[0] not in PERMITIDAS or n.level:
                malos.append((n.lineno, f"from {'.' * n.level}{n.module} import"))
        elif isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name) and f.id in MALAS:
                malos.append((n.lineno, f.id + "("))
            if isinstance(f, ast.Attribute) and f.attr in ATRIB:
                malos.append((n.lineno, "." + f.attr + "("))
            if isinstance(f, ast.Name) and f.id == "open":
                modo = [a.value for a in n.args[1:2] if isinstance(a, ast.Constant)] + [k.value.value for k in n.keywords if k.arg == "mode" and isinstance(k.value, ast.Constant)]
                opens.append((n.lineno, modo or ["r (por defecto)"]))
        elif isinstance(n, ast.Name) and n.id in ("os", "sys", "subprocess", "importlib", "inspect", "__builtins__"):
            malos.append((n.lineno, "nombre " + n.id))
        elif isinstance(n, ast.Raise):
            pass
    print(f"1) AST: prohibidos {malos if malos else 'ninguno'} | open(): {opens} | 'X | None' en anotaciones: se compila en este Python {sys.version.split()[0]}")
    lineas = src.splitlines()
    print(f"   líneas {len(lineas)}, bytes {len(src.encode())}, clase BatteryAgent definida: {any(isinstance(n, ast.ClassDef) and n.name == 'BatteryAgent' for n in tree.body)}"
          f" | asignación BatteryAgent: {[l for l in lineas if l.startswith('BatteryAgent')][:2]}")

    mod = z.cargar(zipdir / "agent.py", "agent_zip_extra")
    envmod = z.cargar(c.REPO / "oficial" / "starter_kit" / "environment.py", "env_oficial2")
    full, _ = c.episodio_test("copia", semanas=[0, 5, 9])
    r1, a1, _, _ = z.correr(envmod, full, mod.BatteryAgent())

    class SinClaves:
        def __init__(self, quitar):
            self.ag, self.quitar = mod.BatteryAgent(), quitar
        def act(self, obs):
            o = dict(obs)
            o["noves_dades_5min"] = dict(o["noves_dades_5min"])
            for k in self.quitar:
                if k in o:
                    o.pop(k)
                else:
                    o["noves_dades_5min"].pop(k, None)
            return self.ag.act(o)

    for nombre, quitar in (("sin cap_max_kwh ni power_max_kw", ("cap_max_kwh", "power_max_kw")),
                           ("sin la meteo", z.METEO),
                           ("sin hour ni day_of_week", ("hour", "day_of_week")),
                           ("sin soc_pct ni soc_percent", ("soc_pct", "soc_percent")),
                           ("sin preu_actual ni co2_actual", ("preu_actual", "co2_actual"))):
        r, a, _, _ = z.correr(envmod, full, SinClaves(quitar))
        print(f"2) {nombre}: score {r['score']:.3f} (con todo {r1['score']:.3f}) | infracciones {r['infraccions']} | máx |dif. acción| {np.abs(a - a1).max():.2e}")

    class TsCadena:
        def __init__(self):
            self.ag = mod.BatteryAgent()
        def act(self, obs):
            return self.ag.act(dict(obs, timestamp=str(obs["timestamp"])))
    r, a, _, _ = z.correr(envmod, full, TsCadena())
    print(f"2) timestamp como cadena todo el episodio: score {r['score']:.3f} | infracciones {r['infraccions']} | máx |dif. acción| {np.abs(a - a1).max():.2e}")

    fin, _ = c.episodio_test("copia", semanas=[10, 11])
    r, a, ms, seen = z.correr(envmod, fin, mod.BatteryAgent())
    print(f"3) jul+ago ({len(fin)} h, acaba {fin.timestamp.iloc[-1]}): score {r['score']:.3f} | infracciones {r['infraccions']} | "
          f"SOC en la última observación {seen[-1]['soc_kwh']:.1f} kWh, última acción {a[-1]:.1f} kW | len de las listas en las 3 últimas horas {[len(o['preus_properes_24h']) for o in seen[-3:]]}")
    print("   últimas 8 h (hora, SOC, acción):", [(o["timestamp"].hour, round(o["soc_kwh"]), round(x)) for o, x in zip(seen[-8:], a[-8:])])
    return 0


if __name__ == "__main__":
    sys.exit(main())
