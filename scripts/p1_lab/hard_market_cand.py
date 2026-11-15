"""Candidato de previsión de PRECIO y CO2 para el HARD MODE (encargo "mercado"). Laboratorio de P1.

Uso con el banco:
    python scripts/p1_hard.py --split dev --market scripts/p1_lab/hard_market_cand.py:make --only "agente actual,CANDIDATO"

Qué cambia frente a battery.hard_market.MarketForecaster (el agente actual). Sigue siendo lo mismo: perfil
por mes, tipo de día y hora, y una regresión lineal por antelación (3 a 23 h) de la desviación
z = log(real / perfil). Lo nuevo:
1. MEMORIA DEL TRAIN ("semilla"). El test de cada mes empieza justo donde acaba el train de ese mes
   (train: días 1 a 23/24; test: los 7 últimos). "Ayer" y "las últimas 24 h" de la primera hora de cada
   semana SÍ se conocen: están en el train. Se guardan los últimos 7 días de cada tramo del train y la
   semana ya no arranca a ciegas.
2. EL NIVEL DEL DÍA. El precio de un día entero se fija de una vez (mercado diario): las horas de un mismo
   día se parecen entre sí más que a las de la víspera. Pistas nuevas: la media de z del día en curso
   (hasta la última hora conocida) y la del día anterior entero.
3. MÁS MEMORIA: ayer a la hora de la última conocida (para medir el salto de ayer a hoy a la misma hora) y
   anteayer a la hora objetivo.
4. LA OTRA VARIABLE: el precio ayuda a prever el CO2 y al revés (última hora conocida, media de 24 h y
   ayer a la hora objetivo).
Si falta alguna pista (una semana sin memoria del train), decide exactamente como el agente actual.

La clase MarketCand solo usa numpy, pandas y math (se puede empaquetar). El ajuste (fit_cand) es del
laboratorio: iría a scripts/p1_hard.py. Lo probado y lo descartado: results/p1_hard/mercado_notas.md.
"""
import math
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
for _p in (str(REPO / "src"), str(REPO / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from battery.hard_market import KNOWN_HOURS, MarketForecaster, hour_index  # noqa: E402

NAMES = ("price", "co2")
LEADS = 21                  # antelaciones con regresión: de 3 a 23 horas
SEED_HOURS = 168            # horas del final de cada tramo del train que se guardan como memoria (7 días;
                            # las pistas miran 48 h atrás como mucho: el resto es margen)
STORE_PAST_H = 24 * 40      # horas hacia atrás que caben en la memoria densa
STORE_LEN_H = 24 * 460      # un año de test y margen
Z_CLIP = 2.0                # la desviación prevista se limita a e^-2..e^2 (igual que el agente actual), y la
                            # observada también: en el train no pasa de 1,2; solo protege de un precio 0 o disparatado
BLOCK_DAYS = 7              # (laboratorio) bloques de días del mes para la variante de perfil cruzado
# Pistas de la regresión. z = desviación de la propia variable, o = desviación de la otra.
#   z0, z1, z2  las tres horas conocidas            zm24, zm6  media de las últimas 24 y 6 horas
#   zy, zy2     ayer y anteayer a la hora objetivo  zyL        ayer a la hora de la última conocida
#   zd, zyd     media del día en curso (hasta la última hora conocida) y del día anterior entero
#   o2, om24, oy   de la otra variable: última hora conocida, media de 24 h y ayer a la hora objetivo
FEATS = ("z0", "z1", "z2", "zm24", "zm6", "zy", "zyL", "zy2", "zd", "zyd", "o2", "om24", "oy")
COLD_FEATS = ("z0", "z1", "z2")
# ridge_hour < 0: una regresión común por antelación. >= 0: otra por hora del día, encogida hacia la común.
DEFAULT_CFG = {"feats": FEATS, "crossfit": False, "ridge_hour": -1.0, "seed_hours": SEED_HOURS, "smear": False}


# ------------------------------------------------------------------------------- inferencia
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


# ------------------------------------------------------------------------------- ajuste (laboratorio)
def dense_market(exclude=None) -> pd.DataFrame:
    """Precio y CO2 del train, una fila por hora del calendario (NaN donde no hay dato o está excluido)."""
    from p1_hard import market_frame
    m = market_frame()
    d = m.reindex(pd.date_range(m.index.min().normalize(), m.index.max(), freq="h"))
    if exclude:
        d.loc[d.index.isin(list(exclude))] = np.nan
    return d


def day_types(index) -> np.ndarray:
    """Tipo de día de cada hora, con la misma regla que usa el agente (battery.hard_market.market_day_type)."""
    from battery.hard_market import market_day_type
    by_day = {}
    out = np.empty(len(index), dtype=int)
    for j, (y, mo, dd) in enumerate(zip(index.year, index.month, index.day)):
        key = (y, mo, dd)
        if key not in by_day:
            by_day[key] = market_day_type(index[j])
        out[j] = by_day[key]
    return out


def profile_sums(v: np.ndarray, mo: np.ndarray, typ: np.ndarray, hr: np.ndarray, mask: np.ndarray) -> tuple:
    """Sumas y cuentas por (mes, tipo de día, hora) de las horas de `mask` con dato."""
    ok = mask & np.isfinite(v)
    flat = mo[ok] * 72 + typ[ok] * 24 + hr[ok]
    s = np.bincount(flat, weights=v[ok], minlength=864).reshape(12, 3, 24)
    c = np.bincount(flat, minlength=864).reshape(12, 3, 24).astype(float)
    return s, c


def profile_from(s: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Media por (mes, tipo, hora); si un tipo de día no tiene datos, la media del mes a esa hora."""
    by_h = s.sum(axis=1, keepdims=True) / np.where(c.sum(axis=1, keepdims=True) > 0, c.sum(axis=1, keepdims=True), np.nan)
    return np.where(c > 0, s / np.where(c > 0, c, 1.0), by_h)


def at(z: np.ndarray, off: int) -> np.ndarray:
    """a[t] = z[t + off] (NaN fuera)."""
    out = np.full(len(z), np.nan)
    if off >= 0:
        if off < len(z):
            out[:len(z) - off] = z[off:]
    elif -off < len(z):
        out[-off:] = z[:off]
    return out


def roll_mean(z: np.ndarray, w: int, min_count: int) -> np.ndarray:
    """Media de z[t-w+1..t] sin contar huecos (NaN con menos de `min_count` valores)."""
    ok = np.isfinite(z)
    cs = np.r_[0.0, np.cumsum(np.where(ok, z, 0.0))]
    cn = np.r_[0, np.cumsum(ok)]
    idx = np.arange(len(z))
    lo = np.maximum(idx - w + 1, 0)
    n = cn[idx + 1] - cn[lo]
    return np.where(n >= min_count, (cs[idx + 1] - cs[lo]) / np.maximum(n, 1), np.nan)


def day_means(z: np.ndarray, hour: np.ndarray) -> tuple:
    """Para cada hora j: media de z desde las 00 h de su día hasta j, y media de z del día anterior entero
    (NaN con menos de 12 horas)."""
    ok = np.isfinite(z)
    cs = np.r_[0.0, np.cumsum(np.where(ok, z, 0.0))]
    cn = np.r_[0, np.cumsum(ok)]
    j = np.arange(len(z))
    start = np.maximum(j - hour, 0)
    n = cn[j + 1] - cn[start]
    today = np.where(n >= 1, (cs[j + 1] - cs[start]) / np.maximum(n, 1), np.nan)
    ys = np.maximum(start - 24, 0)
    n2 = cn[start] - cn[ys]
    yday = np.where(n2 >= 12, (cs[start] - cs[ys]) / np.maximum(n2, 1), np.nan)
    return today, yday


def training_rows(d: pd.DataFrame, feats: tuple, crossfit: bool, blend: bool = False, weekend: bool = False) -> dict:
    """Filas de ajuste por variable y antelación: {name: [(X, Xcold, y, hora_objetivo) para k = 3..23]}.

    Con `crossfit`, cada bloque de días se mide contra el perfil del resto de su mes, y solo cuentan
    las filas con la hora actual y la hora objetivo dentro del bloque: igual que una semana del test."""
    idx = d.index
    mo, hr = idx.month.to_numpy() - 1, idx.hour.to_numpy()
    typ = day_types(idx)
    ym = idx.year.to_numpy() * 12 + mo
    block = np.minimum((idx.day.to_numpy() - 1) // BLOCK_DAYS, 3) if crossfit else np.zeros(len(idx), dtype=int)
    vals = {name: d[name].to_numpy(float) for name in NAMES}
    centers = None
    if blend:       # perfil interpolado entre meses según el día, como battery.hard_market.month_blend
        from p1_hard import blend_lookup, market_centers
        centers = market_centers(idx[np.isfinite(vals["price"]) & np.isfinite(vals["co2"])])
    day = idx.day.to_numpy(float)
    everything = np.ones(len(idx), dtype=bool)
    import p1_hard as bench_mod
    geo = bool(getattr(bench_mod, "PROFILE_GEO", False))
    pvals = {name: (np.log(np.clip(vals[name], 1e-6, None)) if geo else vals[name]) for name in NAMES}
    tot = {name: profile_sums(pvals[name], mo, typ, hr, everything) for name in NAMES}
    rows = {name: [[] for _ in range(LEADS)] for name in NAMES}
    pad = 200
    for m_id in np.unique(ym):
        in_month = ym == m_id
        lo, hi = int(np.argmax(in_month)), int(len(idx) - np.argmax(in_month[::-1]))
        sl = slice(lo, hi)
        for b in np.unique(block[sl]):
            in_block = in_month & (block == b)
            z = {}
            for name in NAMES:
                s, c = tot[name]
                if crossfit:
                    sb, cb = profile_sums(pvals[name], mo, typ, hr, in_block)
                    s, c = s - sb, c - cb
                table = np.exp(profile_from(s, c)) if geo else profile_from(s, c)
                if weekend:     # sábados y domingos suavizados con los meses vecinos, como en fit_market
                    from p1_hard import smooth_weekend
                    table = smooth_weekend(table)
                if centers is None:
                    prof = table[mo[sl], typ[sl], hr[sl]]
                else:
                    from p1_hard import blend_lookup
                    prof = blend_lookup(table, mo[sl], day[sl], typ[sl], hr[sl], centers)
                zz = np.log(np.clip(vals[name][sl], 1e-6, None) / np.clip(prof, 1e-6, None))
                z[name] = np.r_[np.full(pad, np.nan), zz, np.full(pad, np.nan)]
            inb = np.r_[np.zeros(pad, bool), in_block[sl], np.zeros(pad, bool)]
            hour = np.r_[np.zeros(pad, int), hr[sl], np.zeros(pad, int)]
            fixed = {}
            for name, other in (("price", "co2"), ("co2", "price")):
                zo = z[other]
                today, yday = day_means(z[name], hour)
                fixed[name] = {"z0": z[name], "z1": at(z[name], 1), "z2": at(z[name], 2),
                               "zm24": roll_mean(z[name], 24, 12), "zm6": roll_mean(z[name], 6, 3),
                               "zyL": at(z[name], -22), "o2": at(zo, 2), "om24": roll_mean(zo, 24, 12),
                               "zd": at(today, 2), "zyd": at(yday, 2)}
            for k in range(KNOWN_HOURS, KNOWN_HOURS + LEADS):
                tgt_in = at(inb.astype(float), k) == 1.0
                keep_rows = inb & tgt_in
                hour_t = at(hour.astype(float), k)
                for name, other in (("price", "co2"), ("co2", "price")):
                    f = dict(fixed[name])
                    f["zy"], f["zy2"], f["oy"] = at(z[name], k - 24), at(z[name], k - 48), at(z[other], k - 24)
                    y = at(z[name], k)
                    X = np.vstack([f[n] for n in feats]).T
                    Xc = np.vstack([f[n] for n in COLD_FEATS]).T
                    keep = keep_rows & np.isfinite(y) & np.isfinite(Xc).all(axis=1)
                    rows[name][k - KNOWN_HOURS].append((X[keep], Xc[keep], y[keep], hour_t[keep].astype(int)))
    out = {}
    for name in NAMES:
        out[name] = []
        for parts in rows[name]:
            out[name].append(tuple(np.concatenate([p[j] for p in parts]) for j in range(4)))
    return out


def ridge_by_hour(X: np.ndarray, y: np.ndarray, hour: np.ndarray, ridge_hour: float, smear: bool = False) -> np.ndarray:
    """Regresión común (mínimos cuadrados) y, para cada hora objetivo, otra encogida hacia la común:
    minimiza ||y - Xb||^2 + ridge_hour * ||b - b_común||^2. Con ridge_hour < 0, solo la común.
    Con `smear`, corrige el sesgo de volver del logaritmo: exp(media de z) queda por debajo de la media
    real, así que se suma al término independiente log(media de exp(residuo)) (estimador de Duan).
    Devuelve [24][F+1] (el último coeficiente es el término independiente)."""
    A = np.c_[X, np.ones(len(X))]
    nf = A.shape[1]
    if len(A) < 4 * nf:
        return np.zeros((24, nf))
    common = np.linalg.solve(A.T @ A + 1e-6 * np.eye(nf), A.T @ y)
    out = np.tile(common, (24, 1))
    if ridge_hour >= 0:
        for h in range(24):
            sel = hour == h
            if sel.sum() >= nf:
                Ah, yh = A[sel], y[sel]
                out[h] = np.linalg.solve(Ah.T @ Ah + ridge_hour * np.eye(nf), Ah.T @ yh + ridge_hour * common)
    if smear:
        resid = y - (A * out[hour]).sum(axis=1)
        out[:, -1] += float(np.log(np.clip(np.exp(np.clip(resid, -Z_CLIP, Z_CLIP)).mean(), 1.0, 1.25)))
    return out


def ridge_cv(X: np.ndarray, y: np.ndarray, lams=(0.0, 10.0, 30.0, 100.0, 300.0, 1000.0, 3000.0), folds: int = 6) -> tuple:
    """(Laboratorio) Regresión común con encogimiento elegido SOLO con el train: 6 pliegues seguidos en el
    tiempo (unos 2 meses cada uno). Devuelve (coeficientes [F+1], lambda elegida)."""
    A = np.c_[X, np.ones(len(X))]
    nf = A.shape[1]
    P = np.eye(nf)
    P[-1, -1] = 0.0                                   # el término independiente no se encoge
    fold = (np.arange(len(y)) * folds) // max(len(y), 1)
    best, best_err = lams[0], float("inf")
    for lam in lams:
        err = 0.0
        for f in range(folds):
            tr = fold != f
            b = np.linalg.solve(A[tr].T @ A[tr] + lam * P + 1e-9 * np.eye(nf), A[tr].T @ y[tr])
            err += float(((A[~tr] @ b - y[~tr]) ** 2).sum())
        if err < best_err:
            best, best_err = lam, err
    return np.linalg.solve(A.T @ A + best * P + 1e-9 * np.eye(nf), A.T @ y), best


def seed_segments(d: pd.DataFrame, seed_hours: int) -> list:
    """Las últimas `seed_hours` horas de cada tramo seguido de datos del train."""
    ok = np.isfinite(d["price"].to_numpy()) & np.isfinite(d["co2"].to_numpy())
    ends = np.flatnonzero(ok & ~np.r_[ok[1:], False])
    segs = []
    for e in ends:
        s = e
        while s > 0 and ok[s - 1] and e - s + 1 < seed_hours:
            s -= 1
        segs.append({"start": int(hour_index(d.index[s])),
                     "price": [float(v) for v in d["price"].to_numpy()[s:e + 1]],
                     "co2": [float(v) for v in d["co2"].to_numpy()[s:e + 1]]})
    return segs


def fit_cand(exclude=None, cfg: Optional[dict] = None) -> dict:
    """Tablas del candidato ajustadas con el train sin las horas de `exclude`."""
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    feats = tuple(cfg["feats"])
    d = dense_market(exclude)
    rows = training_rows(d, feats, bool(cfg["crossfit"]), bool(cfg.get("blend", False)), bool(cfg.get("weekend", False)))
    full = {}
    for name in NAMES:
        full[name] = []
        for X, Xc, y, hour in rows[name]:
            ok = np.isfinite(X).all(axis=1)
            if cfg.get("ridge_cv"):
                coef, lam = ridge_cv(X[ok], y[ok])
                full[name].append(coef.tolist())
                continue
            coef = ridge_by_hour(X[ok], y[ok], hour[ok], cfg["ridge_hour"], cfg["smear"])
            full[name].append((coef if cfg["ridge_hour"] >= 0 else coef[0]).tolist())
    seed = seed_segments(d, int(cfg["seed_hours"])) if cfg["seed_hours"] else []
    return {"feats": list(feats), "full": full, "seed": seed}


def to_prior(exclude=None, cfg: Optional[dict] = None) -> dict:
    """Lo que hay que añadir a models/hard_market.json bajo la clave "cand" (todo números y listas)."""
    return fit_cand(exclude, cfg)


def make(exclude, prior):
    """Fábrica para el banco: scripts/p1_hard.py --market scripts/p1_lab/hard_market_cand.py:make"""
    return MarketCand({**prior, "cand": fit_cand(exclude)})
