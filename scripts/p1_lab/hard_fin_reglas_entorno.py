"""Revisión de REGLAS Y ENTORNO del modo difícil: ¿hay alguna asimetría explotable en el simulador OFICIAL?

Owner: P1. NO se empaqueta. Ejecuta oficial/starter_kit/environment.py con agentes de juguete (instantáneo):

    python scripts/p1_lab/hard_fin_reglas_entorno.py

Qué prueba:
  A. Acciones raras (NaN, inf, -0.0, array, cadena, bool, justo en el límite): ¿alguna mueve energía sin infracción?
  B. Rendimiento de ida y vuelta medido en la red (¿0,9 exacto en los dos sentidos?).
  C. Excedente: cargar con sobrante solar es gratis; descargar por encima del consumo se pierde.
  D. Máscara de evaluate_results: qué pasa con la nota de una mitad si la carga se paga en la otra.
  E. La observación en t = 0 y al cruzar de una semana a la siguiente.
"""
import importlib.util
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
SPEC = {"capacity_kwh": 6000, "power_kw": 1500, "efficiency": 0.9, "soc_init": 0.5, "soc_min": 0.0,
        "soc_max": 1.0, "dt_hours": 1, "degradation": False}


def load_env():
    path = REPO / "oficial" / "starter_kit" / "environment.py"
    spec = importlib.util.spec_from_file_location("env_oficial", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def frame(load, pv, price=None, co2=None, start="2025-09-24"):
    n = len(load)
    return pd.DataFrame({
        "Fecha": pd.date_range(start, periods=n, freq="1h"),
        "load_kw": np.asarray(load, float), "pv_kw": np.asarray(pv, float),
        "precio_eur_per_kwh": np.full(n, 0.1) if price is None else np.asarray(price, float),
        "co2_kg_per_kwh": np.full(n, 0.1) if co2 is None else np.asarray(co2, float),
    })


def one(mod, action, soc0=3000.0, load=1000.0, pv=0.0):
    env = mod.CampusBatteryEnv(frame([load, load], [pv, pv]), spec=SPEC)
    env.reset()
    env.soc = soc0
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            env.step(action)
    except Exception as e:   # noqa: BLE001
        return f"EXCEPCIÓN {type(e).__name__}: {e}"
    return (f"soc {soc0:.3f} -> {float(env.soc):.6f} | red {env.grid[0]:.6f} | vertido {env.exports[0]:.6f} | "
            f"infracciones {env.clipped + env.violations}")


def main() -> int:
    mod = load_env()
    eta = 0.9 ** 0.5
    print("== A. Acciones raras (batería a 3.000 de 6.000 kWh, consumo 1.000 kW, sin solar) ==")
    cases = [
        ("0.0", 0.0), ("-0.0", -0.0), ("NaN", float("nan")), ("+inf", float("inf")), ("-inf", float("-inf")),
        ("1500 exacto", 1500.0), ("1500 + 1 ulp", float(np.nextafter(1500.0, np.inf))),
        ("-1500 exacto", -1500.0), ("-1500 - 1 ulp", float(np.nextafter(-1500.0, -np.inf))),
        ("array([200.])", np.array([200.0])), ("[200.0] lista", [200.0]), ("'200' cadena", "200"),
        ("True", True), ("np.float32(200.1)", np.float32(200.1)), ("1e-300", 1e-300), ("-1e-300", -1e-300),
        ("5e-324 (subnormal)", 5e-324),
    ]
    for name, a in cases:
        print(f"  {name:22s} {one(mod, a)}")

    print("== A2. Justo en el límite de capacidad ==")
    soc0 = 5000.0
    exact_c = (6000.0 - soc0) / eta
    print(f"  cargar hasta lleno exacto      {one(mod, exact_c, soc0)}")
    print(f"  cargar lleno + 1 ulp           {one(mod, float(np.nextafter(exact_c, np.inf)), soc0)}")
    print(f"  cargar 1e-9 con batería llena  {one(mod, 1e-9, 6000.0)}")
    print(f"  cargar 5e-324 con bat. llena   {one(mod, 5e-324, 6000.0)}")
    soc0 = 800.0
    exact_d = -(soc0 - 0.0) * eta
    print(f"  descargar hasta vacío exacto   {one(mod, exact_d, soc0)}")
    print(f"  descargar vacío - 1 ulp        {one(mod, float(np.nextafter(exact_d, -np.inf)), soc0)}")
    print(f"  descargar -1e-9 con bat. vacía {one(mod, -1e-9, 0.0)}")
    # ¿Se puede pasar de 6.000 o bajar de 0 por redondeo y que el recorte regale energía?
    worst_hi, worst_lo = 0.0, 0.0
    rng = np.random.default_rng(0)
    for _ in range(20000):
        up = rng.random() < 0.5
        # dentro de la potencia: a menos de 1.500 kW del límite de carga o de descarga
        s = float(6000.0 - rng.uniform(0, 1500.0 * eta)) if up else float(rng.uniform(0, 1500.0 / eta))
        env = mod.CampusBatteryEnv(frame([1000.0], [0.0]), spec=SPEC)
        env.reset()
        env.soc = s
        env.step((6000.0 - s) / eta if up else -(s * eta))
        worst_hi = max(worst_hi, float(env.soc) - 6000.0)
        worst_lo = min(worst_lo, float(env.soc))
        assert env.clipped + env.violations == 0, (s, env.clipped, env.violations)
    print(f"  20.000 llenados/vaciados exactos: 0 infracciones; exceso máx. {worst_hi:.2e}, defecto mín. {worst_lo:.2e} kWh")

    print("== B. Ida y vuelta medida en la red ==")
    env = mod.CampusBatteryEnv(frame([2000.0] * 4, [0.0] * 4), spec=SPEC)
    env.reset()
    env.soc = 0.0
    env.step(1000.0)
    stored = float(env.soc)
    env.step(-stored * eta)
    print(f"  compro 1.000 kWh de más -> guardo {stored:.4f} -> devuelvo {2000.0 - env.grid[1]:.4f} kWh "
          f"(rendimiento {(2000.0 - env.grid[1]) / 1000.0:.6f}), batería final {float(env.soc):.2e}, "
          f"infracciones {env.clipped + env.violations}")

    print("== C. Excedente ==")
    print(f"  cargar 1.000 con 1.500 kW de sobrante solar: {one(mod, 1000.0, 3000.0, load=500.0, pv=2000.0)}")
    print(f"  descargar 1.500 con 600 kW de consumo:        {one(mod, -1500.0, 3000.0, load=600.0, pv=0.0)}")
    print(f"  descargar 500 con sobrante solar:             {one(mod, -500.0, 3000.0, load=500.0, pv=2000.0)}")

    print("== D. Máscara: la carga se paga en una mitad y se usa en la otra ==")
    # 8 horas iguales (consumo 2.000, peso constante). Carga en las horas 0-3, descarga en las 4-7.
    env = mod.CampusBatteryEnv(frame([2000.0] * 8, [0.0] * 8), spec=SPEC)
    env.reset()
    env.soc = 0.0
    for a in (1500.0, 1500.0, 1500.0, 1500.0):
        env.step(a)
    full_soc = float(env.soc)
    for _ in range(4):
        env.step(-min(1500.0, float(env.soc) * eta))
    m_first = np.array([True] * 4 + [False] * 4)
    print(f"  batería tras cargar: {full_soc:.1f} kWh; episodio entero: {env.evaluate_results()['score']:.2f} | "
          f"mitad de la carga: {env.evaluate_results(mask=m_first)['score']:.2f} (se trunca a 0) | "
          f"mitad de la descarga: {env.evaluate_results(mask=~m_first)['score']:.2f}")
    # Infracciones fuera de la máscara: no cuentan en la nota de la máscara.
    env = mod.CampusBatteryEnv(frame([2000.0] * 8, [0.0] * 8), spec=SPEC)
    env.reset()
    for a in (9999.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0):
        env.step(a)
    print(f"  1 infracción en la hora 0: entero {env.evaluate_results()['infraccions']} | "
          f"máscara sin la hora 0: {env.evaluate_results(mask=~m_first)['infraccions']} | "
          f"máscara con la hora 0: {env.evaluate_results(mask=m_first)['infraccions']}")

    print("== E. Observación en t = 0 y en el cruce de semanas ==")
    load = np.arange(100.0, 100.0 + 6)
    ts = list(pd.date_range("2025-09-30 21:00", periods=3, freq="1h")) + list(pd.date_range("2025-10-25", periods=3, freq="1h"))
    df = frame(load, [0.0] * 6, price=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
    df["Fecha"] = ts
    env = mod.CampusBatteryEnv(df, spec=SPEC)
    obs = env.reset()
    print(f"  t=0: 'ultim_consum_kw' = {obs['noves_dades_5min']['ultim_consum_kw']} (el consumo de la PROPIA hora 0 es {load[0]})")
    for _ in range(3):
        print(f"  {obs['timestamp']}  precios[:3] = {obs['preus_properes_24h'][:3]}  último consumo = {obs['noves_dades_5min']['ultim_consum_kw']}")
        obs, _ = env.step(0.0)
    print(f"  {obs['timestamp']}  precios[:3] = {obs['preus_properes_24h'][:3]}  último consumo = {obs['noves_dades_5min']['ultim_consum_kw']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
