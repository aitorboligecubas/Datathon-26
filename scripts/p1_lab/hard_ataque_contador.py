"""Ataque 4 al agente del HARD MODE: semanas sin contador, lecturas vacías y averías. NO se empaqueta.

Owner: P1. En el train, noviembre no tiene datos de la planta (ni contador, ni inversores, ni meteo): en el
test, esa semana puede llegar con el consumo y la solar a 0. Aquí se mide qué hace el agente en ese caso y
en otros parecidos: ¿tira energía (descarga contra un consumo nulo)? ¿compra de más o a mala hora?

    python scripts/p1_lab/hard_ataque_contador.py

Episodio: las 12 semanas del test (hard_ataque_comun.episodio_test). Para cada escenario:
    score, óptimo (con todo el futuro) y hueco = óptimo - score: si el hueco crece frente al episodio normal,
        el agente lo lleva peor que una semana normal;
    en las horas afectadas: kWh comprados (con consumo 0 todo lo comprado es carga de batería), a qué peso
        medio frente al de las 4 horas más baratas de esa semana, kWh tirados por descargar y carga al final.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hard_ataque_comun as c  # noqa: E402
from battery.baselines import OracleAgent  # noqa: E402

NAN = float("nan")
W = c.WEEK


def semana(i: int) -> slice:
    return slice(i * W, (i + 1) * W)


def escenarios(full: pd.DataFrame) -> list:
    """(nombre, episodio, máscara de horas afectadas, deformación de la observación o None)."""
    out = []
    n = len(full)
    nada = np.zeros(n, dtype=bool)
    out.append(("0. normal (noviembre con el consumo de octubre)", full, nada, None))

    d = full.copy(); m = nada.copy(); m[semana(c.NOV)] = True
    d.loc[m, ["load_kw", "pv_kw"]] = 0.0
    out.append(("1. noviembre a 0 (consumo y solar)", d, m, None))

    d2 = full.copy(); d2.loc[m, "load_kw"] = 0.0
    out.append(("2. noviembre: consumo a 0, la solar sigue", d2, m, None))

    def nan_si_cero(o, t):                      # el entorno cuenta 0, pero la lectura llega vacía
        if o["noves_dades_5min"]["ultim_consum_kw"] == 0.0:
            o["noves_dades_5min"]["ultim_consum_kw"] = NAN
            o["noves_dades_5min"]["ultima_solar_kw"] = NAN
        return o
    out.append(("3. noviembre a 0 y la lectura llega vacía (NaN)", d, m, nan_si_cero))

    def nan_en_nov(o, t):                       # lectura vacía, pero el campus consume con normalidad
        if c.NOV * W < t <= (c.NOV + 1) * W:
            o["noves_dades_5min"]["ultim_consum_kw"] = NAN
        return o
    out.append(("4. noviembre: lectura vacía (NaN) con consumo REAL", full, m, nan_en_nov))

    def nan_siempre(o, t):
        o["noves_dades_5min"]["ultim_consum_kw"] = NAN
        return o
    out.append(("5. lectura de consumo vacía TODO el test, consumo real", full, ~nada, nan_siempre))

    d3 = full.copy(); m3 = nada.copy()
    for wk, start in ((4, 58), (7, 34), (9, 100)):          # tres averías de 14 h (la del train dura 14 h)
        m3[wk * W + start: wk * W + start + 14] = True
    d3.loc[m3, ["load_kw", "pv_kw"]] = 0.0
    out.append(("6. tres averías de 14 h a media semana", d3, m3, None))

    d4 = full.copy(); m4 = nada.copy(); m4[5 * W + 40: 5 * W + 100] = True
    d4.loc[m4, ["load_kw", "pv_kw"]] = 0.0
    out.append(("7. avería de 60 h a media semana", d4, m4, None))

    d5 = full.copy(); m5 = nada.copy(); m5[semana(11)] = True
    d5.loc[m5, "pv_kw"] = 0.0
    out.append(("8. agosto sin solar (inversores caídos), consumo real", d5, m5, None))

    d6 = full.copy(); m6 = nada.copy(); m6[semana(0)] = True
    d6.loc[m6, ["load_kw", "pv_kw"]] = 0.0
    out.append(("9. la PRIMERA semana a 0", d6, m6, None))
    return out


def main() -> int:
    full, origen = c.episodio_test("copia")
    pm, ps = c.priors(origen)
    rows = []
    for nombre, df, mask, fn in escenarios(full):
        r = c.simular(c.agente(pm, ps), df, fn=fn)
        w = c.pesos(df)
        o = c.simular(OracleAgent(df, *w, p=c.HARD_PARAMS), df)
        log = r["log"]
        peso = w[0] * df.co2_kg_kwh.to_numpy() + w[1] * df.price_eur_kwh.to_numpy()
        imp = log.import_kw.to_numpy(); exp = log.export_kw.to_numpy(); act = log.action_kw.to_numpy()
        zero = mask & (df.load_kw.to_numpy() == 0.0)
        comprado = float(imp[zero].sum())
        peso_pagado = float((imp[zero] * peso[zero]).sum() / comprado) if comprado > 1 else NAN
        barato = float(np.sort(peso[zero])[:4].mean()) if zero.sum() >= 4 else NAN
        last = int(np.flatnonzero(mask)[-1]) if mask.any() else -1
        rows.append({"escenario": nombre, "score": r["score"], "optimo": o["score"], "hueco": o["score"] - r["score"],
                     "infr": r["infr"], "comprado_kwh": comprado, "peso_pagado": peso_pagado, "peso_4h_baratas": barato,
                     "tirado_descarga_kwh": float(exp[mask & (act < -1e-6)].sum()),
                     "solar_no_guardada_kwh": float(exp[mask & (act >= -1e-6)].sum()),
                     "soc_al_final_kwh": float(log.soc_kwh.iloc[last]) if last >= 0 else NAN,
                     "h_sin_actuar_pct": 100.0 * float((np.abs(act[mask]) < 1e-6).mean()) if mask.any() else NAN})
    out = pd.DataFrame(rows)
    out["hueco_extra"] = out["hueco"] - out["hueco"].iloc[0]
    pd.set_option("display.width", 280, "display.max_colwidth", 60)
    print(out.round(3).to_string(index=False))
    out_dir = c.REPO / "results" / "p1_hard"
    out_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_dir / "ataque_contador.csv", index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
