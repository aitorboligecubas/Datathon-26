"""Ataques 1 y 2 al agente del HARD MODE: formato de la observación e infracciones. NO se empaqueta.

Owner: P1. Deforma la observación de muchas maneras y simula con la física real del entorno
(battery.sim.apply_action). Para cada caso cuenta: excepciones que salen de act(), acciones no finitas,
infracciones, % de horas con acción 0 (un agente "parado" no da error: solo deja de puntuar) y el score.

    python scripts/p1_lab/hard_ataque_formato.py            # todos los casos (unos 2 minutos)
    python scripts/p1_lab/hard_ataque_formato.py --solo ts  # solo los casos cuyo nombre contiene "ts"

Episodio: las dos primeras semanas del test (24-30 de septiembre y 25-31 de octubre: 336 h con un salto
de mes en medio). Lo que se espera SIEMPRE: 0 excepciones, 0 acciones no finitas y, si la observación trae
una carga válida y la batería que dice el entorno, 0 infracciones.
"""
import argparse
import datetime as dt
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hard_ataque_comun as c  # noqa: E402
from battery.params import BatteryParams  # noqa: E402

NAN = float("nan")
STD = BatteryParams()            # la batería del modo estándar: 2.000 kWh y 500 kW
LISTS = ("preus_properes_24h", "co2_properes_24h")
CAP_KEYS = ("cap_max_kwh", "power_max_kw")


def lists(fn):
    def f(o, t):
        for k in LISTS:
            o[k] = fn(o[k])
        return o
    return f


def setk(key, value):
    def f(o, t):
        o[key] = value(o) if callable(value) else value
        return o
    return f


def delk(*keys):
    def f(o, t):
        for k in keys:
            o.pop(k, None)
        return o
    return f


def recent(fn):
    def f(o, t):
        o["noves_dades_5min"] = fn(o["noves_dades_5min"])
        return o
    return f


def pad24(fill):
    return lists(lambda v: list(v) + [fill] * (24 - len(v)))


def unequal(o, t):
    o["co2_properes_24h"] = o["co2_properes_24h"][:2]
    return o


def short_at_week_end(o, t):
    """Como si el entorno cortase la previsión al final de cada semana (no solo al final del test)."""
    left = c.WEEK - (t % c.WEEK)
    for k in LISTS:
        o[k] = o[k][:left]
    return o


def meteo(value):
    def f(d):
        for k in ("irradiancia_wm2", "temp_ambient_c", "temp_panel_c", "vent_ms"):
            d[k] = value
        return d
    return recent(f)


def meteo_out(d):
    return {k: d[k] for k in ("ultim_consum_kw", "ultima_solar_kw")}


def price_zero(o, t):
    if t % 5 == 0:
        o["preu_actual"] = 0.0
        o["preus_properes_24h"] = [0.0] + list(o["preus_properes_24h"][1:])
    if t % 7 == 0:
        o["preus_properes_24h"] = [-abs(v) for v in o["preus_properes_24h"]]
        o["preu_actual"] = o["preus_properes_24h"][0]
    return o


def co2_zero(o, t):
    if t % 4 == 0:
        o["co2_actual"] = 0.0
        o["co2_properes_24h"] = [0.0] * len(o["co2_properes_24h"])
    return o


# nombre -> (deformación, física del entorno, se espera 0 infracciones)
CASOS = {
    "base": (None, c.HARD_PARAMS, True),
    # --- listas de previsión
    "lista_2": (lists(lambda v: v[:2]), c.HARD_PARAMS, True),
    "lista_1": (lists(lambda v: v[:1]), c.HARD_PARAMS, True),
    "lista_0": (lists(lambda v: []), c.HARD_PARAMS, True),
    "lista_None": (lists(lambda v: None), c.HARD_PARAMS, True),
    "lista_ausente": (delk(*LISTS), c.HARD_PARAMS, True),
    "lista_numpy": (lists(lambda v: np.asarray(v)), c.HARD_PARAMS, True),
    "lista_series": (lists(lambda v: pd.Series(v)), c.HARD_PARAMS, True),
    "lista_tupla": (lists(tuple), c.HARD_PARAMS, True),
    "lista_str": (lists(lambda v: [str(x) for x in v]), c.HARD_PARAMS, True),
    "lista_24_con_NaN": (pad24(NAN), c.HARD_PARAMS, True),
    "lista_24_con_None": (pad24(None), c.HARD_PARAMS, True),
    "lista_24_con_ceros": (pad24(0.0), c.HARD_PARAMS, True),
    "listas_desiguales_3_y_2": (unequal, c.HARD_PARAMS, True),
    "lista_corta_al_final_de_cada_semana": (short_at_week_end, c.HARD_PARAMS, True),
    "lista_con_NaN_en_medio": (lists(lambda v: [v[0], NAN] + list(v[2:])), c.HARD_PARAMS, True),
    "precio_cero_y_negativo": (price_zero, c.HARD_PARAMS, True),
    "co2_cero": (co2_zero, c.HARD_PARAMS, True),
    "preu_actual_ausente": (delk("preu_actual"), c.HARD_PARAMS, True),
    "co2_actual_ausente": (delk("co2_actual"), c.HARD_PARAMS, True),
    "preu_actual_NaN": (setk("preu_actual", NAN), c.HARD_PARAMS, True),
    # --- fecha
    "ts_str": (setk("timestamp", lambda o: str(o["timestamp"])), c.HARD_PARAMS, True),
    "ts_iso_T": (setk("timestamp", lambda o: o["timestamp"].isoformat()), c.HARD_PARAMS, True),
    "ts_str_con_zona": (setk("timestamp", lambda o: o["timestamp"].isoformat() + "+02:00"), c.HARD_PARAMS, True),
    "ts_dia_mes_anyo": (setk("timestamp", lambda o: o["timestamp"].strftime("%d/%m/%Y %H:%M")), c.HARD_PARAMS, True),
    "ts_datetime": (setk("timestamp", lambda o: o["timestamp"].to_pydatetime()), c.HARD_PARAMS, True),
    "ts_datetime64": (setk("timestamp", lambda o: o["timestamp"].to_datetime64()), c.HARD_PARAMS, True),
    "ts_utc_con_zona": (setk("timestamp", lambda o: o["timestamp"].tz_localize("UTC")), c.HARD_PARAMS, True),
    "ts_epoch_s": (setk("timestamp", lambda o: int(o["timestamp"].timestamp())), c.HARD_PARAMS, True),
    "ts_None": (setk("timestamp", None), c.HARD_PARAMS, True),
    "ts_ausente": (delk("timestamp"), c.HARD_PARAMS, True),
    "ts_basura": (setk("timestamp", "no-es-una-fecha"), c.HARD_PARAMS, True),
    "ts_NaT": (setk("timestamp", pd.NaT), c.HARD_PARAMS, True),
    "ts_fecha_sin_hora": (setk("timestamp", lambda o: o["timestamp"].date()), c.HARD_PARAMS, True),
    "ts_y_hour_ausentes": (delk("timestamp", "hour", "day_of_week"), c.HARD_PARAMS, True),
    "hour_ausente": (delk("hour", "day_of_week"), c.HARD_PARAMS, True),
    "hour_str": (setk("hour", lambda o: str(o["hour"])), c.HARD_PARAMS, True),
    "hour_NaN": (setk("hour", NAN), c.HARD_PARAMS, True),
    # --- lectura de la hora anterior y meteo
    "meteo_ausente": (recent(meteo_out), c.HARD_PARAMS, True),
    "meteo_None": (meteo(None), c.HARD_PARAMS, True),
    "meteo_NaN": (meteo(NAN), c.HARD_PARAMS, True),
    "meteo_str": (meteo("n/d"), c.HARD_PARAMS, True),
    "lectura_ausente": (delk("noves_dades_5min"), c.HARD_PARAMS, True),
    "lectura_None": (setk("noves_dades_5min", None), c.HARD_PARAMS, True),
    "lectura_lista": (setk("noves_dades_5min", lambda o: [o["noves_dades_5min"]] * 12), c.HARD_PARAMS, True),
    "consumo_NaN": (recent(lambda d: dict(d, ultim_consum_kw=NAN)), c.HARD_PARAMS, True),
    "consumo_None": (recent(lambda d: dict(d, ultim_consum_kw=None)), c.HARD_PARAMS, True),
    "solar_NaN": (recent(lambda d: dict(d, ultima_solar_kw=NAN)), c.HARD_PARAMS, True),
    "solar_sin_x12": (recent(lambda d: dict(d, ultima_solar_kw=d["ultima_solar_kw"] / 12.0)), c.HARD_PARAMS, True),
    "consumo_y_solar_negativos": (recent(lambda d: dict(d, ultim_consum_kw=-abs(d["ultim_consum_kw"]),
                                                         ultima_solar_kw=-abs(d["ultima_solar_kw"]))), c.HARD_PARAMS, True),
    # --- batería
    "cap_ausente": (delk(*CAP_KEYS), c.HARD_PARAMS, True),
    "cap_str": (lambda o, t: dict(o, cap_max_kwh=str(o["cap_max_kwh"]), power_max_kw=str(o["power_max_kw"])), c.HARD_PARAMS, True),
    "cap_None": (lambda o, t: dict(o, cap_max_kwh=None, power_max_kw=None), c.HARD_PARAMS, True),
    "cap_NaN_y_0": (lambda o, t: dict(o, cap_max_kwh=NAN, power_max_kw=0.0), c.HARD_PARAMS, True),
    "solo_falta_power": (delk("power_max_kw"), c.HARD_PARAMS, True),
    "bateria_2000_500_avisada": (None, STD, True),
    "bateria_2000_500_SIN_avisar": (delk(*CAP_KEYS), STD, False),
    "bateria_2000_500_solo_cap": (delk("power_max_kw"), STD, False),
    # --- carga
    "soc_np_float": (setk("soc_kwh", lambda o: np.float64(o["soc_kwh"])), c.HARD_PARAMS, True),
    "soc_str": (setk("soc_kwh", lambda o: str(o["soc_kwh"])), c.HARD_PARAMS, True),
    "soc_redondeado_3_dec": (setk("soc_kwh", lambda o: round(o["soc_kwh"], 3)), c.HARD_PARAMS, True),
    "soc_redondeado_2_dec": (setk("soc_kwh", lambda o: round(o["soc_kwh"], 2)), c.HARD_PARAMS, True),
    "soc_redondeado_entero": (setk("soc_kwh", lambda o: float(round(o["soc_kwh"]))), c.HARD_PARAMS, True),
    "soc_NaN": (setk("soc_kwh", NAN), c.HARD_PARAMS, False),
    "soc_None": (setk("soc_kwh", None), c.HARD_PARAMS, False),
    "soc_ausente": (delk("soc_kwh"), c.HARD_PARAMS, False),
    "soc_negativo": (setk("soc_kwh", -50.0), c.HARD_PARAMS, False),
    "soc_mayor_que_cap": (setk("soc_kwh", 7000.0), c.HARD_PARAMS, False),
    "soc_en_tanto_por_uno": (setk("soc_kwh", lambda o: o["soc_pct"]), c.HARD_PARAMS, False),
}
SEGUROS = [k for k, v in CASOS.items() if v[1] is c.HARD_PARAMS and v[2] and k != "base"
           and not k.startswith("soc_redondeado")]


def fuzz(seed: int):
    """Cada hora, una deformación al azar de las que no tocan ni la carga ni la batería."""
    rng = np.random.default_rng(seed)
    picks = rng.choice(len(SEGUROS), size=5000)

    def f(o, t):
        fn = CASOS[SEGUROS[int(picks[t])]][0]
        return fn(o, t) if fn is not None else o
    return f


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--solo", default="", help="solo los casos cuyo nombre contiene este texto")
    args = ap.parse_args()
    full, origen = c.episodio_test("copia")
    pm, ps = c.priors(origen)
    df = full.iloc[:2 * c.WEEK].reset_index(drop=True)
    casos = dict(CASOS)
    for s in (1, 2, 3):
        casos[f"fuzz_semilla_{s}"] = (fuzz(s), c.HARD_PARAMS, True)
    rows, base = [], {}
    for nombre, (fn, p, limpio) in casos.items():
        if args.solo and args.solo not in nombre and nombre != "base":
            continue
        r = c.simular(c.agente(pm, ps), df, fn=fn, p=p)
        if nombre == "base":
            base = r
        mal = []
        if r["excepciones"]:
            mal.append("EXCEPCION")
        if r["no_finitas"]:
            mal.append("NO FINITA")
        if r["infr"] and limpio:
            mal.append("INFRACCION")
        if p is c.HARD_PARAMS and base and r["score"] < base["score"] - 1.0:
            mal.append("pierde score")
        rows.append({"caso": nombre, "score": r["score"], "dif": r["score"] - base["score"] if p is c.HARD_PARAMS else NAN,
                     "infr": r["infr"], "excep": r["excepciones"], "no_fin": r["no_finitas"],
                     "pct_cero": r["pct_cero"], "vert_desc": r["vert_descarga"], "ms_max": r["ms_max"],
                     "aviso": ", ".join(mal), "error": r["error"]})
    out = pd.DataFrame(rows)
    pd.set_option("display.width", 250, "display.max_rows", 200, "display.max_colwidth", 60)
    print(f"episodio: {len(df)} h (dos semanas del test, con salto de mes). Score base {base['score']:.3f}")
    print(out.round(2).to_string(index=False))
    out_dir = c.REPO / "results" / "p1_hard"
    out_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_dir / ("ataque_formato.csv" if not args.solo else f"ataque_formato_{args.solo}.csv"), index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
