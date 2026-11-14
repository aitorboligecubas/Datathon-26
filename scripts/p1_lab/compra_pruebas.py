"""Pruebas del candidato "compra". NO se empaqueta.

    python scripts/p1_lab/compra_pruebas.py

1. Las cuentas del precio de reserva: la normal acumulada, la parada óptima y sus límites.
2. Observaciones hostiles (las de scripts/p1_auditoria.py) y una semana sin datos con pesos rotos:
   ni excepciones, ni respuestas no numéricas, ni infracciones.
3. Un episodio con noviembre a cero: la regla nueva se usa de verdad (no cae en el respaldo), el agente no
   recurre a la regla de emergencia y el tiempo por paso sigue lejos del límite.
"""
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "p1_lab"))

import cand_compra as C  # noqa: E402
import p1_banco as B  # noqa: E402
from battery.adapter import make_official_obs  # noqa: E402
from battery.sim import apply_action  # noqa: E402
from p1_auditoria import hostile_obs  # noqa: E402

OK = True


def check(name: str, cond: bool, detail: str = "") -> None:
    global OK
    OK = OK and bool(cond)
    print(f"  [{'ok' if cond else 'FALLO'}] {name} {detail}")


def cuentas() -> None:
    print("1. cuentas del precio de reserva")
    x = np.linspace(-6, 6, 241)
    exact = np.array([0.5 * (1 + math.erf(v / math.sqrt(2))) for v in x])
    check("normal acumulada", np.abs(C.normal_cdf(x) - exact).max() < 1e-6)
    s = 0.17
    # Nivel conocido (tau -> 0): es la recursión clásica c_1 = E[v], c_k = E[min(v, c_(k-1))].
    z = C.GRID_Z * s
    c = float((np.exp(z) * C.GRID_P).sum())
    ref = [c]
    for _ in range(5):
        c = float((np.minimum(np.exp(z), c) * C.GRID_P).sum())
        ref.append(c)
    got = [C.wait_factor(3, [0.0] * k, s, 1e-6) for k in range(1, 7)]
    check("nivel conocido = recursión clásica", np.allclose(got, ref, atol=2e-4), f"{np.round(got, 4)}")
    check("más días por delante, reserva más baja", all(a > b for a, b in zip(got, got[1:])))
    # Con el nivel incierto se espera menos de la espera que si el nivel se conociera (se compra antes).
    unknown = [C.wait_factor(1, [0.0] * k, s, 0.2) for k in range(1, 7)]
    check("nivel incierto: factores finitos y decrecientes", all(math.isfinite(a) for a in unknown)
          and all(a >= b for a, b in zip(unknown, unknown[1:])), f"{np.round(unknown, 4)}")
    we = C.wait_factor(3, [0.0, 0.0, C.WEEKEND_SHIFT, C.WEEKEND_SHIFT], s, 0.2)
    check("con fin de semana por delante se espera pagar menos", we < C.wait_factor(3, [0.0] * 4, s, 0.2), f"{we:.4f}")
    thin = C.wait_factor(3, [0.0] * 3, s, 0.2, margin=0.0)
    fat = C.wait_factor(3, [0.0] * 3, s, 0.2, margin=1.0)
    check("si la carga puede valer poco, la reserva baja", thin < fat <= C.wait_factor(3, [0.0] * 3, s, 0.2) + 1e-9,
          f"margen 0: {thin:.4f}, margen 1: {fat:.4f}")
    check("sin referencia ni días vistos no hay reserva", math.isinf(C.wait_factor(0, [0.0], s, float("inf"))))
    check("lunes 24-11-2025 no es fin de semana y sábado 29 sí",
          not C.is_weekend(pd.Timestamp("2025-11-24").toordinal()) and C.is_weekend(pd.Timestamp("2025-11-29").toordinal()))


def hostiles(n: int = 6000) -> None:
    print("2. observaciones hostiles")
    rng = np.random.default_rng(123)
    agent, errors, nonfinite, infr = C.make_agent(), 0, 0, 0
    for i in range(n):
        if i % 1500 == 0:
            agent = C.make_agent()
        obs, soc = hostile_obs(rng)
        try:
            a = agent.act(obs)
        except Exception:
            errors += 1
            continue
        if not isinstance(a, float) or not math.isfinite(a):
            nonfinite += 1
            continue
        infr += apply_action(min(max(soc, 0.0), 2000.0), a)[2]
    check(f"{n} observaciones sueltas", errors + nonfinite + infr == 0, f"excepciones {errors}, no numéricas {nonfinite}, infracciones {infr}")
    # Una semana sin datos seguida, con precios y CO2 a 0, negativos, NaN o enormes en algunas horas.
    agent, errors, nonfinite, infr, soc = C.make_agent(), 0, 0, 0, 1000.0
    hours = pd.date_range("2025-10-25", periods=168, freq="h").append(pd.date_range("2025-11-24", periods=168, freq="h"))
    price = rng.lognormal(-2.2, 0.5, len(hours) + 24)
    co2 = rng.lognormal(-2.5, 0.5, len(hours) + 24)
    for arr in (price, co2):
        idx = rng.integers(0, len(arr), size=60)
        arr[idx] = rng.choice([0.0, -0.05, np.nan, 1e9, np.inf], size=60)
    for t, ts in enumerate(hours):
        load = float(rng.uniform(700, 1500)) if t < 168 else 0.0
        obs = make_official_obs(ts, soc, price[t:t + 24], co2[t:t + 24], load, 0.0)
        obs["preus_properes_24h"], obs["co2_properes_24h"] = list(price[t:t + 24]), list(co2[t:t + 24])
        obs["preu_actual"], obs["co2_actual"] = float(price[t]), float(co2[t])
        try:
            a = agent.act(obs)
        except Exception:
            errors += 1
            continue
        if not isinstance(a, float) or not math.isfinite(a):
            nonfinite += 1
            continue
        applied, soc, k = apply_action(soc, a)
        infr += k
    check("semana sin datos con pesos rotos", errors + nonfinite + infr == 0, f"excepciones {errors}, no numéricas {nonfinite}, infracciones {infr}")


def episodio() -> None:
    print("3. episodio con noviembre a cero (dev-00 del banco)")
    df = B.make_episode(1000, "nov0")
    agent = C.make_agent()
    pol = agent.policy
    calls = {"nueva": 0, "sin_regla": 0}
    inner = pol.reserve_now

    def spy(obs):
        r = inner(obs)
        calls["nueva" if math.isfinite(r) else "sin_regla"] += 1
        return r

    pol.reserve_now = spy
    soc, times, infr = 1000.0, [], 0
    load, pv = df.load_kw.to_numpy(), df.pv_kw.to_numpy()
    price, co2 = df.price_eur_kwh.to_numpy(), df.co2_kg_kwh.to_numpy()
    for t in range(len(df)):
        prev = t - 1 if t > 0 else t
        obs = make_official_obs(df.timestamp[t], soc, price[t:t + 24], co2[t:t + 24], load[prev], pv[prev])
        t0 = time.perf_counter()
        a = agent.act(obs)
        times.append(time.perf_counter() - t0)
        _, soc, k = apply_action(soc, a)
        infr += k
    ms = 1000 * np.array(times)
    zero = ms[336:504]
    check("la regla nueva da la reserva en la semana sin datos", calls["nueva"] >= 120 and calls["sin_regla"] <= 1,
          f"{calls['nueva']} horas con la regla nueva, {calls['sin_regla']} sin ella (la hora 00 del último día)")
    check("sin regla de emergencia ni infracciones", pol.n_fallbacks == 0 and infr == 0, f"respaldos {pol.n_fallbacks}, infracciones {infr}")
    check("tiempo por paso", ms.mean() < 5 and np.percentile(ms, 99) < 10,
          f"media {ms.mean():.2f} ms, p99 {np.percentile(ms, 99):.2f} ms, máx {ms.max():.2f} ms; "
          f"en la semana sin datos {zero.mean():.2f} ms; proyección a 2.016 pasos {ms.mean() * 2.016:.1f} s")


def main() -> int:
    cuentas()
    hostiles()
    episodio()
    print("TODO BIEN" if OK else "HAY FALLOS")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
