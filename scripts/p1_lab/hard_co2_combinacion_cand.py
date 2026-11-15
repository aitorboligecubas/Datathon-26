"""Candidato "combinacion" para la previsión del CO2 del HARD MODE. Laboratorio de P1 (domingo 15/11).

Uso con el banco:
    python scripts/p1_hard.py --split dev --only "agente actual,CANDIDATO" \
        --market scripts/p1_lab/hard_co2_combinacion_cand.py:make

Idea: la previsión de la desviación del CO2 (z = log(real / perfil)) de la v14 es una regresión lineal por
antelación (battery.hard_market.MarketCand). Aquí se promedia, con pesos FIJOS, con otros previsores:
  - "knn":  días parecidos. De todo el train se buscan las K horas, a la misma hora del día, cuyas últimas 24
            desviaciones (21 vistas y las 3 conocidas) más se parecen a las de ahora, y se promedia lo que pasó
            después en ellas (antelaciones de 3 a 23 h). Es el único miembro NO lineal.
  - "lvl":  el perfil con el nivel reciente (media de z de las últimas 24 h).
  - "yday": ayer a la misma hora.
El precio no se toca: se prevé igual que en la v14. Si falta algo o algo falla, decide como MarketCand.

La inferencia solo usa numpy, pandas y math. La "biblioteca" de días parecidos son las series de precio y CO2
del train (2 x 6.900 números): caben en JSON.

RESULTADO (domingo 15/11, 08:00-08:30): NINGUNA variante cumple el criterio (ganar en 4 de 5 ventanas con media
>= +0,03). Dif. de score frente a la v14 en dev, 1-7, 3-9, 12-18 y 15-21:
    make        (regresión + días parecidos, 50/50)   -0,177 -0,141 -0,140 -0,192 -0,178
    make_third  (2/3 + 1/3)                           -0,090 -0,072 -0,082 -0,125 -0,100
    make_all4   (media de los 4)                      -0,524 (solo dev)
    make_cal    (recalibrada por antelación)          +0,008 -0,005 -0,017 -0,038  0,000
    make_wls    (filas ponderadas por nivel^2)        -0,001 -0,012 +0,016 +0,004  0,000
    make_wls1   (filas ponderadas por nivel)          -0,001 +0,003 +0,023 +0,012 +0,012   (media +0,010: ruido)
    make_smooth (suavizar entre antelaciones)         -0,022 -0,012 +0,001 +0,008 +0,011
    make_dn     (regresión de día y de noche)         -0,034 -0,042 -0,040 -0,004 +0,042
  Lo único que no pierde: la regresión a medias con días parecidos que prevén EL CAMBIO desde la última hora
  conocida ("delta"). Gana poco y no llega al umbral:
    make_delta    (contexto 24 h, todas las antelaciones)   0,000 +0,008 +0,045 +0,040 +0,002   (media +0,019)
    make_delta35  (contexto 24 h, solo 3-5 h)              +0,020 +0,011 +0,013 +0,018  0,000   (media +0,012)
    make_d12      (contexto 12 h, todas)                   -0,014 +0,041 +0,042 +0,048 -0,013   (media +0,021)
    make_d12_8    (contexto 12 h, solo 3-8 h)              -0,002 +0,039 +0,014 +0,035 -0,005   (media +0,016)
Diagnóstico que queda (diag_real_*): con el CO2 REAL solo a 3-5 h se gana +0,22 (dev y 15-21) de un techo de
+0,24 / +0,37 con el CO2 real a 3-23 h; con el CO2 real solo a 12-23 h, 0,00 / +0,02. Lo único que da score es
acertar las antelaciones de 3 a 5 h (8 h como mucho). Salidas: results/p1_hard/co2_combinacion_*.txt
"""
import sys
from pathlib import Path
from typing import Optional

import numpy as np

REPO = Path(__file__).resolve().parents[2]
for _p in (str(REPO / "src"), str(REPO / "scripts"), str(REPO / "scripts" / "p1_lab")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from battery.hard_market import KNOWN_HOURS, LEADS, NAMES, Z_CLIP, MarketCand, log_ratio  # noqa: E402

CTX_H = 24                  # horas de contexto de "días parecidos": las 21 últimas vistas y las 3 conocidas
ROW_H = CTX_H + LEADS       # contexto + las 21 antelaciones (de 3 a 23 h)
KNN_K = 20                  # vecinos que se promedian (de unos 250 candidatos por hora del día)


class ComboCand(MarketCand):
    """MarketCand con la desviación prevista del CO2 promediada con otros previsores (pesos fijos).

    prior["combo"] = {"weights": {"reg": .., "knn": .., "lvl": .., "yday": ..},
                      "series": [{"start": número de hora, "price": [...], "co2": [...]}, ...],   # train entero
                      "k": vecinos, "delta": bool, "ctx_price": bool}
    """

    def __init__(self, prior: Optional[dict] = None, **kwargs):
        super().__init__(prior, **kwargs)
        self.combo_w = {}
        self.lib = {}
        self.knn_k, self.knn_delta, self.knn_price = KNN_K, False, False
        self.scale = None           # [21] factor por antelación sobre la desviación prevista del CO2 (calibración)
        self.smooth = False         # media móvil de 3 antelaciones sobre la desviación prevista del CO2
        self.max_lead = 0
        self.ctx_h = CTX_H          # horas de contexto de los días parecidos (las últimas, hasta la última conocida)
        try:
            c = prior["combo"]
            self.smooth = bool(c.get("smooth", False))
            self.max_lead = int(c.get("max_lead", 0))     # > 0: la combinación solo se aplica hasta esa antelación
            self.ctx_h = min(max(int(c.get("ctx_h", CTX_H)), KNOWN_HOURS), 48)
            if c.get("scale") is not None:
                sc = np.asarray(c["scale"], dtype=float)
                if sc.shape == (LEADS,) and np.isfinite(sc).all():
                    self.scale = sc
            w = {str(m): float(v) for m, v in c["weights"].items() if float(v) > 0}
            self.knn_k = int(c.get("k", KNN_K))
            self.knn_delta = bool(c.get("delta", False))
            self.knn_price = bool(c.get("ctx_price", False))
            if w.get("knn", 0.0) > 0:
                self.lib = self.build_library(c["series"])
            self.combo_w = w
        except Exception:
            self.combo_w = {}

    def build_library(self, series: list) -> dict:
        """{hora del día: (contextos [N][24 o 48], futuros [N][21])} con las desviaciones del train."""
        ctx = [[] for _ in range(24)]
        fut = [[] for _ in range(24)]
        ch = self.ctx_h
        row_h = ch + LEADS
        off = np.arange(row_h)
        for seg in series:
            start, n = int(seg["start"]), len(seg["co2"])
            if n < row_h:
                continue
            z = {}
            for name in NAMES:
                z[name] = np.array([log_ratio(float(seg[name][j]), self.profile_at(name, start + j)) for j in range(n)])
            rows = np.arange(n - row_h + 1)[:, None] + off[None, :]
            zc = z["co2"][rows]
            c = zc[:, :ch]
            if self.knn_price:
                c = np.c_[c, z["price"][rows][:, :ch]]
            f = zc[:, ch:]
            ok = np.isfinite(c).all(axis=1) & np.isfinite(f).all(axis=1)
            hour_now = (start + (ch - KNOWN_HOURS) + np.arange(len(rows))) % 24
            for h in range(24):
                sel = ok & (hour_now == h)
                if sel.any():
                    ctx[h].append(c[sel])
                    fut[h].append(f[sel])
        return {h: (np.vstack(ctx[h]), np.vstack(fut[h])) for h in range(24) if ctx[h]}

    def knn(self, i: int, ks: np.ndarray, hour_now: int):
        """Desviación del CO2 prevista por días parecidos (None si no se puede)."""
        lib = self.lib.get(hour_now)
        if lib is None:
            return None
        C, F = lib
        if len(C) < 2 * self.knn_k:
            return None
        ch = self.ctx_h
        lo, hi = i - (ch - KNOWN_HOURS), i + KNOWN_HOURS
        c = self.z["co2"][lo:hi]
        if self.knn_price:
            c = np.r_[c, self.z["price"][lo:hi]]
        if len(c) != C.shape[1] or not np.isfinite(c).all():
            return None
        d = ((C - c) ** 2).sum(axis=1)
        nn = np.argpartition(d, self.knn_k)[:self.knn_k]
        f = F[nn]
        if self.knn_delta:      # lo que cambió después en los días parecidos, sumado a la última hora conocida
            fhat = c[ch - 1] + (f - C[nn, ch - 1][:, None]).mean(axis=0)
        else:
            fhat = f.mean(axis=0)
        return fhat[ks - KNOWN_HOURS]

    def predict(self, name: str, other: str, sc: dict, i: int, ks: np.ndarray, hours: np.ndarray) -> np.ndarray:
        zreg = super().predict(name, other, sc, i, ks, hours)
        if name != "co2" or not self.combo_w or not len(ks):
            return zreg
        try:
            z = self.z[name]
            members = {"reg": zreg}
            if "lvl" in self.combo_w:
                members["lvl"] = np.full(len(ks), sc[name]["m24"])
            if "yday" in self.combo_w:
                members["yday"] = z[i + ks - 24]
            if "knn" in self.combo_w:
                members["knn"] = self.knn(i, ks, int((hours[0] - ks[0]) % 24))
            num, den = np.zeros(len(ks)), np.zeros(len(ks))
            for m, wt in self.combo_w.items():
                v = members.get(m)
                if v is None:
                    continue
                ok = np.isfinite(v)
                num += np.where(ok, v, 0.0) * wt
                den += ok * wt
            out = np.where(den > 0, num / np.maximum(den, 1e-12), zreg)
            if self.max_lead > 0:
                out = np.where(ks <= self.max_lead, out, zreg)
            if self.scale is not None:
                out = out * self.scale[ks - KNOWN_HOURS]
            if self.smooth and len(ks) >= 2 and bool(np.all(np.diff(ks) == 1)):
                first = sc[name]["2"] if ks[0] == KNOWN_HOURS else out[0]      # la última hora conocida
                out = (np.r_[first, out[:-1]] + out + np.r_[out[1:], out[-1]]) / 3.0
            return np.clip(np.where(np.isfinite(out), out, zreg), -Z_CLIP, Z_CLIP)
        except Exception:
            return zreg


# ------------------------------------------------------------------------------- ajuste (laboratorio)
def train_series(exclude) -> list:
    """Series de precio y CO2 del train sin las horas de `exclude`, por tramos seguidos (la biblioteca)."""
    from hard_market_cand import dense_market, seed_segments
    return seed_segments(dense_market(exclude), 10 ** 6)


def build(exclude, prior, weights: dict, **opts):
    return ComboCand({**prior, "combo": {"weights": weights, "series": train_series(exclude), **opts}})


def make(exclude, prior):
    """Regresión de la v14 y días parecidos, a partes iguales."""
    return build(exclude, prior, {"reg": 0.5, "knn": 0.5})


def make_knnp(exclude, prior):
    """Como make, con el precio en el contexto de los días parecidos."""
    return build(exclude, prior, {"reg": 0.5, "knn": 0.5}, ctx_price=True)


def make_delta(exclude, prior):
    """Como make, con los días parecidos previendo el cambio desde la última hora conocida."""
    return build(exclude, prior, {"reg": 0.5, "knn": 0.5}, delta=True)


def make_delta35(exclude, prior):
    """Como make_delta, pero la combinación solo se aplica a las antelaciones de 3 a 5 h (las que dan score)."""
    return build(exclude, prior, {"reg": 0.5, "knn": 0.5}, delta=True, max_lead=5)


def make_d6(exclude, prior):
    """make_delta con 6 horas de contexto (la tendencia reciente) en vez de 24."""
    return build(exclude, prior, {"reg": 0.5, "knn": 0.5}, delta=True, ctx_h=6)


def make_d12(exclude, prior):
    return build(exclude, prior, {"reg": 0.5, "knn": 0.5}, delta=True, ctx_h=12)


def make_d6_8(exclude, prior):
    """make_d6 aplicado solo a las antelaciones de 3 a 8 h (donde está todo el hueco del CO2)."""
    return build(exclude, prior, {"reg": 0.5, "knn": 0.5}, delta=True, ctx_h=6, max_lead=8)


def make_d12_8(exclude, prior):
    return build(exclude, prior, {"reg": 0.5, "knn": 0.5}, delta=True, ctx_h=12, max_lead=8)


def make_delta8(exclude, prior):
    """make_delta (24 h de contexto) aplicado solo a las antelaciones de 3 a 8 h."""
    return build(exclude, prior, {"reg": 0.5, "knn": 0.5}, delta=True, max_lead=8)


def make_all4(exclude, prior):
    """Media simple de los cuatro previsores."""
    return build(exclude, prior, {"reg": 0.25, "knn": 0.25, "lvl": 0.25, "yday": 0.25})


def make_third(exclude, prior):
    """Dos tercios de regresión y un tercio de días parecidos."""
    return build(exclude, prior, {"reg": 2.0 / 3.0, "knn": 1.0 / 3.0})


CAL_WINDOWS = ((1, 7), (8, 14), (15, 21))        # ventanas de días del mes donde se mide la calibración
CAL_GROUPS = ((3, 5), (6, 11), (12, 17), (18, 23))  # grupos de antelación (los de r3_coste_notas.md)


def calibration_pairs(exclude) -> tuple:
    """(z previsto, z real, antelación) del CO2 con la regresión de la v14, FUERA DE MUESTRA y sin tocar las
    horas de `exclude`: en cada ventana de calibración que no pisa los días de `exclude`, se ajusta todo sin
    esa ventana (ni `exclude`) y se pasa el previsor por ella como en el test."""
    import math
    from types import SimpleNamespace
    import pandas as pd
    import p1_hard as B
    one_h = pd.Timedelta(hours=1)
    m = B.market_frame()
    exclude = set(exclude or ())
    days_out = {t.day for t in exclude}
    truth = {t: (float(p), float(c)) for t, p, c in zip(m.index, m.price, m.co2)}
    zp, zr, kk = [], [], []
    for a, b in CAL_WINDOWS:
        if any(a <= d <= b for d in days_out):
            continue
        cal = [t for t in m.index if a <= t.day <= b]
        cal_set = set(cal)
        fc = MarketCand(B.fit_market(exclude | cal_set, None))
        for ts in cal:
            near = [ts + j * one_h for j in range(KNOWN_HOURS)]
            known = [truth.get(t) for t in near]
            if any(v is None for v in known) or any(t in exclude for t in near):
                continue
            obs = SimpleNamespace(price=np.array([v[0] for v in known]), co2=np.array([v[1] for v in known]))
            times = [ts + k * one_h for k in range(24)]
            _, co2 = fc.forecast(obs, times, None)
            for k in range(KNOWN_HOURS, 24):
                t = times[k]
                if t in cal_set and t.month == ts.month:
                    prof = fc.profile("co2", t)
                    if prof > 0 and co2[k] > 0 and truth[t][1] > 0:
                        zp.append(math.log(co2[k] / prof))
                        zr.append(math.log(truth[t][1] / prof))
                        kk.append(k)
    return np.array(zp), np.array(zr), np.array(kk)


def calibration_scale(exclude) -> list:
    """Factor por antelación = pendiente de z real frente a z previsto en cada grupo de antelaciones."""
    zp, zr, kk = calibration_pairs(exclude)
    scale = np.ones(LEADS)
    for a, b in CAL_GROUPS:
        s = (kk >= a) & (kk <= b)
        if s.sum() >= 1000 and np.var(zp[s]) > 0:
            slope = float(np.cov(zr[s], zp[s])[0, 1] / np.var(zp[s], ddof=1))
            scale[a - KNOWN_HOURS:b - KNOWN_HOURS + 1] = min(max(slope, 0.8), 1.3)
    return [float(v) for v in scale]


def make_cal(exclude, prior):
    """La regresión de la v14 con la desviación del CO2 recalibrada por antelación (pendiente medida fuera de
    muestra en otras ventanas del train)."""
    return ComboCand({**prior, "combo": {"weights": {"reg": 1.0}, "scale": calibration_scale(exclude)}})


def make_smooth(exclude, prior):
    """La regresión de la v14 con la desviación prevista del CO2 suavizada entre antelaciones vecinas (media de 3)."""
    return ComboCand({**prior, "combo": {"weights": {"reg": 1.0}, "smooth": True}})


def make_only(member: str, **opts):
    """Fábrica de un previsor solo (para medir cada uno por separado)."""
    def fac(exclude, prior):
        return build(exclude, prior, {member: 1.0}, **opts)
    return fac


# ------------------------------------------------------------------------------- ajuste ponderado por el nivel
# La regresión de la v14 minimiza el error RELATIVO (en logaritmos): un 15 % de error pesa igual con el CO2 a 0,03
# que a 0,25 kg/kWh. El score cuenta kg: el error ABSOLUTO es nivel x error relativo. Aquí se ajusta la misma
# regresión (mismas 13 pistas, mismas tablas, misma inferencia) con cada fila ponderada por el nivel previsto del
# CO2 en la hora objetivo al cuadrado (perfil x exp(z previsto por la regresión sin ponderar)). No usa el valor
# real de la hora objetivo en el peso (eso sesgaría la previsión hacia arriba).
def co2_rows_with_level(exclude, feats: tuple) -> list:
    """Como hard_market_cand.training_rows (perfil interpolado y fines de semana suavizados, igual que la v14),
    solo para el CO2 y devolviendo el perfil de la hora objetivo: [(X, y, perfil objetivo) para k = 3..23]."""
    import hard_market_cand as L
    from p1_hard import blend_lookup, market_centers, smooth_weekend
    d = L.dense_market(exclude)
    idx = d.index
    mo, hr = idx.month.to_numpy() - 1, idx.hour.to_numpy()
    typ = L.day_types(idx)
    ym = idx.year.to_numpy() * 12 + mo
    vals = {name: d[name].to_numpy(float) for name in NAMES}
    centers = market_centers(idx[np.isfinite(vals["price"]) & np.isfinite(vals["co2"])])
    day = idx.day.to_numpy(float)
    everything = np.ones(len(idx), dtype=bool)
    tot = {name: L.profile_sums(vals[name], mo, typ, hr, everything) for name in NAMES}
    rows = [[] for _ in range(LEADS)]
    pad = 200
    for m_id in np.unique(ym):
        in_month = ym == m_id
        lo, hi = int(np.argmax(in_month)), int(len(idx) - np.argmax(in_month[::-1]))
        sl = slice(lo, hi)
        z, pr = {}, {}
        for name in NAMES:
            table = smooth_weekend(L.profile_from(*tot[name]))
            prof = blend_lookup(table, mo[sl], day[sl], typ[sl], hr[sl], centers)
            zz = np.log(np.clip(vals[name][sl], 1e-6, None) / np.clip(prof, 1e-6, None))
            z[name] = np.r_[np.full(pad, np.nan), zz, np.full(pad, np.nan)]
            pr[name] = np.r_[np.full(pad, np.nan), prof, np.full(pad, np.nan)]
        inb = np.r_[np.zeros(pad, bool), in_month[sl], np.zeros(pad, bool)]
        hour = np.r_[np.zeros(pad, int), hr[sl], np.zeros(pad, int)]
        zc, zo = z["co2"], z["price"]
        today, yday = L.day_means(zc, hour)
        fixed = {"z0": zc, "z1": L.at(zc, 1), "z2": L.at(zc, 2), "zm24": L.roll_mean(zc, 24, 12),
                 "zm6": L.roll_mean(zc, 6, 3), "zyL": L.at(zc, -22), "o2": L.at(zo, 2),
                 "om24": L.roll_mean(zo, 24, 12), "zd": L.at(today, 2), "zyd": L.at(yday, 2)}
        for k in range(KNOWN_HOURS, KNOWN_HOURS + LEADS):
            tgt_in = L.at(inb.astype(float), k) == 1.0
            f = dict(fixed)
            f["zy"], f["zy2"], f["oy"] = L.at(zc, k - 24), L.at(zc, k - 48), L.at(zo, k - 24)
            y = L.at(zc, k)
            X = np.vstack([f[n] for n in feats]).T
            keep = inb & tgt_in & np.isfinite(y) & np.isfinite(X).all(axis=1)
            rows[k - KNOWN_HOURS].append((X[keep], y[keep], L.at(pr["co2"], k)[keep]))
    return [tuple(np.concatenate([p[j] for p in parts]) for j in range(3)) for parts in rows]


def fit_level_weighted(exclude, prior, power: float = 2.0) -> tuple:
    """Coeficientes [21][F+1] del CO2 con las filas ponderadas por (nivel previsto) ** power.
    Devuelve (coeficientes, diferencia máxima entre el ajuste sin ponderar de aquí y el de la v14, filas efectivas)."""
    feats = tuple(prior["cand"]["feats"])
    ols = np.asarray(prior["cand"]["full"]["co2"], dtype=float)
    out, gap, neff = [], 0.0, []
    for i, (X, y, prof) in enumerate(co2_rows_with_level(exclude, feats)):
        A = np.c_[X, np.ones(len(X))]
        nf = A.shape[1]
        mine = np.linalg.solve(A.T @ A + 1e-6 * np.eye(nf), A.T @ y)
        gap = max(gap, float(np.abs(mine - ols[i]).max()))
        w = (prof * np.exp(A @ mine)) ** power
        w = w / w.mean()
        neff.append(float(w.sum() ** 2 / (w ** 2).sum()))
        Aw = A * w[:, None]
        out.append(np.linalg.solve(Aw.T @ A + 1e-6 * np.eye(nf), Aw.T @ y).tolist())
    return out, gap, neff


def make_wls(exclude, prior):
    """La regresión de la v14 con el CO2 ajustado con las filas ponderadas por el nivel previsto al cuadrado.
    La inferencia es MarketCand tal cual: solo cambian los números de la tabla del CO2."""
    try:
        coef, _, _ = fit_level_weighted(exclude, prior, 2.0)
        cand = dict(prior["cand"])
        cand["full"] = {"price": prior["cand"]["full"]["price"], "co2": coef}
        return MarketCand({**prior, "cand": cand})
    except Exception:
        return MarketCand(prior)


def make_wls1(exclude, prior):
    """Como make_wls, ponderando por el nivel previsto (sin elevar al cuadrado): más filas efectivas."""
    try:
        coef, _, _ = fit_level_weighted(exclude, prior, 1.0)
        cand = dict(prior["cand"])
        cand["full"] = {"price": prior["cand"]["full"]["price"], "co2": coef}
        return MarketCand({**prior, "cand": cand})
    except Exception:
        return MarketCand(prior)


# ------------------------------------------------------------------------------- diagnóstico (tramposo, NO es candidato)
class _Co2TruthLeads(MarketCand):
    """Previsor TRAMPOSO para medir dónde está el hueco: la v14, pero con el CO2 REAL en las antelaciones
    lo <= k <= hi (el resto, previsto). Solo para diagnóstico en el banco; nunca se empaqueta."""

    def __init__(self, prior, truth: dict, lo: int, hi: int):
        super().__init__(prior)
        self.truth, self.lo, self.hi = truth, lo, hi

    def forecast(self, obs, times, weather=None):
        price, co2 = super().forecast(obs, times, weather)
        for k in range(self.lo, min(self.hi + 1, len(times))):
            v = self.truth.get(times[k])
            if v is not None:
                co2[k] = v
        return price, co2


def _truth_factory(lo: int, hi: int):
    def fac(exclude, prior):
        import p1_hard as B
        m = B.market_frame()
        return _Co2TruthLeads(prior, {t: float(c) for t, c in zip(m.index, m.co2)}, lo, hi)
    return fac


diag_real_3_5 = _truth_factory(3, 5)        # CO2 real hasta 5 h (6 horas conocidas en vez de 3)
diag_real_3_8 = _truth_factory(3, 8)
diag_real_3_11 = _truth_factory(3, 11)
diag_real_12_23 = _truth_factory(12, 23)    # CO2 real solo de 12 a 23 h
diag_real_3_23 = _truth_factory(3, 23)      # CO2 real en todo el horizonte (el techo del CO2)


# ------------------------------------------------------------------------------- regresión de día y de noche
# La desviación del CO2 que viene del sol se apaga de noche y la que viene del viento no: cuánto dura una desviación
# depende de si la hora OBJETIVO tiene sol. La regresión común por antelación no lo distingue; la de "una por hora
# del día" (24 grupos, ya descartada) sí, pero con 160 filas por grupo mete ruido. Aquí son DOS grupos por
# antelación: horas objetivo con sol todo el año (10 a 17 h) y el resto. La inferencia es MarketCand tal cual
# (ya admite una tabla [21][24][F+1] por hora objetivo): solo cambia la tabla del CO2.
SOLAR_HOURS = (10, 11, 12, 13, 14, 15, 16, 17)


def fit_day_night(exclude, prior, groups=(SOLAR_HOURS,)) -> list:
    """Tabla [21][24][F+1] del CO2: una regresión por antelación y grupo de horas objetivo."""
    import hard_market_cand as L
    feats = tuple(prior["cand"]["feats"])
    rows = L.training_rows(L.dense_market(exclude), feats, False, True, True)["co2"]
    group_of = np.zeros(24, dtype=int)
    for g, hours in enumerate(groups):
        group_of[list(hours)] = g + 1
    table = []
    for X, _, y, hour in rows:
        ok = np.isfinite(X).all(axis=1)
        A = np.c_[X[ok], np.ones(int(ok.sum()))]
        yy, gg = y[ok], group_of[hour[ok]]
        nf = A.shape[1]
        common = np.linalg.solve(A.T @ A + 1e-6 * np.eye(nf), A.T @ yy)
        by_hour = np.tile(common, (24, 1))
        for g in range(len(groups) + 1):
            sel = gg == g
            if sel.sum() >= 20 * nf:
                Ag = A[sel]
                by_hour[group_of == g] = np.linalg.solve(Ag.T @ Ag + 1e-6 * np.eye(nf), Ag.T @ yy[sel])
        table.append(by_hour.tolist())
    return table


def make_dn(exclude, prior):
    """La v14 con dos regresiones del CO2 por antelación: horas objetivo con sol (10-17 h) y el resto."""
    try:
        cand = dict(prior["cand"])
        cand["full"] = {"price": prior["cand"]["full"]["price"], "co2": fit_day_night(exclude, prior)}
        return MarketCand({**prior, "cand": cand})
    except Exception:
        return MarketCand(prior)


only_d24 = make_only("knn", delta=True)
only_d12 = make_only("knn", delta=True, ctx_h=12)
only_d6 = make_only("knn", delta=True, ctx_h=6)
