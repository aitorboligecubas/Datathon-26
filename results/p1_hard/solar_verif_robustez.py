"""Verificación independiente del candidato 'solar' (HARD MODE): reglas del empaquetado y robustez.

    python results/p1_hard/solar_verif_robustez.py

A. Reglas: imports del bloque de inferencia, llamadas prohibidas, sintaxis de Python 3.9 y nombres que
   chocan con otros módulos del paquete (candidato y copia en src/battery/hard_solar.py).
B. Llamadas directas a update / forecast / adjust_action con entradas raras: no deben lanzar excepciones
   ni devolver NaN, negativos o longitudes equivocadas.
C. El agente entero (HardPolicy con el candidato dentro) con observaciones oficiales estropeadas.
D. Coste de la previsión por hora.
No se empaqueta. No toca nada del repo.
"""
import ast
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import p1_hard as bench  # noqa: E402
from battery.forecaster import FORECASTER_FILE, Forecaster  # noqa: E402
from battery.hard import HARD_PARAMS  # noqa: E402
from battery.obs import Obs  # noqa: E402
from battery.policy import find_models_dir, load_json  # noqa: E402
from battery.sim import apply_action  # noqa: E402

CAND_FILE = REPO / "scripts" / "p1_lab" / "hard_solar_cand.py"
make = bench.load_factory(str(CAND_FILE) + ":make")
G = make.__globals__
SolarCand, to_prior = G["SolarCand"], G["to_prior"]
ALLOWED = {"numpy", "pandas", "math", "collections", "typing"}
BAD_CALLS = {"stack", "eval", "exec", "compile", "globals", "locals", "vars", "__import__", "print", "open", "write", "write_text"}
OTHER_MODULES = ["params", "obs", "adapter", "safety", "forecaster", "optimizer", "policy", "hard_market", "hard"]
H = pd.Timedelta(hours=1)
PROBLEMS = []


def top_names(tree) -> set:
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        names.add(n.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def static_rules(label: str, source: str, others: set) -> None:
    try:
        tree = ast.parse(source, feature_version=(3, 9))
    except SyntaxError as exc:
        print(f"   {label}: NO es sintaxis de Python 3.9: {exc}"); return
    imports, calls, unions = set(), [], 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                imports.add((node.module or "").split(".")[0])
        elif isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
            if name in BAD_CALLS:
                calls.append(f"{name} (línea {node.lineno})")
        elif isinstance(node, (ast.FunctionDef, ast.AnnAssign, ast.arg)):
            anns = [node.returns] if isinstance(node, ast.FunctionDef) else [node.annotation]
            unions += sum(isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr) for a in anns if a is not None for n in ast.walk(a))
        elif isinstance(node, ast.Match if hasattr(ast, "Match") else ()):
            unions += 1
    clash = sorted(top_names(tree) & others)
    print(f"   {label}: imports {sorted(imports)} | fuera de la lista: {sorted(imports - ALLOWED) or 'ninguno'} | "
          f"llamadas prohibidas: {calls or 'ninguna'} | anotaciones 'X | None' o match: {unions} | nombres que chocan: {clash or 'ninguno'}")


def rules() -> None:
    print("A. REGLAS DEL EMPAQUETADO")
    others = set()
    for m in OTHER_MODULES:
        others |= top_names(ast.parse((REPO / "src" / "battery" / (m + ".py")).read_text(encoding="utf-8")))
    src = CAND_FILE.read_text(encoding="utf-8")
    cut = src.index("# ------------------------------------------------------------------------------------ ajuste")
    static_rules("candidato, bloque de inferencia", src[:cut], others)
    static_rules("candidato, bloque de ajuste (no se empaqueta)", src[cut:], set())
    hs = (REPO / "src" / "battery" / "hard_solar.py").read_text(encoding="utf-8")
    static_rules("src/battery/hard_solar.py (copia v7)", hs, others)
    # ¿la copia de src decide igual? diferencias de texto de la clase SolarCand
    a = src[src.index("class SolarCand"):cut].splitlines()
    b = hs[hs.index("class SolarCand"):hs.index("def make_netload")].splitlines()
    import difflib
    diff = [ln for ln in difflib.unified_diff(a, b, lineterm="", n=0) if ln[:1] in "+-" and ln[:3] not in ("+++", "---")]
    print(f"   líneas distintas entre SolarCand del candidato y la copia de src: {len(diff)}")
    for ln in diff[:40]:
        print("      " + ln[:150])


def obs_of(ts, load_prev=1000.0, pv_prev=0.0, soc=3000.0) -> Obs:
    hour = int(ts.hour) if (ts is not None and ts is not pd.NaT and hasattr(ts, "hour")) else 0
    wd = int(ts.dayofweek) if (ts is not None and ts is not pd.NaT and hasattr(ts, "dayofweek")) else 0
    return Obs(hour=hour, weekday=wd, soc_kwh=soc, price=np.array([0.12, 0.10, 0.09]), co2=np.array([0.10, 0.09, 0.08]),
               load_prev_kw=load_prev, pv_prev_kw=pv_prev, timestamp=ts)


def new_base(prior=True):
    b = Forecaster(load_json(find_models_dir(), FORECASTER_FILE) if prior else None)
    try:
        b.pv_prior = b.pv_prior * 12.0
    except Exception:
        pass
    return b


N_CALLS = {"update": 0, "forecast": 0, "adjust": 0}


def note(kind: str, tag: str, detail: str) -> None:
    PROBLEMS.append((kind, tag, detail))


def step(f, obs, weather, times, tag: str, actions=(-1500.0, -700.0, -1.0, 0.0, 300.0, 1500.0)) -> None:
    """Una hora: update, forecast y adjust_action. Apunta excepciones y salidas malas."""
    try:
        f.update(obs, weather); N_CALLS["update"] += 1
    except Exception as exc:
        note("EXCEPCIÓN update", tag, repr(exc)[:120])
    try:
        load, pv = f.forecast(obs, times); N_CALLS["forecast"] += 1
        load, pv = np.asarray(load, float), np.asarray(pv, float)
        n = max(1, len(times))
        if len(load) != n or len(pv) != n:
            note("LONGITUD forecast", tag, f"{len(load)}/{len(pv)} en vez de {n}")
        if not (np.isfinite(load).all() and np.isfinite(pv).all()):
            note("NaN forecast", tag, f"load {load[:3]}, pv {pv[:3]}")
        elif (load < 0).any() or (pv < 0).any():
            note("NEGATIVO forecast", tag, f"min load {load.min():.1f}, min pv {pv.min():.1f}")
        elif load.max() > 20000 or pv.max() > 20000:
            note("ABSURDO forecast (> 20 MW)", tag, f"max load {load.max():.3g}, max pv {pv.max():.3g}")
    except Exception as exc:
        note("EXCEPCIÓN forecast", tag, repr(exc)[:120])
    for a in actions:
        try:
            out = f.adjust_action(a, obs, HARD_PARAMS); N_CALLS["adjust"] += 1
            if not (isinstance(out, (int, float)) and math.isfinite(out)):
                note("NaN adjust_action", tag, f"acción {a} -> {out}")
            elif out > HARD_PARAMS.max_charge_kw + 1e-9:
                note("CARGA > potencia máxima en adjust_action", tag, f"acción {a} -> {out:.1f}")
            elif a >= 0 and out < -1e-9:
                note("adjust_action convierte una carga en descarga", tag, f"acción {a} -> {out:.1f}")
        except Exception as exc:
            note("EXCEPCIÓN adjust_action", tag, repr(exc)[:120])


def times_from(ts, n: int) -> list:
    return [ts + H * k for k in range(n)]


def warm(f, start, hours: int = 30, load=1000.0, pv=200.0):
    """Unas horas normales para que el previsor tenga memoria. Devuelve la fecha siguiente."""
    ts = pd.Timestamp(start)
    f.new_block()
    for i in range(hours):
        o = obs_of(ts, float("nan") if i == 0 else load, float("nan") if i == 0 else (pv if 8 <= (ts - H).hour <= 18 else 0.0))
        f.update(o, {}); f.forecast(o, times_from(ts, 24))
        ts = ts + H
    return ts


def direct_calls(prior) -> None:
    print("B. LLAMADAS DIRECTAS CON ENTRADAS RARAS")
    nan, inf = float("nan"), float("inf")
    readings = [nan, 0.0, -5.0, 1e-9, 50.0, 1100.0, 1e9, inf, -inf]
    # B1. lecturas raras, con y sin memoria, a varias horas del día
    for start in ("2025-09-24 00:00", "2026-01-25 00:00", "2026-06-24 00:00"):
        for hours in (0, 2, 9, 14, 21, 24, 30, 54):
            for lp in readings:
                for pp in (nan, 0.0, -3.0, 500.0, 1e9, inf):
                    f = SolarCand(prior, new_base())
                    ts = warm(f, start, hours) if hours else pd.Timestamp(start)
                    step(f, obs_of(ts, lp, pp), {}, times_from(ts, 24), f"B1 lectura load={lp} pv={pp} tras {hours} h desde {start}")
    # B2. meteo rara
    for w in (None, {}, {"irradiancia_wm2": nan, "temp_ambient_c": nan, "temp_panel_c": nan, "vent_ms": nan},
              {"irradiancia_wm2": "abc"}, {"x": object()}, [], "meteo", 3.5, [1, 2], np.array([1.0, 2.0]), np.array([])):
        f = SolarCand(prior, new_base())
        ts = warm(f, "2026-03-25 00:00", 12)
        step(f, obs_of(ts, 900.0, 300.0), w, times_from(ts, 24), f"B2 meteo={type(w).__name__}:{str(w)[:30]}")
    # B3. times raros
    ts0 = pd.Timestamp("2026-04-26 10:00")
    weird_times = {
        "vacío": [], "1 hora": times_from(ts0, 1), "2 horas": times_from(ts0, 2), "3 horas": times_from(ts0, 3),
        "48 horas": times_from(ts0, 48), "[None]": [None], "[None, None]": [None, None], "[ts, None]": [ts0, None],
        "[ts, NaT]": [ts0, pd.NaT], "[NaT]": [pd.NaT], "repetidas": [ts0] * 5, "hacia atrás": [ts0 - H * k for k in range(6)],
        "salto al mes siguiente": times_from(pd.Timestamp("2026-04-30 20:00"), 4) + times_from(pd.Timestamp("2026-05-25 00:00"), 20),
        "fin de año": times_from(pd.Timestamp("2025-12-31 20:00"), 4) + times_from(pd.Timestamp("2026-01-25 00:00"), 20),
        "datetime de Python": [t.to_pydatetime() for t in times_from(ts0, 4)], "texto": ["2026-04-26 10:00", "2026-04-26 11:00"],
        "con zona horaria": [t.tz_localize("Europe/Madrid") for t in times_from(ts0, 4)],
        "a y media": times_from(pd.Timestamp("2026-04-26 10:30"), 6), "año 2099": times_from(pd.Timestamp("2099-03-29 00:00"), 30),
        "cambio de hora de marzo": [pd.Timestamp("2026-03-29 00:00"), pd.Timestamp("2026-03-29 01:00")] + times_from(pd.Timestamp("2026-03-29 03:00"), 22),
        "cambio de hora de octubre": times_from(pd.Timestamp("2025-10-26 00:00"), 3) + times_from(pd.Timestamp("2025-10-26 02:00"), 21),
        "29 de febrero": times_from(pd.Timestamp("2028-02-28 12:00"), 30),
    }
    for name, times in weird_times.items():
        for hours in (0, 30):
            f = SolarCand(prior, new_base())
            ts = warm(f, ts0 - H * hours, hours) if hours else ts0
            first = times[0] if times else ts
            o = obs_of(first if isinstance(first, pd.Timestamp) and first is not pd.NaT else ts, 950.0, 400.0)
            step(f, o, {}, times, f"B3 times={name} tras {hours} h")
    # B4. fechas raras en la observación y saltos entre observaciones
    seqs = {
        "fecha None": [None, None, None],
        "NaT": [pd.NaT, pd.NaT],
        "primera hora de una semana (sin aviso)": ["2025-09-24 00:00", "2025-09-24 01:00"],
        "salto de un mes sin new_block": ["2025-09-30 22:00", "2025-09-30 23:00", "2025-10-25 00:00", "2025-10-25 01:00"],
        "salto de un mes a mediodía": ["2026-05-31 12:00", "2026-05-31 13:00", "2026-06-24 13:00", "2026-06-24 14:00"],
        "reloj hacia atrás": ["2026-02-25 10:00", "2026-02-25 11:00", "2026-02-25 05:00", "2026-02-25 06:00"],
        "misma hora 30 veces": ["2026-02-25 10:00"] * 30,
        "salto de 2 horas (cambio de hora)": ["2026-03-29 00:00", "2026-03-29 01:00", "2026-03-29 03:00", "2026-03-29 04:00"],
        "hora repetida (cambio de hora)": ["2025-10-26 01:00", "2025-10-26 02:00", "2025-10-26 02:00", "2025-10-26 03:00"],
        "fin de año": ["2025-12-31 22:00", "2025-12-31 23:00", "2026-01-25 00:00"],
        "None entre fechas": ["2026-02-25 10:00", None, "2026-02-25 12:00"],
        "con zona horaria": [pd.Timestamp("2026-02-25 10:00", tz="Europe/Madrid"), pd.Timestamp("2026-02-25 11:00", tz="Europe/Madrid")],
        "a y media": ["2026-02-25 10:30", "2026-02-25 11:30"],
        "año 1900": ["1900-03-25 10:00", "1900-03-25 11:00"],
    }
    for name, seq in seqs.items():
        for hours in (0, 40):
            f = SolarCand(prior, new_base())
            if hours and seq[0] is not None and seq[0] is not pd.NaT:
                first = pd.Timestamp(seq[0])
                warm(f, (first.tz_localize(None) if first.tzinfo is not None else first) - H * hours, hours)
            for i, raw in enumerate(seq):
                ts = raw if (raw is None or raw is pd.NaT or isinstance(raw, pd.Timestamp)) else pd.Timestamp(raw)
                ok_ts = isinstance(ts, pd.Timestamp) and ts is not pd.NaT
                times = times_from(ts, 24) if ok_ts else [None, None, None]
                step(f, obs_of(ts, 1000.0, 250.0), {}, times, f"B4 secuencia '{name}' paso {i} tras {hours} h")
    # B5. muchas horas sin lecturas y contador a cero, de día y de noche
    for lp, pp, name in ((nan, nan, "todo NaN"), (0.0, 0.0, "contador y solar a 0"), (0.0, 700.0, "contador a 0 con solar"),
                         (1e9, 1e9, "lecturas absurdas"), (-50.0, -50.0, "lecturas negativas")):
        f = SolarCand(prior, new_base())
        ts = warm(f, "2026-07-25 00:00", 30)
        for i in range(60):
            step(f, obs_of(ts, lp, pp), {}, times_from(ts, 24), f"B5 {name}, hora {i}")
            ts = ts + H
    # B6. tablas rotas o ausentes
    def broken(**changes):
        p = dict(prior)
        for k, v in changes.items():
            if v is None:
                p.pop(k, None)
            else:
                p[k] = v
        return p
    nan_how = [float("nan")] * 168
    priors = {"None": None, "vacío": {}, "sin load_reg3": broken(load_reg3=None), "load_how con NaN": broken(load_how=nan_how),
              "load_how a cero": broken(load_how=[0.0] * 168), "pv_clear con NaN": broken(pv_clear=[[float("nan")] * 24] * 12),
              "pv_clear corto": broken(pv_clear=[[100.0] * 12] * 12), "reg3 corto": broken(load_reg3=[[[0.0] * 4] * 3] * 24),
              "reg3 con NaN": broken(load_reg3=[[[float("nan")] * 4] * 24] * 24), "pv_a con NaN": broken(pv_a=[float("nan")] * 16),
              "pv_up con texto": broken(pv_up=["a", "b", "c", "d", "e"]), "pv_day a cero": broken(pv_day=[0.0] * 12),
              "pv_day enorme": broken(pv_day=[400.0] * 12), "load_lo con NaN": broken(load_lo=[float("nan")] * 24)}
    for name, pr in priors.items():
        for with_base in (True, False):
            f = SolarCand(pr, new_base(with_base))
            ts = warm(f, "2026-05-25 00:00", 30)
            for i in range(30):
                step(f, obs_of(ts, 1000.0 + 10 * i, 300.0 if 8 <= ts.hour <= 18 else 0.0), {}, times_from(ts, 24),
                     f"B6 tablas '{name}'{'' if with_base else ' y previsor de P2 sin perfil'} hora {i}")
                ts = ts + H
    kinds = {}
    for kind, tag, detail in PROBLEMS:
        kinds.setdefault(kind, []).append((tag, detail))
    print(f"   llamadas: {N_CALLS} | problemas: {len(PROBLEMS)}")
    for kind, items in kinds.items():
        print(f"   - {kind}: {len(items)} casos. Ejemplos:")
        seen = set()
        for tag, detail in items:
            key = tag.split(" tras ")[0].split(" hora ")[0].split(" paso ")[0]
            if key in seen:
                continue
            seen.add(key)
            if len(seen) > 8:
                break
            print(f"        {tag} -> {detail}")


def whole_agent(prior) -> None:
    print("C. EL AGENTE ENTERO CON OBSERVACIONES ESTROPEADAS")
    full = bench.hard_table()
    df = bench.split_frame(full, "val")
    mprior = bench.fit_market(None, full)
    agent = bench.hard_agent(mprior, {"cand": prior})
    agent.policy.netload = SolarCand(prior, agent.policy.forecaster)
    rng = np.random.default_rng(123)
    junk = [None, float("nan"), float("inf"), -float("inf"), "x", "", [], {}, -1.0, 0.0, 1e12, np.nan, True, "12,5", [1, 2], np.array([np.nan])]
    load_ = df.load_kw.to_numpy(float); pv = df.pv_kw.to_numpy(float)
    price = df.price_eur_kwh.to_numpy(float); co2 = df.co2_kg_kwh.to_numpy(float)
    ts = pd.DatetimeIndex(df.timestamp)
    p = HARD_PARAMS
    soc, infr, exc, bad, hostile = p.soc_init_kwh, 0, 0, 0, 0
    n = len(df)
    for t in range(n):
        prev = max(t - 1, 0)
        obs = {"timestamp": ts[t], "hour": int(ts[t].hour), "day_of_week": int(ts[t].dayofweek), "soc_kwh": float(soc),
               "soc_pct": float(soc / p.capacity_kwh), "soc_percent": float(soc / p.capacity_kwh * 100),
               "preu_actual": float(price[t]), "co2_actual": float(co2[t]),
               "preus_properes_24h": [float(v) for v in price[t:t + 3]], "co2_properes_24h": [float(v) for v in co2[t:t + 3]],
               "noves_dades_5min": {"ultim_consum_kw": float(load_[prev]), "ultima_solar_kw": float(pv[prev]), "irradiancia_wm2": 100.0,
                                    "temp_ambient_c": 20.0, "temp_panel_c": 25.0, "vent_ms": 0.0},
               "cap_max_kwh": float(p.capacity_kwh), "power_max_kw": float(p.max_charge_kw)}
        if rng.random() < 0.5:                       # la mitad de las horas llega algo roto (la carga, nunca: es del entorno)
            hostile += 1
            for _ in range(int(rng.integers(1, 4))):
                where = rng.choice(["top", "recent", "drop", "ts", "lists"])
                j = junk[int(rng.integers(len(junk)))]
                if where == "top":
                    k = rng.choice(["hour", "day_of_week", "preu_actual", "co2_actual", "noves_dades_5min", "preus_properes_24h", "co2_properes_24h"])
                    obs[k] = j
                elif where == "recent" and isinstance(obs.get("noves_dades_5min"), dict):
                    k = rng.choice(["ultim_consum_kw", "ultima_solar_kw", "irradiancia_wm2", "temp_ambient_c", "temp_panel_c", "vent_ms"])
                    obs["noves_dades_5min"][k] = j
                elif where == "drop":
                    obs.pop(rng.choice(["hour", "day_of_week", "noves_dades_5min", "preus_properes_24h", "timestamp", "co2_actual"]), None)
                elif where == "ts":
                    obs["timestamp"] = [None, "no es una fecha", pd.NaT, str(ts[t]), ts[t] - pd.Timedelta(days=40), ts[t] + pd.Timedelta(days=400),
                                        ts[t].to_pydatetime(), 12345, ts[t] + pd.Timedelta(minutes=30)][int(rng.integers(9))]
                else:
                    m = int(rng.integers(0, 5))
                    obs["preus_properes_24h"] = [float(v) for v in price[t:t + m]]
                    obs["co2_properes_24h"] = [float(v) for v in co2[t:t + int(rng.integers(0, 5))]]
        try:
            a_req = agent.act(obs)
            if not (isinstance(a_req, float) and math.isfinite(a_req)):
                bad += 1; a_req = 0.0
        except Exception:
            exc += 1; a_req = 0.0
        _, soc, i = apply_action(soc, float(a_req), p)
        infr += i
    print(f"   {n} horas, {hostile} con algo roto: excepciones {exc} | acciones no finitas {bad} | infracciones {infr} | "
          f"respaldos de la política {agent.policy.n_fallbacks}")


def cost(prior) -> None:
    print("D. COSTE DE LA PREVISIÓN")
    f = SolarCand(prior, new_base())
    ts = warm(f, "2026-06-24 00:00", 30)
    t0 = time.perf_counter()
    n = 2016
    for i in range(n):
        o = obs_of(ts, 1000.0, 300.0 if 8 <= ts.hour <= 19 else 0.0)
        f.update(o, {}); f.forecast(o, times_from(ts, 24)); f.adjust_action(-500.0, o, HARD_PARAMS)
        ts = ts + H
    dt = time.perf_counter() - t0
    t1 = time.perf_counter()
    for i in range(n):
        times_from(ts, 24)
    dt_times = time.perf_counter() - t1
    print(f"   update + forecast(24 h) + adjust_action: {1000 * (dt - dt_times) / n:.3f} ms por hora ({dt - dt_times:.2f} s en 2.016 h)")


if __name__ == "__main__":
    rules()
    PRIOR = to_prior(None)
    direct_calls(PRIOR)
    whole_agent(PRIOR)
    cost(PRIOR)
