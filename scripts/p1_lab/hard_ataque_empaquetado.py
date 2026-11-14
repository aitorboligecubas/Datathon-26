"""Ataques 5 y 6 al agente del HARD MODE: tiempo y diferencias entre src/ y el agent.py empaquetado.

Owner: P1. NO se empaqueta y NO escribe en dist/: empaqueta el src/ actual en un directorio temporal.

    python scripts/p1_lab/hard_ataque_empaquetado.py

Qué hace:
1. Empaqueta src/ con scripts/build_submission.py (bundle(hard=True)) en un directorio temporal y mira si
   dist/hard/agent.py es ese mismo fichero (si no, lo que hay en dist/ está viejo).
2. Graba las observaciones de tres episodios mientras decide el agente de src/ (con los modelos de models/):
   300 pasos del banco (dev), 336 pasos con el calendario del test (con salto de mes) y el test entero (2.016).
3. Ejecuta el agent.py empaquetado AISLADO (python -I, en el directorio temporal), con los JSON al lado y sin
   ellos, sobre esas observaciones. Compara las acciones con las de src/ y mide el tiempo de cada act().
"""
import hashlib
import json
import pickle
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hard_ataque_comun as c  # noqa: E402
import build_submission as bs  # noqa: E402
import p1_hard  # noqa: E402
from battery.hard import HardBatteryAgent  # noqa: E402

CHILD = r"""
import json, pickle, runpy, time
t0 = time.perf_counter()
g = runpy.run_path("agent.py")
agent = g["BatteryAgent"]()
init_s = time.perf_counter() - t0
obs = pickle.load(open("obs.pkl", "rb"))
acts, ms = [], []
for o in obs:
    t1 = time.perf_counter()
    a = float(agent.act(o))
    ms.append(1000 * (time.perf_counter() - t1))
    acts.append(a)
pol = getattr(agent, "policy", None)
print(json.dumps({"acts": acts, "ms": ms, "init_s": init_s, "fallbacks": getattr(pol, "n_fallbacks", -1)}))
"""


class Grabadora:
    def __init__(self):
        self.agent, self.obs, self.ms = HardBatteryAgent(), [], []

    def act(self, obs):
        import time
        self.obs.append(obs)
        t0 = time.perf_counter()
        a = self.agent.act(obs)
        self.ms.append(1000 * (time.perf_counter() - t0))
        return a


def grabar(df: pd.DataFrame) -> tuple:
    g = Grabadora()
    _, log = p1_hard.simulate_hard(g, df)
    return g.obs, [float(a) for a in log.action_kw], g.ms, g.agent.policy.n_fallbacks


def aislado(tmp: Path, obs: list) -> dict:
    with open(tmp / "obs.pkl", "wb") as fh:
        pickle.dump(obs, fh)
    out = subprocess.run([sys.executable, "-I", "-c", CHILD], cwd=tmp, capture_output=True, text=True, timeout=600)
    if out.returncode != 0:
        return {"error": out.stderr[-1500:]}
    return json.loads(out.stdout.strip().splitlines()[-1])


def main() -> int:
    bs.HARD_BUILD = True
    code = bs.bundle(True)
    dist = c.REPO / "dist" / "hard" / "agent.py"
    same = dist.exists() and hashlib.sha1(dist.read_bytes()).hexdigest() == hashlib.sha1(code.encode("utf-8")).hexdigest()
    print(f"agent.py empaquetado ahora: {len(code.splitlines())} líneas, {len(code) / 1e3:.0f} kB. "
          f"dist/hard/agent.py {'ES el mismo' if same else 'NO es el mismo (dist/ está viejo o no existe)'}")

    full, _ = c.episodio_test("copia")
    dev = p1_hard.split_frame(c.tabla(), "dev")
    episodios = {"banco dev, 300 pasos": dev.iloc[:300].reset_index(drop=True),
                 "calendario del test, 336 pasos (salto de mes)": full.iloc[:336].reset_index(drop=True),
                 "test entero, 2.016 pasos": full}
    rows = []
    with tempfile.TemporaryDirectory() as tmp_s:
        tmp = Path(tmp_s)
        (tmp / "agent.py").write_text(code, encoding="utf-8")
        zip_path = tmp / "submission.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(tmp / "agent.py", "agent.py")
            for f in bs.model_files():
                z.write(f, f.name)
        if bs.OFFICIAL_CHECKER.exists():
            chk = subprocess.run([sys.executable, str(bs.OFFICIAL_CHECKER), str(zip_path)], cwd=bs.OFFICIAL_CHECKER.parent,
                                 capture_output=True, text=True, timeout=180)
            print("check_submission.py oficial:", "VÁLIDA" if "VÀLIDA" in chk.stdout and chk.returncode == 0 else "RECHAZADA\n" + chk.stdout[-800:])
        zip_path.unlink()
        for con_json in (True, False):
            for f in bs.model_files():
                if con_json:
                    (tmp / f.name).write_bytes(f.read_bytes())
                elif (tmp / f.name).exists():
                    (tmp / f.name).unlink()
            for nombre, df in episodios.items():
                if not con_json and len(df) > 400:
                    continue
                obs, ref, ms_src, fb_src = grabar(df)
                r = aislado(tmp, obs)
                if "error" in r:
                    rows.append({"episodio": nombre, "json_al_lado": con_json, "error": r["error"][-200:]})
                    continue
                dif = np.abs(np.asarray(r["acts"]) - np.asarray(ref))
                ms = np.asarray(r["ms"])
                rows.append({"episodio": nombre, "json_al_lado": con_json, "pasos": len(df),
                             "dif_max_kw": float(dif.max()), "pasos_distintos": int((dif > 1e-6).sum()),
                             "ms_medio": float(ms.mean()), "ms_p99": float(np.percentile(ms, 99)), "ms_max": float(ms.max()),
                             "init_s": r["init_s"], "s_2016_pasos": r["init_s"] + float(ms.mean()) * 2016 / 1000.0,
                             "s_2016_si_todos_fueran_el_peor": r["init_s"] + float(ms.max()) * 2016 / 1000.0,
                             "ms_medio_src": float(np.mean(ms_src)), "fallbacks": r["fallbacks"], "fallbacks_src": fb_src})
    out = pd.DataFrame(rows)
    pd.set_option("display.width", 280, "display.max_colwidth", 60)
    print(out.round(3).to_string(index=False))
    out_dir = c.REPO / "results" / "p1_hard"
    out_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_dir / "ataque_empaquetado.csv", index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
