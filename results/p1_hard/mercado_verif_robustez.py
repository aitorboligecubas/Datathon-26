"""Verificación del candidato "mercado": entradas raras (P1, sábado 14/11). No se empaqueta.

Llama a MarketCand.forecast (scripts/p1_lab/hard_market_cand.py) y al agente entero (HardPolicy.act) con
observaciones estropeadas. Cada caso tiene que devolver, sin lanzar excepciones, valores finitos y >= 0 de
la longitud pedida (previsor) o una acción finita y válida (agente).

    python results/p1_hard/mercado_verif_robustez.py
"""
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
for _p in (str(REPO / "src"), str(REPO / "scripts"), str(REPO / "scripts" / "p1_lab")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hard_market_cand as L  # noqa: E402
from battery.hard import HardPolicy  # noqa: E402
from battery.obs import Obs  # noqa: E402
from battery.sim import apply_action  # noqa: E402

PRIOR = json.loads((REPO / "models" / "hard_market.json").read_text(encoding="utf-8"))
NAN = float("nan")
FAILS = []


def hours(start: str, n: int) -> list:
    t0 = pd.Timestamp(start)
    return [t0 + pd.Timedelta(hours=k) for k in range(n)]


def safe_int(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def mk_obs(price, co2, ts=None) -> Obs:
    return Obs(hour=safe_int(getattr(ts, "hour", 0)), weekday=0, soc_kwh=3000.0,
               price=price, co2=co2, load_prev_kw=1000.0, pv_prev_kw=0.0, timestamp=ts)


def check_fc(label: str, m, obs, times, weather=None) -> None:
    try:
        out = m.forecast(obs, times, weather)
        p, c = out
        ok = (len(p) == len(times) and len(c) == len(times) and bool(np.isfinite(p).all()) and bool(np.isfinite(c).all())
              and bool((np.asarray(p) >= 0).all()) and bool((np.asarray(c) >= 0).all()))
        if not ok:
            FAILS.append(f"PREVISOR {label}: salida mala: price={np.asarray(p)[:6]} co2={np.asarray(c)[:6]} (pedidas {len(times)})")
    except Exception as e:      # noqa: BLE001
        FAILS.append(f"PREVISOR {label}: EXCEPCIÓN {type(e).__name__}: {e}")


def forecaster_cases() -> int:
    n = 0
    arr = np.array
    good_p, good_c = arr([0.12, 0.13, 0.11]), arr([0.10, 0.11, 0.09])
    starts = {"primera hora de una semana del test (con semilla)": "2025-09-24 00:00",
              "mitad de semana": "2025-12-27 13:00", "última hora del mes": "2026-01-31 23:00",
              "última hora del test": "2026-08-31 23:00", "mes sin semilla cerca (día 5)": "2026-03-05 10:00",
              "noviembre": "2025-11-24 00:00", "cambio de hora (26/10 02:00)": "2025-10-26 02:00",
              "fecha lejana": "2031-02-28 22:00", "fecha antigua": "1999-12-31 23:00", "29 de febrero": "2028-02-29 05:00"}
    prices = {"normal": (good_p, good_c), "NaN en la hora actual": (arr([NAN, 0.13, 0.11]), good_c),
              "todo NaN": (arr([NAN] * 3), arr([NAN] * 3)), "precio 0": (arr([0.0, 0.0, 0.0]), good_c),
              "precio negativo": (arr([-0.05, 0.02, -0.01]), good_c), "infinito": (arr([np.inf, 0.1, 0.1]), arr([0.1, -np.inf, 0.1])),
              "enorme": (arr([1e9, 1e-12, 5.0]), arr([1e6, 1e-9, 3.0])), "listas": ([0.12, 0.13, 0.11], [0.10, 0.11, 0.09]),
              "1 valor": (arr([0.12]), arr([0.10])), "2 valores": (arr([0.12, 0.13]), arr([0.10, 0.11])),
              "vacío": (arr([]), arr([])), "longitudes distintas": (good_p, arr([0.10, 0.11])),
              "24 valores": (np.full(24, 0.1), np.full(24, 0.1)), "enteros": (arr([1, 2, 3]), arr([1, 2, 3]))}
    weathers = {"None": None, "vacío": {}, "NaN": {"irradiancia_wm2": NAN, "temp_ambient_c": NAN, "temp_panel_c": NAN, "vent_ms": NAN},
                "texto": {"irradiancia_wm2": "x"}}
    for sname, s in starts.items():
        for pname, (p, c) in prices.items():
            for H in (1, 2, 3, 4, 24, 30):
                for wname, w in weathers.items():
                    if wname != "None" and (H != 24 or pname not in ("normal", "todo NaN")):
                        continue
                    m = L.MarketCand(PRIOR)
                    times = hours(s, H)
                    check_fc(f"[{sname} | {pname} | H={H} | meteo {wname}]", m, mk_obs(p, c, times[0]), times, w)
                    n += 1
    # secuencias con estado: una misma instancia, varias llamadas seguidas
    seqs = {"salto de un mes": ["2025-09-30 22:00", "2025-09-30 23:00", "2025-10-25 00:00", "2025-10-25 01:00"],
            "salto atrás de un año": ["2026-08-31 22:00", "2025-09-24 00:00", "2025-09-24 01:00"],
            "misma hora dos veces": ["2025-10-26 02:00", "2025-10-26 02:00", "2025-10-26 03:00"],
            "hora que falta": ["2026-03-29 01:00", "2026-03-29 03:00", "2026-03-29 04:00"],
            "saltos enormes": ["2025-09-24 00:00", "2045-01-01 00:00", "1990-06-01 12:00", "2025-09-24 01:00"],
            "desorden": ["2025-12-27 05:00", "2025-12-27 03:00", "2025-12-27 04:00", "2025-12-26 23:00"]}
    for qname, seq in seqs.items():
        for pname, (p, c) in prices.items():
            m = L.MarketCand(PRIOR)
            for j, s in enumerate(seq):
                times = hours(s, 24)
                check_fc(f"[secuencia {qname} paso {j} | {pname}]", m, mk_obs(p, c, times[0]), times, {})
                n += 1
    # fechas raras dentro de `times`
    m = L.MarketCand(PRIOR)
    odd = {"times vacío": [], "times[0] None": [None, None, None], "None en medio": hours("2025-09-24 00:00", 3) + [None] * 21,
           "NaT": [pd.NaT] * 24, "con minutos": [pd.Timestamp("2025-09-24 00:37") + pd.Timedelta(hours=k) for k in range(24)],
           "con zona horaria": list(pd.date_range("2025-09-24", periods=24, freq="h", tz="Europe/Madrid")),
           "repetidas": [pd.Timestamp("2025-09-24 00:00")] * 24, "al revés": hours("2025-09-24 00:00", 24)[::-1],
           "salto dentro del plan": hours("2025-09-30 22:00", 2) + hours("2025-10-25 00:00", 22),
           "datetime de Python": [t.to_pydatetime() for t in hours("2025-09-24 00:00", 24)],
           "numpy datetime64": [np.datetime64("2025-09-24T00") + np.timedelta64(k, "h") for k in range(24)],
           "cadenas": ["2025-09-24 00:00"] * 24, "muy largo (200 h)": hours("2025-09-24 00:00", 200)}
    for oname, times in odd.items():
        for pname, (p, c) in prices.items():
            check_fc(f"[times {oname} | {pname}]", m, mk_obs(p, c, times[0] if times else None), times, None)
            n += 1
    # tablas rotas
    broken = {"sin cand": {k: v for k, v in PRIOR.items() if k != "cand"}, "cand None": {**PRIOR, "cand": None},
              "cand vacío": {**PRIOR, "cand": {}}, "sin semilla": {**PRIOR, "cand": {**PRIOR["cand"], "seed": None}},
              "semilla con basura": {**PRIOR, "cand": {**PRIOR["cand"], "seed": [None, 3, {"start": "x"}, {"start": 10 ** 12, "price": [1.0], "co2": [1.0]},
                                                                         {"start": 17750000, "price": [None, "a", NAN, -1.0, 0.0], "co2": [0.1]}]}},
              "feats desconocidas": {**PRIOR, "cand": {**PRIOR["cand"], "feats": ["zz"] * 13}},
              "tablas con NaN": {**PRIOR, "cand": {**PRIOR["cand"], "full": {"price": [[NAN] * 14] * 21, "co2": [[NAN] * 14] * 21}}},
              "sin reg": {k: v for k, v in PRIOR.items() if k != "reg"}, "prior None": None, "prior vacío": {},
              "perfil con ceros": {**PRIOR, "price": np.zeros((12, 3, 24)).tolist()},
              "perfil con NaN": {**PRIOR, "co2": np.full((12, 3, 24), NAN).tolist()}}
    for bname, prior in broken.items():
        try:
            m = L.MarketCand(prior)
        except Exception as e:      # noqa: BLE001
            FAILS.append(f"PREVISOR [tablas {bname}]: EXCEPCIÓN al crear: {type(e).__name__}: {e}")
            continue
        for s in ("2025-09-24 00:00", "2025-09-24 01:00", "2025-09-26 12:00"):
            times = hours(s, 24)
            check_fc(f"[tablas {bname} | {s}]", m, mk_obs(good_p, good_c, times[0]), times, None)
            n += 1
    return n


def raw_obs(ts, soc, price, co2, recent, **extra) -> dict:
    o = {"timestamp": ts, "hour": safe_int(getattr(ts, "hour", 0)), "day_of_week": safe_int(getattr(ts, "dayofweek", 0)),
         "soc_kwh": soc, "soc_pct": soc / 6000.0, "soc_percent": soc / 60.0, "preu_actual": price[0] if price else NAN,
         "co2_actual": co2[0] if co2 else NAN, "preus_properes_24h": price, "co2_properes_24h": co2,
         "noves_dades_5min": recent, "cap_max_kwh": 6000.0, "power_max_kw": 1500.0}
    o.update(extra)
    return o


def agent_cases() -> int:
    """El agente entero con el candidato dentro: episodios cortos con observaciones estropeadas."""
    n = 0
    rng = np.random.default_rng(7)
    good_recent = {"ultim_consum_kw": 1100.0, "ultima_solar_kw": 300.0, "irradiancia_wm2": 200.0, "temp_ambient_c": 18.0,
                   "temp_panel_c": 25.0, "vent_ms": 2.0}
    recents = {"normal": good_recent, "todo NaN": {k: NAN for k in good_recent}, "vacío": {}, "None": None,
               "meteo NaN": {**good_recent, "irradiancia_wm2": NAN, "temp_ambient_c": NAN, "temp_panel_c": NAN, "vent_ms": NAN},
               "texto": {k: "?" for k in good_recent}, "lista": [1, 2, 3]}
    plists = {"3 valores": lambda: (list(rng.uniform(0.05, 0.3, 3)), list(rng.uniform(0.02, 0.3, 3))),
              "1 valor": lambda: ([0.1], [0.1]), "2 valores": lambda: ([0.1, 0.2], [0.1, 0.2]), "vacío": lambda: ([], []),
              "NaN": lambda: ([NAN, 0.1, NAN], [0.1, NAN, NAN]), "24 valores": lambda: (list(rng.uniform(0.05, 0.3, 24)), list(rng.uniform(0.02, 0.3, 24))),
              "negativos": lambda: ([-0.1, 0.0, 0.2], [0.0, 0.0, 0.0]), "None": lambda: (None, None)}
    seqs = {"semana normal": hours("2025-09-24 00:00", 30),
            "final de mes y salto": hours("2025-09-30 20:00", 4) + hours("2025-10-25 00:00", 6),
            "final del test": hours("2026-08-31 18:00", 6),
            "salto de un mes sin avisar": hours("2025-12-27 10:00", 3) + hours("2026-01-27 13:00", 3),
            "fecha None": [None] * 4, "fecha texto": ["2025-09-24 00:00:00", "2025-09-24 01:00:00", "2025-09-24 02:00:00"],
            "NaT": [pd.NaT] * 3, "hacia atrás": hours("2025-09-26 05:00", 3)[::-1]}
    for qname, seq in seqs.items():
        for rname, recent in recents.items():
            for pname, pf in plists.items():
                try:
                    pol = HardPolicy()
                except Exception as e:      # noqa: BLE001
                    FAILS.append(f"AGENTE: EXCEPCIÓN al crear: {type(e).__name__}: {e}")
                    return n
                soc = 3000.0
                for j, ts in enumerate(seq):
                    price, co2 = pf()
                    label = f"[{qname} paso {j} | lectura {rname} | precios {pname}]"
                    try:
                        a = pol.act(raw_obs(ts, soc, price, co2, recent))
                        a = float(a)
                        if not math.isfinite(a):
                            FAILS.append(f"AGENTE {label}: acción no finita {a}")
                            a = 0.0
                        _, soc, infr = apply_action(soc, a, pol.p)
                        if infr:
                            FAILS.append(f"AGENTE {label}: INFRACCIÓN con acción {a:.1f} y carga {soc:.1f}")
                    except Exception as e:      # noqa: BLE001
                        FAILS.append(f"AGENTE {label}: EXCEPCIÓN {type(e).__name__}: {e}")
                    n += 1
    return n


def main() -> int:
    t0 = time.perf_counter()
    n1 = forecaster_cases()
    t1 = time.perf_counter()
    n2 = agent_cases()
    t2 = time.perf_counter()
    print(f"previsor: {n1} llamadas en {t1 - t0:.1f} s | agente: {n2} pasos en {t2 - t1:.1f} s | fallos: {len(FAILS)}")
    seen = set()
    for f in FAILS:
        key = f.split("|")[0] + f.split(":")[-1][:60]
        if key in seen:
            continue
        seen.add(key)
        print("  -", f)
    print(f"({len(seen)} fallos distintos mostrados de {len(FAILS)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
