"""Candidato del encargo "arranque" (HARD MODE): cada semana del test arranca con memoria del train.

Owner: P1 (laboratorio). Uso con el banco:

    python scripts/p1_hard.py --split dev --only "agente actual,CANDIDATO" --agent scripts/p1_lab/hard_arranque_cand.py:make

Qué cambia frente al agente actual (v8). Una sola cosa: la SEMILLA de consumo y solar.
El test son los últimos 7 días de cada mes y el train llega justo hasta la hora anterior. Hoy, en la primera
hora de cada semana el agente tira la lectura "de la hora anterior" (es de hace un mes) y el previsor de
consumo y solar (battery.hard_solar.SolarCand) arranca sin historia. Pero las horas anteriores a cada semana
SÍ se conocen: son las últimas del train. Aquí se guardan las últimas 48 lecturas horarias de cada tramo
seguido del train y, al empezar una semana, se le "cuentan" al previsor una a una por el mismo camino por el
que aprende de las lecturas reales (SolarCand.learn). No hay ninguna receta nueva de previsión: el previsor
queda exactamente como si llevara dos días funcionando. Con eso, desde la primera hora tiene:
  - el cociente consumo/perfil de la hora anterior (r1) y los de ayer (ry, ry1): regresión de 3 pistas;
  - la lectura de las 23 h, que con el contador congelado de 23 a 5 h es el consumo de las 6 primeras horas;
  - la claridad media de ayer (pista de la solar antes de amanecer).
Si no hay semilla para una semana (noviembre no tiene contador en el train) o algo falla, arranca como ahora.

El horizonte del plan y el valor final (segunda parte del encargo) NO cambian: ninguna variante gana en las
dos ventanas de diseño. Las medidas están en results/p1_hard/arranque_notas.md y el laboratorio en
scripts/p1_lab/hard_arranque_lab.py.

La parte de "inferencia" solo usa numpy, pandas, math y typing (se puede empaquetar). La de "ajuste" es del
laboratorio: iría a scripts/p1_hard.py (fit_solar) y a models/hard_solar.json (clave "seed").
"""
import math
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
for _extra in (str(REPO / "src"), str(REPO / "scripts")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

from battery.hard_market import hour_index  # noqa: E402
from battery.hard_solar import HOUR_NS, PV_FACTOR, SolarCand  # noqa: E402

SEED_HOURS = 48             # lecturas horarias del final de cada tramo del train que se guardan (2 días: el
                            # previsor mira 25 horas atrás; el resto es margen por si falta alguna)
SEED_STEP = pd.Timedelta(hours=1)
NO_MARKET = np.empty(0)     # las lecturas de la semilla no traen precio ni CO2


# ------------------------------------------------------------------------------------ inferencia
def seed_value(v) -> float:
    """Valor de la semilla como número (None o basura -> NaN)."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return float("nan")
    return v if math.isfinite(v) else float("nan")


class SeededSolar(SolarCand):
    """SolarCand que arranca cada semana con las últimas lecturas del train.

    seed = [{"start": número de hora de la primera lectura (battery.hard_market.hour_index),
             "load": [kW, ...], "pv": [kW ya x12 o None, ...]}, ...]      # una lectura por hora, seguidas
    Solo se usa el tramo que acaba JUSTO en la hora anterior a la primera de la semana.
    """
    seed = ()
    n_seeded = 0                # semanas arrancadas con semilla
    seeded_at = ()              # fechas en las que se usó (para comprobar)

    def update(self, obs, weather: Optional[dict] = None) -> None:
        try:
            obs = self.warm_start(obs)
        except Exception:
            try:
                SolarCand.new_block(self)       # a medias no vale: se arranca sin memoria, como el agente actual
            except Exception:
                pass
        SolarCand.update(self, obs, weather)

    def seed_segment(self, now: int):
        """Tramo de la semilla cuya última lectura es la de la hora `now` - 1 (None si no hay)."""
        for seg in self.seed:
            try:
                if int(seg["start"]) + len(seg["load"]) == now and len(seg["load"]) > 0:
                    return seg
            except Exception:
                continue
        return None

    def warm_start(self, obs):
        """Si esta hora empieza una semana y el train tiene las horas de justo antes, se repasan una a una
        y se devuelve la observación con la lectura de la hora anterior (la última del train)."""
        ts = obs.timestamp
        if not self.seed or not self.ok or ts is None:
            return obs
        if self.last_value is not None and ts.value - self.last_value == HOUR_NS:
            return obs                          # hora seguida de la anterior: no empieza ninguna semana
        seg = self.seed_segment(hour_index(ts))
        if seg is None:
            return obs
        load = [seed_value(v) for v in seg["load"]]
        pv = [seed_value(v) for v in (seg.get("pv") or [])]
        n = len(load)
        pv = (pv + [float("nan")] * n)[:n]
        SolarCand.new_block(self)
        for j in range(n - 1):                  # la lectura j es de la hora ts - (n - j); se ve una hora después
            t = ts - SEED_STEP * (n - 1 - j)
            self.learn(obs._replace(hour=t.hour, weekday=t.dayofweek, timestamp=t, load_prev_kw=load[j],
                                    pv_prev_kw=pv[j], price=NO_MARKET, co2=NO_MARKET))
        self.n_seeded += 1
        self.seeded_at = tuple(self.seeded_at) + (ts,)
        return obs._replace(load_prev_kw=load[-1], pv_prev_kw=pv[-1])


# ------------------------------------------------------------------------------------ ajuste (laboratorio)
READINGS_CACHE = {}


def hourly_readings() -> pd.DataFrame:
    """Consumo y solar (ya x12) del train, una fila por hora del calendario (NaN donde no hay dato).

    El consumo sale del contador con la receta de battery.data.build_hourly (variante oficial): -potencia,
    recortada a 0..5000, media horaria. La solar, de la tabla horaria del banco. No se exige que estén los
    dos: del 17 al 24 de agosto hay contador pero no inversores, y esas lecturas de consumo son la semilla
    de la última semana del test."""
    if "d" not in READINGS_CACHE:
        import p1_hard as bench
        from battery.data import P_COL, TRAIN_DIR, ensure_official
        ensure_official()
        cont = pd.read_csv(TRAIN_DIR / "contador.csv", parse_dates=["Fecha"], usecols=["Fecha", P_COL]).set_index("Fecha")
        load = (-cont[P_COL]).clip(lower=0, upper=5000).resample("1h").mean().dropna()
        table = bench.hard_table().set_index("timestamp")
        load = load[load.index < "2026-09-01"]
        idx = pd.date_range(min(load.index.min(), table.index.min()).normalize(), max(load.index.max(), table.index.max()), freq="h")
        READINGS_CACHE["d"] = pd.DataFrame({"load": load.reindex(idx), "pv": table.pv_kw.reindex(idx),
                                            "table_load": table.load_kw.reindex(idx)})
    return READINGS_CACHE["d"].copy()


def seed_segments(exclude=None, hours: int = SEED_HOURS) -> list:
    """Las últimas `hours` lecturas de cada tramo seguido de consumo del train, sin las horas de `exclude`.
    Cada tramo acaba donde acaban los datos: justo antes de una semana del test o de un bloque excluido."""
    d = hourly_readings()
    if exclude:
        d.loc[d.index.isin(list(exclude))] = np.nan
    load, pv = d["load"].to_numpy(float), d["pv"].to_numpy(float)
    ok = np.isfinite(load)
    ends = np.flatnonzero(ok & ~np.r_[ok[1:], False])
    segs = []
    for e in ends:
        s = e
        while s > 0 and ok[s - 1] and e - s + 1 < hours:
            s -= 1
        segs.append({"start": int(hour_index(d.index[s])),
                     "load": [float(v) for v in load[s:e + 1]],
                     "pv": [float(v) if math.isfinite(v) else None for v in pv[s:e + 1]]})
    return segs


def to_prior(exclude=None) -> dict:
    """Lo que hay que añadir a models/hard_solar.json: {"seed": [...]} (todo números, listas y None)."""
    return {"seed": seed_segments(exclude)}


def make(prior: dict, solar_prior: dict, exclude: set, seed: bool = True, seed_hours: int = SEED_HOURS, segments=None):
    """Fábrica para el banco. El agente actual con las mismas tablas y, si `seed`, el previsor de consumo y
    solar con la semilla (construida SIN las horas de `exclude`). `segments`: semilla ya hecha (laboratorio)."""
    import p1_hard as bench
    agent = bench.hard_agent(prior, solar_prior)
    net = agent.policy.netload
    if seed and isinstance(net, SolarCand):
        try:
            segs = segments if segments is not None else seed_segments(exclude, seed_hours)
            net.__class__ = SeededSolar         # mismas tablas y estado, con el arranque del candidato
            net.seed = segs
        except Exception:
            pass
    return agent
