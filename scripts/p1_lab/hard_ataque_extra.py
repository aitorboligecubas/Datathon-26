"""Ataques sueltos al agente del HARD MODE que no caben en los otros scripts. NO se empaqueta.

Owner: P1.

    python scripts/p1_lab/hard_ataque_extra.py

X1. La carga de la observación llega REDONDEADA (2 decimales, entero): ¿cuántas infracciones en el test
    entero? ¿Y con un margen de seguridad de 1 kW en vez de 0,0001 kW? ¿Cuánto cuesta ese margen?
X2. La misma instancia del agente se usa dos veces seguidas (prueba rápida de 48 pasos y luego el test).
X3. Cambio de hora: una hora repetida (26/10/2025 a las 02:00) o una hora que falta.
X4. La lista de previsión empieza en la hora SIGUIENTE (t+1, t+2, t+3) en vez de en la actual.
X5. Lecturas de consumo vacías (NaN) sueltas: un 10 % de las horas al azar, con consumo real.
X6. Un día entero (24 h) de lecturas vacías a media semana, con consumo real.
X7. Se agota el presupuesto de tiempo (40 s) y el agente pasa a la regla de respaldo: ¿qué score da esa regla?
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hard_ataque_comun as c  # noqa: E402
import battery.safety as safety  # noqa: E402

NAN = float("nan")
W = c.WEEK


def fila(nombre, r, base=None) -> dict:
    return {"caso": nombre, "score": r["score"], "dif": (r["score"] - base) if base is not None else NAN,
            "infr": r["infr"], "excep": r["excepciones"], "no_fin": r["no_finitas"],
            "vert_desc": r["vert_descarga"], "soc_final": r["soc_final"], "ms_max": r["ms_max"]}


def main() -> int:
    full, origen = c.episodio_test("copia")
    pm, ps = c.priors(origen)
    rows = []
    base = c.simular(c.agente(pm, ps), full)
    rows.append(fila("base: test entero", base, base["score"]))

    # X1 ---------------------------------------------------------------------------------------------
    margen = safety.SAFETY_MARGIN_KW
    for dec in (2, 0):
        fn = (lambda d: (lambda o, t: dict(o, soc_kwh=float(round(o["soc_kwh"], d)))))(dec)
        rows.append(fila(f"X1 carga redondeada a {dec} decimales (margen {margen} kW)", c.simular(c.agente(pm, ps), full, fn=fn), base["score"]))
    try:
        safety.SAFETY_MARGIN_KW = 1.0
        rows.append(fila("X1 margen de 1 kW, carga exacta", c.simular(c.agente(pm, ps), full), base["score"]))
        fn = lambda o, t: dict(o, soc_kwh=float(round(o["soc_kwh"], 0)))  # noqa: E731
        rows.append(fila("X1 margen de 1 kW, carga redondeada a entero", c.simular(c.agente(pm, ps), full, fn=fn), base["score"]))
    finally:
        safety.SAFETY_MARGIN_KW = margen

    # X2 ---------------------------------------------------------------------------------------------
    a = c.agente(pm, ps)
    c.simular(a, full.iloc[:48].reset_index(drop=True))
    rows.append(fila("X2 misma instancia: 48 pasos y luego el test entero", c.simular(a, full), base["score"]))
    a = c.agente(pm, ps)
    c.simular(a, full)
    rows.append(fila("X2 misma instancia: el test entero dos veces (2.ª vuelta)", c.simular(a, full), base["score"]))

    # X3 ---------------------------------------------------------------------------------------------
    tres = full.iloc[:3 * W].reset_index(drop=True)          # septiembre, octubre y noviembre: acaban igual
    b3 = c.simular(c.agente(pm, ps), tres)
    rows.append(fila("X3 tres semanas (sep-nov), tal cual", b3, b3["score"]))
    i = int(tres.index[tres.timestamp == pd.Timestamp("2025-10-26 02:00")][0])
    dup = pd.concat([tres.iloc[:i + 1], tres.iloc[i:i + 1], tres.iloc[i + 1:]], ignore_index=True)     # 02:00 dos veces
    rows.append(fila("X3 con las 02:00 del 26/10 repetidas (cambio de hora)", c.simular(c.agente(pm, ps), dup), b3["score"]))
    rows.append(fila("X3 sin las 02:00 del 26/10 (una hora que falta)", c.simular(c.agente(pm, ps), tres.drop(index=i).reset_index(drop=True)), b3["score"]))

    # X4 ---------------------------------------------------------------------------------------------
    dos = full.iloc[:2 * W].reset_index(drop=True)
    b_dos = c.simular(c.agente(pm, ps), dos)
    rows.append(fila("X4 dos semanas, tal cual", b_dos, b_dos["score"]))
    price, co2 = dos.price_eur_kwh.to_numpy(), dos.co2_kg_kwh.to_numpy()

    def desplazada(o, t):
        o["preus_properes_24h"] = [float(v) for v in price[t + 1:t + 4]]
        o["co2_properes_24h"] = [float(v) for v in co2[t + 1:t + 4]]
        return o
    rows.append(fila("X4 la lista empieza en la hora siguiente (t+1..t+3)", c.simular(c.agente(pm, ps), dos, fn=desplazada), b_dos["score"]))

    # X5 y X6 ----------------------------------------------------------------------------------------
    rng = np.random.default_rng(7)
    huecos = rng.random(len(full)) < 0.10

    def nan_suelto(o, t):
        if huecos[t]:
            o["noves_dades_5min"]["ultim_consum_kw"] = NAN
        return o
    rows.append(fila("X5 lectura de consumo vacía en el 10 % de las horas", c.simular(c.agente(pm, ps), full, fn=nan_suelto), base["score"]))

    def nan_un_dia(o, t):
        if 4 * W + 60 <= t < 4 * W + 84:
            o["noves_dades_5min"]["ultim_consum_kw"] = NAN
        return o
    r6 = c.simular(c.agente(pm, ps), full, fn=nan_un_dia)
    rows.append(fila("X6 24 h seguidas de lectura vacía (consumo real)", r6, base["score"]))

    def nan_dos_dias(o, t):
        if 4 * W + 60 <= t < 4 * W + 108:
            o["noves_dades_5min"]["ultim_consum_kw"] = NAN
        return o
    rows.append(fila("X6 48 h seguidas de lectura vacía (consumo real)", c.simular(c.agente(pm, ps), full, fn=nan_dos_dias), base["score"]))

    # X7 ---------------------------------------------------------------------------------------------
    rows.append(fila("X7 regla de respaldo desde el primer paso (time_budget_s = 0)", c.simular(c.agente(pm, ps, time_budget_s=0.0), full), base["score"]))
    rows.append(fila("X7 regla de respaldo en la segunda mitad (presupuesto agotado a mitad)", c.simular(c.agente(pm, ps, time_budget_s=2.4), full), base["score"]))

    out = pd.DataFrame(rows)
    pd.set_option("display.width", 250, "display.max_colwidth", 70)
    print(out.round(3).to_string(index=False))
    out_dir = c.REPO / "results" / "p1_hard"
    out_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_dir / "ataque_extra.csv", index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
