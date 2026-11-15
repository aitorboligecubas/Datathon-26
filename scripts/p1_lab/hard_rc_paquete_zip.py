"""Revisión del PAQUETE ENTREGADO del HARD MODE (el agent.py del ZIP, tal como lo carga el servidor). NO se empaqueta.

Owner: P1 (revisión de cierre). No toca src/ ni el ZIP: solo carga el agent.py descomprimido.

    python scripts/p1_lab/hard_rc_paquete_zip.py <carpeta con agent.py y los JSON> <carpeta con solo agent.py>

Qué mide:
1. BatteryAgent() con los JSON al lado y sin ellos: se construye y decide lo mismo.
2. Simulador OFICIAL (CampusBatteryEnv, 6.000 kWh, 1.500 kW) en 504 h con calendario de test, 3 horas conocidas y
   la meteo: infracciones, tiempo por paso y proyección a 2.016 pasos. También frente al código de src/.
3. Observaciones raras (claves ausentes, None, NaN, listas cortas, timestamp cadena...): 0 excepciones, acción
   finita, dentro de la potencia y sin infracción con el SOC real.
"""
import copy
import importlib.util
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hard_ataque_comun as c  # noqa: E402
from battery.hard import HardBatteryAgent  # noqa: E402
from battery.sim import to_env_frame  # noqa: E402

SPEC = {"capacity_kwh": 6000, "power_kw": 1500, "efficiency": 0.9, "soc_init": 0.5, "soc_min": 0.0,
        "soc_max": 1.0, "dt_hours": 1, "degradation": False}
METEO = ("irradiancia_wm2", "temp_ambient_c", "temp_panel_c", "vent_ms")
ETA = math.sqrt(0.9)
NAN = float("nan")


def cargar(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def correr(envmod, full, agent):
    class HardEnv(envmod.CampusBatteryEnv):
        def _get_obs(self):
            obs = super()._get_obs()
            if obs is None:
                return None
            obs["preus_properes_24h"] = obs["preus_properes_24h"][:3]
            obs["co2_properes_24h"] = obs["co2_properes_24h"][:3]
            prev = self.t - 1 if self.t > 0 else self.t
            for k in METEO:
                obs["noves_dades_5min"][k] = float(full[k].iloc[prev])
            obs["cap_max_kwh"], obs["power_max_kw"] = self.cap, self.power
            return obs

    env = HardEnv(to_env_frame(full), spec=SPEC)
    obs, done = env.reset(), False
    acts, ms, seen = [], [], []
    while not done:
        seen.append(copy.deepcopy(obs))
        t0 = time.perf_counter()
        a = agent.act(obs)
        ms.append(1000 * (time.perf_counter() - t0))
        acts.append(float(a))
        obs, done = env.step(a)
    return env.evaluate_results(), np.array(acts), np.array(ms), seen


def mutaciones(o):
    out = []

    def put(k, v):
        return lambda d: d.__setitem__(k, v)

    for k in list(o.keys()):
        out.append((f"sin {k}", lambda d, k=k: d.pop(k, None)))
        for nm, v in (("None", None), ("NaN", NAN), ("'x'", "x"), ("[]", []), ("-1", -1), ("1e12", 1e12), ("inf", float("inf"))):
            out.append((f"{k}={nm}", put(k, v)))
    pr, co = list(o["preus_properes_24h"]), list(o["co2_properes_24h"])
    for k, base in (("preus_properes_24h", pr), ("co2_properes_24h", co)):
        for nm, v in (("len1", base[:1]), ("len2", base[:2]), ("[NaN]*3", [NAN] * 3), ("[None]*3", [None] * 3),
                      ("['a','b','c']", ["a", "b", "c"]), ("NaN en medio", [base[0], NAN, base[2]]),
                      ("NaN primero", [NAN, base[1], base[2]]), ("ndarray", np.array(base)), ("tupla", tuple(base)),
                      ("24 valores", (base * 8)[:24]), ("30 valores", (base * 10)[:30]), ("negativos", [-0.05] * 3),
                      ("ceros", [0.0] * 3), ("1e9", [1e9] * 3), ("inf", [float("inf")] * 3), ("lista de listas", [base]),
                      ("dict", {"a": 1})):
            out.append((f"{k}: {nm}", put(k, v)))
    for nm, n in (("ambas []", 0), ("ambas len1", 1), ("ambas len2", 2)):
        out.append((nm, lambda d, n=n: (d.__setitem__("preus_properes_24h", pr[:n]), d.__setitem__("co2_properes_24h", co[:n]))))
    out.append(("ambas None", lambda d: (d.__setitem__("preus_properes_24h", None), d.__setitem__("co2_properes_24h", None))))
    out.append(("ambas ausentes", lambda d: (d.pop("preus_properes_24h"), d.pop("co2_properes_24h"))))
    out.append(("preus len3, co2 len1", put("co2_properes_24h", co[:1])))
    out.append(("preus len1, co2 len3", put("preus_properes_24h", pr[:1])))
    out.append(("ambas [] y sin actual", lambda d: (d.__setitem__("preus_properes_24h", []), d.__setitem__("co2_properes_24h", []),
                                                    d.pop("preu_actual"), d.pop("co2_actual"))))
    ts = o["timestamp"]
    for nm, v in (("str", str(ts)), ("isoformat", ts.isoformat()), ("'basura'", "basura"), ("''", ""), ("epoch int", int(ts.timestamp())),
                  ("NaT", pd.NaT), ("datetime", ts.to_pydatetime()), ("np.datetime64", np.datetime64(ts)),
                  ("tz Madrid", ts.tz_localize("Europe/Madrid")), ("tz UTC", ts.tz_localize("UTC")), ("1900", pd.Timestamp("1900-01-01")),
                  ("2030", pd.Timestamp("2030-06-15 12:00")), ("fin del test", pd.Timestamp("2026-08-31 23:00")),
                  ("str fin del test", "2026-08-31 23:00:00"), ("tras el test", pd.Timestamp("2026-09-01 00:00")),
                  ("solo fecha str", str(ts.date())), ("dd/mm/yyyy", ts.strftime("%d/%m/%Y %H:%M")), ("29 feb str", "2026-02-29 10:00"),
                  ("float", 1.5), ("lista", [2026, 1, 1])):
        out.append((f"timestamp: {nm}", put("timestamp", v)))
    out.append(("sin timestamp ni hour ni day_of_week", lambda d: (d.pop("timestamp"), d.pop("hour"), d.pop("day_of_week"))))
    nd = dict(o["noves_dades_5min"])
    for nm, v in (("lista", [1.0, 2.0]), ("{}", {}), ("solo consumo", {"ultim_consum_kw": nd["ultim_consum_kw"]}),
                  ("valores None", {k: None for k in nd}), ("valores NaN", {k: NAN for k in nd}), ("valores 'x'", {k: "x" for k in nd}),
                  ("valores -100", {k: -100.0 for k in nd}), ("valores 1e9", {k: 1e9 for k in nd}), ("valores inf", {k: float("inf") for k in nd}),
                  ("valores 0", {k: 0.0 for k in nd}), ("sin meteo", {k: nd[k] for k in ("ultim_consum_kw", "ultima_solar_kw")}),
                  ("meteo None", dict(nd, **{k: None for k in METEO})), ("meteo NaN", dict(nd, **{k: NAN for k in METEO})),
                  ("irradiancia -5", dict(nd, irradiancia_wm2=-5.0)), ("irradiancia 5000", dict(nd, irradiancia_wm2=5000.0)),
                  ("solar 20000", dict(nd, ultima_solar_kw=20000.0)), ("consumo lista", dict(nd, ultim_consum_kw=[1, 2])),
                  ("lista de 5 min", dict(nd, ultim_consum_kw=[900.0] * 12, ultima_solar_kw=[100.0] * 12))):
        out.append((f"noves_dades_5min: {nm}", put("noves_dades_5min", v)))
    for nm, v in (("-100", -100.0), ("-1e-9", -1e-9), ("6000.0001", 6000.0001), ("7000", 7000.0), ("0", 0.0), ("6000", 6000.0)):
        out.append((f"soc_kwh={nm}", put("soc_kwh", v)))
    out.append(("sin soc_kwh (queda soc_pct)", lambda d: d.pop("soc_kwh")))
    out.append(("sin ningún soc", lambda d: (d.pop("soc_kwh"), d.pop("soc_pct"), d.pop("soc_percent"))))
    out.append(("sin cap ni power", lambda d: (d.pop("cap_max_kwh"), d.pop("power_max_kw"))))
    out.append(("cap y power None", lambda d: (d.__setitem__("cap_max_kwh", None), d.__setitem__("power_max_kw", None))))
    out.append(("cap y power 0", lambda d: (d.__setitem__("cap_max_kwh", 0), d.__setitem__("power_max_kw", 0))))
    out.append(("cap 2000 y power 500", lambda d: (d.__setitem__("cap_max_kwh", 2000), d.__setitem__("power_max_kw", 500))))
    out.append(("cap y power str", lambda d: (d.__setitem__("cap_max_kwh", "6000"), d.__setitem__("power_max_kw", "1500"))))
    for nm, v in (("24", 24), ("12.5", 12.5), ("'12'", "12")):
        out.append((f"hour={nm}", put("hour", v)))
    out.append(("day_of_week=7", put("day_of_week", 7)))
    out.append(("claves de sobra", lambda d: d.update({"extra": object(), 1: 2})))
    return out


def comprobar(a, o, toca_fisica):
    """'' si la acción es correcta; si no, qué falla."""
    try:
        af = float(a)
    except Exception as e:
        return f"no es número ({type(a).__name__}: {e})"
    if isinstance(a, (bool, str)):
        return f"tipo raro {type(a).__name__}"
    if not math.isfinite(af):
        return f"no finita ({af})"
    if abs(af) > 1500 + 1e-9:
        return f"fuera de potencia ({af:.1f})"
    if not toca_fisica:
        soc = float(o["soc_kwh"])
        if af > 0 and af > (6000 - soc) / ETA + 1e-9:
            return f"INFRACCIÓN al cargar ({af:.2f} con SOC {soc:.1f})"
        if af < 0 and -af > soc * ETA + 1e-9:
            return f"INFRACCIÓN al descargar ({af:.2f} con SOC {soc:.1f})"
    return ""


def main() -> int:
    zipdir, nojson = Path(sys.argv[1]), Path(sys.argv[2])
    t0 = time.perf_counter()
    m_json = cargar(zipdir / "agent.py", "agent_zip_json")
    t_imp = time.perf_counter() - t0
    m_solo = cargar(nojson / "agent.py", "agent_zip_solo")
    t0 = time.perf_counter()
    m_json.BatteryAgent()
    t_ctor = time.perf_counter() - t0
    print(f"1) import {t_imp:.2f} s | constructor {1000 * t_ctor:.0f} ms | con JSON y sin JSON: se construyen")

    envmod = cargar(c.REPO / "oficial" / "starter_kit" / "environment.py", "env_oficial")
    full, _ = c.episodio_test("copia", semanas=[0, 5, 9])
    r1, a1, ms1, seen = correr(envmod, full, m_json.BatteryAgent())
    print(f"2) OFICIAL, ZIP con JSON, {len(full)} h (sep, feb, jun): score {r1['score']:.3f} | infracciones {r1['infraccions']} | "
          f"ms/paso media {ms1.mean():.1f}, p99 {np.percentile(ms1, 99):.1f}, máx {ms1.max():.1f} | "
          f"proyección a 2.016 pasos {ms1.mean() * 2016 / 1000:.1f} s")
    r2, a2, ms2, _ = correr(envmod, full, m_solo.BatteryAgent())
    print(f"   ZIP sin JSON (copia incrustada): score {r2['score']:.3f} | infracciones {r2['infraccions']} | "
          f"máx |dif. de acción| con JSON {np.abs(a1 - a2).max():.2e} | proyección {ms2.mean() * 2016 / 1000:.1f} s")
    r3, a3, _, _ = correr(envmod, full, HardBatteryAgent())
    print(f"   código de src/ (árbol de trabajo): score {r3['score']:.3f} | infracciones {r3['infraccions']} | "
          f"máx |dif. de acción| con el ZIP {np.abs(a1 - a3).max():.2e}")
    print(f"   acciones del ZIP: carga {int((a1 > 1e-6).sum())} h, descarga {int((a1 < -1e-6).sum())} h, cero {int((np.abs(a1) <= 1e-6).sum())} h")

    # 3) Observaciones raras: agente nuevo (primera observación rara) y agente con 13 h vividas (rara a las 13:00).
    fisica = ("soc", "cap", "power")
    fallos, cicatrices, n = [], [], 0
    for nombre_mod, mod in (("con JSON", m_json), ("sin JSON", m_solo)):
        for k0 in (0, 13, 180):
            base = mod.BatteryAgent()
            for o in seen[max(0, k0 - 13):k0]:
                base.act(copy.deepcopy(o))
            limpio = copy.deepcopy(base)
            ref = [float(limpio.act(copy.deepcopy(o))) for o in seen[k0:k0 + 3]]
            for nombre, f in mutaciones(seen[k0]):
                n += 1
                ag = copy.deepcopy(base)
                d = copy.deepcopy(seen[k0])
                try:
                    f(d)
                except Exception as e:
                    fallos.append((nombre_mod, k0, nombre, f"la mutación no se pudo montar: {e}"))
                    continue
                toca = any(s in nombre for s in fisica)
                try:
                    a = ag.act(d)
                    err = comprobar(a, seen[k0], toca)
                except Exception as e:
                    err = f"EXCEPCIÓN {type(e).__name__}: {e}"[:160]
                if err:
                    fallos.append((nombre_mod, k0, nombre, err))
                    continue
                try:
                    post = [float(ag.act(copy.deepcopy(o))) for o in seen[k0 + 1:k0 + 3]]
                    for j, (x, o) in enumerate(zip(post, seen[k0 + 1:k0 + 3])):
                        e2 = comprobar(x, o, True)
                        if e2:
                            fallos.append((nombre_mod, k0, nombre, f"hora +{j + 1} tras la rara: {e2}"))
                    if max(abs(x - y) for x, y in zip(post, ref[1:])) > 1e-6:
                        cicatrices.append((nombre_mod, k0, nombre, float(a), ref[0], post, ref[1:]))
                except Exception as e:
                    fallos.append((nombre_mod, k0, nombre, f"EXCEPCIÓN en la hora siguiente {type(e).__name__}: {e}"[:160]))
    for rara in (None, [], "x", 42, {}, 3.5, [1, 2, 3]):
        for nombre_mod, mod in (("con JSON", m_json), ("sin JSON", m_solo)):
            n += 1
            try:
                ag = mod.BatteryAgent()
                a = ag.act(rara)
                err = comprobar(a, {"soc_kwh": 3000.0}, True)
                x = ag.act(copy.deepcopy(seen[0]))
                err = err or comprobar(x, seen[0], False)
            except Exception as e:
                err = f"EXCEPCIÓN {type(e).__name__}: {e}"[:160]
            if err:
                fallos.append((nombre_mod, "-", f"obs={rara!r}", err))
    print(f"3) observaciones raras: {n} casos | fallos {len(fallos)} | casos que cambian las 2 horas siguientes {len(cicatrices)}")
    for f in fallos[:40]:
        print("   FALLO", f)
    for s in cicatrices[:60]:
        print(f"   cicatriz [{s[0]}, t={s[1]}] {s[2]}: acción {s[3]:.1f} (limpia {s[4]:.1f}); siguientes {[round(v, 1) for v in s[5]]} (limpias {[round(v, 1) for v in s[6]]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
