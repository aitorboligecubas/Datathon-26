"""Prototipo de los arreglos que proponen los ataques al agente del HARD MODE. NO se empaqueta.

Owner: P1. No toca src/: `Blindado` hereda de battery.hard.HardPolicy y añade, delante, una limpieza de la
observación. Sirve para MEDIR cada arreglo; el arreglo de verdad hay que escribirlo en src/battery/hard.py.

    python scripts/p1_lab/hard_ataque_arreglos.py

Arreglos (cada uno, con su motivo):
  A. Lectura de consumo vacía desde el primer paso: es un problema de formato (la clave no llega), no una
     semana sin datos. No se bloquea: se planifica con el perfil.
  B. Margen de 1 kW al recortar la acción (ahora 0,0001 kW): aguanta una carga redondeada hasta al entero.
     1 kW durante 1 h es 1 kWh de 6.000: no cuesta nada.
  C. LAST_MONTHS solo con agosto de 2026: el test tiene 12 semanas y la de julio no es la última.
  D. Sin fecha (None, ausente, ilegible, de 1970): reloj propio. La hora siguiente a la última conocida y, si
     nunca hubo fecha, el 24/09/2025 a las 00:00 (primera hora del test, docs/envios.md). Si la fecha no trae
     hora pero `hour` sí, se usa `hour`.
  E. Listas de previsión con relleno: se quita la COLA de valores vacíos o no finitos y, si llegan más de 3
     valores, también la cola de ceros (el anuncio dice que solo llegan 3: lo demás es relleno). Así 24 valores
     con 21 de relleno vuelven a ser 3. Un hueco en medio se deja (el adaptador ya lo rellena).
  H. "Se acaban los datos" = llega una lista MÁS CORTA que la más larga vista hasta ahora (no "menos de 3").
     Si el entorno diese siempre 2 valores, o 1, el agente actual cree en cada paso que el test acaba ya.
  I. ¿La batería sigue de una semana a otra o cada semana se simula por separado? El agente lo ve solo: al
     empezar la SEGUNDA semana, si la carga observada es el 50 % justo y no la que él dejó, el entorno ha
     reiniciado la batería. Desde ahí cierra cada semana vacía (lo que hace EMPTY_EVERY_WEEK = True). Si no,
     sigue como ahora. No hace falta gastar envíos ni leer el ranking público para saberlo.
  F. `preu_actual` / `co2_actual` ausentes: el primer valor de la lista. `hour` / `day_of_week` ilegibles: los
     de la fecha.
  G. Batería: si falta `cap_max_kwh`, capacidad = soc_kwh / soc_pct; si falta `power_max_kw`, capacidad / 4
     (la proporción de las dos baterías del reto: 2.000/500 y 6.000/1.500).
"""
import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hard_ataque_comun as c  # noqa: E402
import battery.hard as hard  # noqa: E402
from battery.adapter import _to_float, _to_timestamp  # noqa: E402
from battery.safety import feasible_range, soc_after  # noqa: E402

MARGIN_KW = 1.0
TEST_START = pd.Timestamp("2025-09-24 00:00")
ONLY_LAST = ((2026, 8),)


def next_test_hour(ts):
    nxt = ts + hard.ONE_HOUR
    if nxt.month != ts.month:
        nxt = nxt + hard.ONE_HOUR * (24 * (nxt.days_in_month - 7))
    return nxt


def clean_list(v):
    try:
        arr = [_to_float(x) for x in list(v)]
    except Exception:
        return None
    k = len(arr)
    while k > 1 and not math.isfinite(arr[k - 1]):                      # cola vacía (None, NaN): fuera
        k -= 1
    while k > hard.KNOWN_HOURS and not arr[k - 1] > 0:                  # más de 3 valores y la cola a 0: relleno
        k -= 1
    return arr[:k]


class Blindado(hard.HardPolicy):
    clock = None            # fecha que se espera en la próxima observación
    seen_reading = False    # ha llegado alguna lectura de consumo válida
    cap_guess = None
    max_known = 0           # la lista de previsión más larga vista hasta ahora
    n_blocks = 0            # semanas del test empezadas
    expected_soc = None     # carga que debería verse en la próxima observación
    empty_weeks = False     # el entorno reinicia la batería cada semana: se cierra cada una vacía

    def plan_action(self, obs) -> float:                                                                     # H
        self.max_known = max(self.max_known, len(obs.price))
        keep = hard.KNOWN_HOURS
        hard.KNOWN_HOURS = min(keep, self.max_known)
        try:
            return super().plan_action(obs)
        finally:
            hard.KNOWN_HOURS = keep

    def clean(self, raw) -> dict:
        o = dict(raw)
        for now_key, list_key in (("preu_actual", "preus_properes_24h"), ("co2_actual", "co2_properes_24h")):   # E y F
            arr = clean_list(o.get(list_key)) if o.get(list_key) is not None else None
            if arr:
                o[list_key] = arr
                if not math.isfinite(_to_float(o.get(now_key))) and math.isfinite(arr[0]):
                    o[now_key] = arr[0]
            elif now_key not in o:
                o[now_key] = float("nan")
        ts = _to_timestamp(o.get("timestamp"))                                                               # D
        hour = _to_float(o.get("hour"))
        if ts is not None and ts.year < 2000:
            ts = None
        if ts is None:
            ts = self.clock if self.clock is not None else TEST_START
        elif math.isfinite(hour) and int(hour) % 24 != ts.hour and ts.hour == 0 and ts.minute == 0:
            ts = ts + hard.ONE_HOUR * (int(hour) % 24)
        o["timestamp"] = ts
        self.clock = next_test_hour(ts)
        if not math.isfinite(hour):                                                                          # F
            o["hour"] = ts.hour
        if not math.isfinite(_to_float(o.get("day_of_week"))):
            o["day_of_week"] = ts.dayofweek
        cap, power = _to_float(o.get("cap_max_kwh")), _to_float(o.get("power_max_kw"))                       # G
        if not (math.isfinite(cap) and cap > 0):
            soc, pct = _to_float(o.get("soc_kwh")), _to_float(o.get("soc_pct"))
            if self.cap_guess is None and math.isfinite(soc) and math.isfinite(pct) and pct > 0.01 and soc > 0:
                self.cap_guess = float(round(soc / pct))
            cap = self.cap_guess if self.cap_guess is not None else float("nan")
        if math.isfinite(cap) and cap > 0:
            if not (math.isfinite(power) and power > 0):
                power = cap / 4.0
            o["cap_max_kwh"], o["power_max_kw"] = cap, power
        return o

    def track_block(self, obs) -> bool:                                                                      # A
        new_block = super().track_block(obs)
        if new_block:                                                                                        # I
            self.n_blocks += 1
            if self.n_blocks == 2 and self.expected_soc is not None and math.isfinite(obs.soc_kwh):
                self.empty_weeks = (abs(obs.soc_kwh - self.expected_soc) > 1.0
                                    and abs(obs.soc_kwh - 0.5 * self.p.capacity_kwh) < 1.0)
        if math.isfinite(obs.load_prev_kw):
            self.seen_reading = True
        if self.no_reading and not self.seen_reading:
            self.no_data_block, self.no_reading = False, False
        return new_block

    def horizon_times(self, obs) -> list:                                                                    # C
        keep, keep_empty = hard.LAST_MONTHS, hard.EMPTY_EVERY_WEEK
        hard.LAST_MONTHS, hard.EMPTY_EVERY_WEEK = ONLY_LAST, bool(keep_empty or self.empty_weeks)
        try:
            return super().horizon_times(obs)
        finally:
            hard.LAST_MONTHS, hard.EMPTY_EVERY_WEEK = keep, keep_empty

    def act_obs(self, obs) -> float:                                                                         # B
        a = super().act_obs(obs)
        lo, hi = feasible_range(obs.soc_kwh, self.p)
        if not (math.isfinite(lo) and math.isfinite(hi)):
            return 0.0
        a = min(max(a, min(0.0, lo + MARGIN_KW)), max(0.0, hi - MARGIN_KW))
        self.expected_soc = soc_after(obs.soc_kwh, a, self.p)
        return a

    def act(self, raw_obs) -> float:
        try:
            raw_obs = self.clean(raw_obs)
        except Exception:
            pass
        return super().act(raw_obs)


def blindado(pm, ps):
    a = c.agente(pm, ps)
    a.policy.__class__ = Blindado
    return a


def main() -> int:
    import hard_ataque_formato as f
    solo = sys.argv[1] if len(sys.argv) > 1 else ""
    full, origen = c.episodio_test("copia")
    pm, ps = c.priors(origen)
    dos = full.iloc[:2 * c.WEEK].reset_index(drop=True)
    nan_load = f.CASOS["consumo_NaN"][0]
    casos = [(k, dos, f.CASOS[k][0], f.CASOS[k][1]) for k in (
        "base", "ts_None", "ts_basura", "ts_epoch_s", "ts_fecha_sin_hora", "ts_y_hour_ausentes", "hour_NaN",
        "lista_24_con_NaN", "lista_24_con_None", "lista_24_con_ceros", "lista_con_NaN_en_medio",
        "preu_actual_ausente", "co2_actual_ausente", "bateria_2000_500_avisada", "bateria_2000_500_SIN_avisar",
        "bateria_2000_500_solo_cap", "soc_redondeado_2_dec", "soc_redondeado_entero", "consumo_NaN", "lectura_ausente",
        "lista_2", "lista_1", "lista_0", "listas_desiguales_3_y_2", "lista_corta_al_final_de_cada_semana",
        "precio_cero_y_negativo", "co2_cero", "cap_ausente", "meteo_ausente", "solar_NaN")]
    casos += [("TEST ENTERO: base", full, None, c.HARD_PARAMS),
              ("TEST ENTERO: lectura de consumo vacía siempre", full, nan_load, c.HARD_PARAMS),
              ("TEST ENTERO: carga redondeada a 2 decimales", full, f.CASOS["soc_redondeado_2_dec"][0], c.HARD_PARAMS),
              ("TEST ENTERO: fuzz", full, f.fuzz(11), c.HARD_PARAMS)]
    rows = []
    for nombre, df, fn, p in casos:
        if solo and solo not in nombre:
            continue
        r0 = c.simular(c.agente(pm, ps), df, fn=fn, p=p)
        r1 = c.simular(blindado(pm, ps), df, fn=fn, p=p)
        rows.append({"caso": nombre, "score_actual": r0["score"], "score_blindado": r1["score"],
                     "gana": r1["score"] - r0["score"], "infr_actual": r0["infr"], "infr_blindado": r1["infr"],
                     "excep_blindado": r1["excepciones"], "ms_medio_blindado": r1["ms_medio"]})
    out = pd.DataFrame(rows)
    pd.set_option("display.width", 250, "display.max_colwidth", 60)
    print(out.round(3).to_string(index=False))
    out_dir = c.REPO / "results" / "p1_hard"
    out_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_dir / ("ataque_arreglos.csv" if not solo else "ataque_arreglos_parcial.csv"), index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
