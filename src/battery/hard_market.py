"""Previsión del precio y del CO2 para el HARD MODE (solo se conocen 3 horas).

Owner: P1 (optimizador), con P2 (datos). Se empaqueta en el agent.py del modo difícil.

CONTRATO (no cambiar sin avisar):
    m = MarketForecaster(prior)                 # prior: dict de models/hard_market.json, o None
    price, co2 = m.forecast(obs, times, weather)
        obs.price / obs.co2: lo que da el entorno (la hora actual y las siguientes, 3 valores)
        times: lista de pd.Timestamp, una por hora del plan ([0] = hora actual)
        weather: dict con la meteo de la hora anterior (o None)
        -> dos np.ndarray de la misma longitud que `times`, >= 0; las horas conocidas se respetan
Se llama una vez por hora y tiene que tardar menos de ~2 ms. Solo numpy, pandas y math.
"""
import math
from typing import Optional

import numpy as np
import pandas as pd

from .obs import Obs

KNOWN_HOURS = 3             # horas de precio y CO2 que da el entorno (la actual y las dos siguientes)
MARKET_FILE = "hard_market.json"
LEVEL_PRIOR_H = 6.0         # horas "ficticias" a nivel 1 con las que se estima el nivel al empezar una semana
LEVEL_WINDOW_H = 48         # horas recientes con las que se estima el nivel del precio y del CO2
YESTERDAY_WEIGHT = 0.5      # cuánto pesa "ayer a esta hora" frente al nivel reciente
REG_LEADS = 21              # antelaciones con regresión propia: de 3 a 23 horas
# Festivos nacionales del periodo del reto (sep-2025 a ago-2026). Mueven la demanda de toda la red y, con
# ella, el precio y el CO2: en el perfil cuentan como domingo.
NATIONAL_HOLIDAYS = ((2025, 10, 12), (2025, 11, 1), (2025, 12, 6), (2025, 12, 8), (2025, 12, 25), (2026, 1, 1),
                     (2026, 1, 6), (2026, 4, 3), (2026, 5, 1), (2026, 8, 15))


def market_day_type(ts) -> int:
    """0 = laborable, 1 = sábado, 2 = domingo o festivo nacional."""
    if (ts.year, ts.month, ts.day) in NATIONAL_HOLIDAYS:
        return 2
    wd = ts.dayofweek
    return 0 if wd < 5 else (1 if wd == 5 else 2)


MARKET_MONTH_DAYS = 30.4     # días medios de un mes, para interpolar el perfil entre meses


def month_blend(month: int, day: float, centers) -> tuple:
    """Mes vecino (índice 0-11) y peso con el que entra su perfil, según lo lejos que cae el día del centro de los
    datos con los que se ajustó el perfil del mes. El test son los días 25-31 y el train los días 1-24: el perfil
    de la semana del test está a medio camino del perfil del mes siguiente."""
    c = centers[month - 1]
    if day >= c:
        other = month % 12
        w = (day - c) / (MARKET_MONTH_DAYS - c + centers[other])
    else:
        other = (month - 2) % 12
        w = (c - day) / (c + MARKET_MONTH_DAYS - centers[other])
    return other, min(max(w, 0.0), 1.0)


def hour_index(ts) -> int:
    """Número de hora absoluto (para medir cuántas horas separan dos fechas sin restar fechas)."""
    return ts.toordinal() * 24 + ts.hour


class MarketForecaster:
    """Previsión del precio y del CO2 más allá de las 3 horas que da el entorno.

    1. Perfil por mes, tipo de día (laborable, sábado, domingo) y hora, aprendido en el train.
    2. Lo que importa es la DESVIACIÓN frente a ese perfil, z = log(real / perfil). Para cada antelación
       (de 3 a 23 horas) una regresión lineal ajustada en el train predice la desviación futura con las
       tres horas conocidas, la media de las últimas 6 y 24 horas y la de ayer a la misma hora.
    3. Al empezar una semana (sin historia) se usa una regresión que solo mira las tres horas conocidas.
    Si el fichero no trae regresiones, se usa la receta sencilla: nivel reciente y "ayer a esta hora".
    """

    def __init__(self, prior: Optional[dict] = None, yesterday_weight: float = YESTERDAY_WEIGHT):
        self.prof = {}
        self.reg = {}
        if prior:
            for name in ("price", "co2"):
                self.prof[name] = np.asarray(prior[name], dtype=float)      # [mes 0-11][tipo 0-2][hora 0-23]
            try:
                for name in ("price", "co2"):
                    full = np.asarray(prior["reg"][name]["full"], dtype=float)    # [21 antelaciones][7 coeficientes]
                    cold = np.asarray(prior["reg"][name]["cold"], dtype=float)    # [21][4]
                    if full.shape == (REG_LEADS, 7) and cold.shape == (REG_LEADS, 4):
                        self.reg[name] = (full, cold)
            except Exception:
                self.reg = {}
        self.centers = None        # día medio de los datos de cada mes: con él, el perfil se interpola entre meses
        try:
            centers = [float(v) for v in prior["day_center"]]
            if len(centers) == 12 and all(1.0 <= v <= 31.0 for v in centers):
                self.centers = centers
        except Exception:
            self.centers = None
        self.seen = {"price": {}, "co2": {}}       # número de hora -> (valor real, valor del perfil)
        self.yesterday_weight = yesterday_weight

    def profile(self, name: str, ts) -> float:
        p = self.prof.get(name)
        if p is None:
            return float("nan")
        typ = market_day_type(ts)
        value = float(p[ts.month - 1][typ][ts.hour])
        if self.centers is not None:
            other, w = month_blend(ts.month, ts.day, self.centers)
            if w > 0.0:
                value = (1.0 - w) * value + w * float(p[other][typ][ts.hour])
        return value

    def remember(self, obs: Obs, times: list) -> None:
        """Guarda los valores reales que se acaban de conocer (la hora actual y las siguientes)."""
        now = hour_index(times[0])
        for name, arr in (("price", obs.price), ("co2", obs.co2)):
            store = self.seen[name]
            for k in range(min(len(arr), len(times))):
                store[hour_index(times[k])] = (float(arr[k]), self.profile(name, times[k]))
            if len(store) > 400:
                for key in [key for key in store if key < now - 200]:
                    del store[key]

    def deviation(self, name: str, key: int) -> float:
        """z = log(real / perfil) de una hora ya conocida (NaN si no se conoce)."""
        got = self.seen[name].get(key)
        if got is None or not (got[0] > 0 and got[1] > 0):
            return float("nan")
        return math.log(got[0] / got[1])

    def level(self, name: str, now: int) -> float:
        """Nivel reciente frente al perfil: mediana de real/perfil en las últimas horas, tirando a 1
        cuando hay pocas (al empezar una semana solo se conocen 3)."""
        ratios = [v / b for key, (v, b) in self.seen[name].items()
                  if now - LEVEL_WINDOW_H <= key <= now + KNOWN_HOURS and b > 0 and math.isfinite(v) and math.isfinite(b)]
        if not ratios:
            return 1.0
        n = float(len(ratios))
        return float((n * float(np.median(ratios)) + LEVEL_PRIOR_H) / (n + LEVEL_PRIOR_H))

    def regression(self, name: str, now: int, times: list, n_known: int):
        """Desviaciones previstas para las horas no conocidas (None si no se puede usar la regresión)."""
        if name not in self.reg or n_known < KNOWN_HOURS:
            return None
        full, cold = self.reg[name]
        z = [self.deviation(name, now + j) for j in range(KNOWN_HOURS)]
        if not all(math.isfinite(v) for v in z):
            return None
        last24 = [v for v in (self.deviation(name, now - j) for j in range(24)) if math.isfinite(v)]
        last6 = [v for v in (self.deviation(name, now - j) for j in range(6)) if math.isfinite(v)]
        warm = len(last24) >= 12 and len(last6) >= 3
        zm24 = sum(last24) / len(last24) if last24 else 0.0
        zm6 = sum(last6) / len(last6) if last6 else 0.0
        out = {}
        month = times[0].month
        for k in range(n_known, len(times)):
            if times[k].month != month:
                out[k] = 0.0                       # otra semana del test (otro mes): solo el perfil
                continue
            i = min(k, REG_LEADS + KNOWN_HOURS - 1) - KNOWN_HOURS
            zy = self.deviation(name, now + k - 24) if warm else float("nan")
            if warm and math.isfinite(zy):
                c = full[i]
                zhat = c[0] * z[0] + c[1] * z[1] + c[2] * z[2] + c[3] * zm24 + c[4] * zm6 + c[5] * zy + c[6]
            else:
                c = cold[i]
                zhat = c[0] * z[0] + c[1] * z[1] + c[2] * z[2] + c[3]
            out[k] = min(max(zhat, -2.0), 2.0)
        return out

    def forecast(self, obs: Obs, times: list, weather: Optional[dict] = None) -> tuple:
        """Precio y CO2 para cada fecha de `times` ([0] = hora actual). Lo conocido se respeta."""
        self.remember(obs, times)
        now = hour_index(times[0])
        out = []
        for name, arr in (("price", obs.price), ("co2", obs.co2)):
            zhat = self.regression(name, now, times, len(arr))
            lvl = self.level(name, now) if zhat is None else 1.0
            store = self.seen[name]
            x = np.empty(len(times))
            for k, t in enumerate(times):
                if k < len(arr):
                    x[k] = arr[k]
                    continue
                base = self.profile(name, t)
                if not (base > 0 and math.isfinite(base)):
                    x[k] = arr[-1]                       # sin perfil: se repite lo último conocido
                    continue
                if zhat is not None:
                    x[k] = base * math.exp(zhat[k])
                    continue
                ratio = lvl
                prev = store.get(hour_index(t) - 24)     # ayer a esta hora (solo si es de esta misma semana)
                if prev is not None and prev[1] > 0 and now - hour_index(t) + 24 <= 30:
                    ratio = self.yesterday_weight * prev[0] / prev[1] + (1.0 - self.yesterday_weight) * lvl
                x[k] = base * ratio
            out.append(np.maximum(x, 0.0))
        return out[0], out[1]


# ======================================================================================================
# Previsor con memoria del train y más pistas (entrega del encargo "mercado", sábado 14/11).
# Validación reservada: 20,55 -> 20,66. Notas: results/p1_hard/mercado_notas.md
# ======================================================================================================
NAMES = ("price", "co2")
LEADS = 21                  # antelaciones con regresión: de 3 a 23 horas
STORE_PAST_H = 24 * 40      # horas hacia atrás que caben en la memoria densa
STORE_LEN_H = 24 * 460      # un año de test y margen
Z_CLIP = 2.0                # la desviación prevista se limita a e^-2..e^2


def log_ratio(value: float, base: float) -> float:
    """z = log(real / perfil). NaN si falta alguno de los dos."""
    if not (math.isfinite(value) and math.isfinite(base) and base > 0):
        return float("nan")
    return min(max(math.log(max(value, 1e-6) / max(base, 1e-6)), -Z_CLIP), Z_CLIP)


def window_mean(z: np.ndarray, lo: int, hi: int, min_count: int) -> float:
    """Media de z[lo:hi] sin contar los huecos (NaN si hay menos de `min_count` valores)."""
    w = z[max(lo, 0):max(hi, 0)]
    ok = np.isfinite(w)
    n = int(ok.sum())
    return float(w[ok].sum() / n) if n >= min_count and n > 0 else float("nan")


class MarketCand(MarketForecaster):
    """Previsión de precio y CO2 con memoria del train y una regresión por antelación con más pistas.

    prior["cand"] = {"feats": [nombres de las F pistas],
                     "full": {"price": [21][F+1], "co2": [21][F+1]},      # o [21][24][F+1], por hora objetivo
                     "seed": [{"start": número de hora, "price": [...], "co2": [...]}, ...]}
    El resto de `prior` es el de siempre (perfiles y "reg"). Si falta algo o algo falla, decide como el
    agente actual (la clase madre).
    """

    def __init__(self, prior: Optional[dict] = None, **kwargs):
        super().__init__(prior, **kwargs)
        self.cand_ok = False
        self.feats, self.full, self.seed = (), {}, []
        try:
            c = prior["cand"]
            self.feats = tuple(c["feats"])
            for name in NAMES:
                full = np.asarray(c["full"][name], dtype=float)
                if full.ndim == 2:                      # una regresión común por antelación: vale para las 24 horas
                    full = np.repeat(full[:, None, :], 24, axis=1)
                if full.shape != (LEADS, 24, len(self.feats) + 1) or not np.isfinite(full).all():
                    raise ValueError("tablas con otra forma o con huecos")
                self.full[name] = full
            self.seed = list(c.get("seed") or [])
            self.cand_ok = bool(self.prof) and all(name in self.reg for name in NAMES)
        except Exception:
            self.cand_ok = False
        self.h0 = None                    # número de hora de la posición 0 de la memoria densa
        self.z = {}                       # nombre -> desviaciones por hora (NaN = no conocida)

    # --- memoria densa: una posición por hora, con lo del train (semilla) y lo que se va viendo
    def profile_at(self, name: str, key: int) -> float:
        """Perfil de la hora con número `key` (día ordinal * 24 + hora)."""
        day, hour = divmod(key, 24)
        return self.profile(name, pd.Timestamp.fromordinal(int(day)).replace(hour=int(hour)))

    def rebase(self, now: int) -> None:
        """Crea la memoria alrededor de `now` y vuelca en ella la semilla y lo visto hasta ahora."""
        self.h0 = now - STORE_PAST_H
        self.z = {name: np.full(STORE_LEN_H, np.nan) for name in NAMES}
        for seg in self.seed:
            try:
                start = int(seg["start"])
                for name in NAMES:
                    vals = seg[name]
                    for j in range(len(vals)):
                        pos = start + j - self.h0
                        if 0 <= pos < STORE_LEN_H and vals[j] is not None:
                            self.z[name][pos] = log_ratio(float(vals[j]), self.profile_at(name, start + j))
            except Exception:
                continue
        for name in NAMES:               # lo ya visto en este episodio manda sobre la semilla
            for key, (v, b) in self.seen[name].items():
                pos = key - self.h0
                if 0 <= pos < STORE_LEN_H:
                    self.z[name][pos] = log_ratio(v, b)

    def scalars(self, name: str, i: int, hour_now: int) -> dict:
        """Pistas que no dependen de la antelación. `i` = posición de la hora actual en la memoria."""
        z = self.z[name]
        start = i + 2 - (hour_now + 2) % 24         # primera hora del día de la última hora conocida
        return {"0": float(z[i]), "1": float(z[i + 1]), "2": float(z[i + 2]),
                "m24": window_mean(z, i - 23, i + 1, 12), "m6": window_mean(z, i - 5, i + 1, 3),
                "yL": float(z[i - 22]), "d": window_mean(z, start, i + 3, 1),
                "yd": window_mean(z, start - 24, start, 12)}

    def predict(self, name: str, other: str, sc: dict, i: int, ks: np.ndarray, hours: np.ndarray) -> np.ndarray:
        """Desviación prevista de `name` para las antelaciones `ks` (horas del día `hours`)."""
        own, oth = sc[name], sc[other]
        z, zo = self.z[name], self.z[other]
        vals = {"z0": own["0"], "z1": own["1"], "z2": own["2"], "zm24": own["m24"], "zm6": own["m6"],
                "zyL": own["yL"], "zd": own["d"], "zyd": own["yd"], "zy": z[i + ks - 24], "zy2": z[i + ks - 48],
                "o2": oth["2"], "om24": oth["m24"], "oy": zo[i + ks - 24]}
        X = np.empty((len(ks), len(self.feats)))
        for j, f in enumerate(self.feats):
            X[:, j] = vals[f]
        C = self.full[name][ks - KNOWN_HOURS, hours]                    # [n][F+1]
        zhat = (X * C[:, :-1]).sum(axis=1) + C[:, -1]
        bad = ~np.isfinite(zhat)
        if bad.any():
            # Falta alguna pista (semana sin memoria del train): se decide como el agente actual, con su
            # regresión de 6 pistas si hay medio día de historia y, si no, con la de las 3 horas conocidas.
            base, cold = self.reg[name]
            Cb = base[ks - KNOWN_HOURS]
            zb = (Cb[:, 0] * own["0"] + Cb[:, 1] * own["1"] + Cb[:, 2] * own["2"] + Cb[:, 3] * own["m24"]
                  + Cb[:, 4] * own["m6"] + Cb[:, 5] * vals["zy"] + Cb[:, 6])
            Cc = cold[ks - KNOWN_HOURS]
            zc = Cc[:, 0] * own["0"] + Cc[:, 1] * own["1"] + Cc[:, 2] * own["2"] + Cc[:, 3]
            zhat = np.where(bad, np.where(np.isfinite(zb), zb, zc), zhat)
        return np.clip(zhat, -Z_CLIP, Z_CLIP)

    def cand_forecast(self, obs, times: list):
        n_known = min(len(obs.price), len(obs.co2), len(times))
        if n_known < KNOWN_HOURS or times[0] is None:
            return None
        H = len(times)
        keys = [hour_index(t) for t in times]
        now = keys[0]
        if self.h0 is None or not (STORE_PAST_H // 2 <= now - self.h0 < STORE_LEN_H - 200):
            self.rebase(now)
        i = now - self.h0
        base = {name: np.array([self.profile(name, t) for t in times]) for name in NAMES}
        for name, arr in (("price", obs.price), ("co2", obs.co2)):
            for k in range(n_known):
                pos = keys[k] - self.h0
                if 0 <= pos < STORE_LEN_H:
                    self.z[name][pos] = log_ratio(float(arr[k]), float(base[name][k]))
        sc = {name: self.scalars(name, i, times[0].hour) for name in NAMES}
        for name in NAMES:
            if not all(math.isfinite(sc[name][j]) for j in ("0", "1", "2")):
                return None
        month = times[0].month
        ks = np.array([k for k in range(n_known, H) if keys[k] - now == k and times[k].month == month], dtype=int)
        ks = ks[ks < LEADS + KNOWN_HOURS]
        out = []
        for name, other, arr in (("price", "co2", obs.price), ("co2", "price", obs.co2)):
            b = base[name]
            if not (np.isfinite(b).all() and (b > 0).all()):
                return None
            zhat = np.zeros(H)                      # otra semana del test (otro mes): solo el perfil
            if len(ks):
                hours = np.array([times[k].hour for k in ks], dtype=int)
                zhat[ks] = self.predict(name, other, sc, i, ks, hours)
            x = b * np.exp(zhat)
            x[:n_known] = np.asarray(arr[:n_known], dtype=float)
            if not np.isfinite(x).all():
                return None
            out.append(np.maximum(x, 0.0))
        return out[0], out[1]

    def forecast(self, obs, times: list, weather: Optional[dict] = None) -> tuple:
        """Precio y CO2 para cada fecha de `times` ([0] = hora actual). Lo conocido se respeta. Nunca falla."""
        out = None
        if self.cand_ok:
            try:
                out = self.cand_forecast(obs, times)
                if out is not None:
                    self.remember(obs, times)       # la clase madre sigue al día por si hay que volver a ella
            except Exception:
                out = None
        if out is None:
            try:
                out = super().forecast(obs, times, weather)
            except Exception:
                out = None
        return self.repair(obs.price, out[0] if out else None, len(times)), self.repair(obs.co2, out[1] if out else None, len(times))

    @staticmethod
    def repair(known, x, n: int) -> np.ndarray:
        """Último seguro: `n` valores finitos y >= 0. Un hueco se rellena con el último valor válido."""
        try:
            x = np.array(x, dtype=float).ravel()
        except Exception:
            x = np.empty(0)
        if len(x) != n:
            try:
                k = np.array(known, dtype=float).ravel()[:n]
            except Exception:
                k = np.empty(0)
            x = np.r_[k, np.full(n - len(k), np.nan)]
        bad = ~np.isfinite(x)
        if bad.any():
            good = x[~bad]
            last = float(good[0]) if len(good) else 0.0
            for j in range(n):
                if bad[j]:
                    x[j] = last
                else:
                    last = x[j]
        return np.maximum(x, 0.0)
