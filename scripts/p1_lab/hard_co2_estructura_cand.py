"""Candidato "estructura" para la previsión del CO2 en el HARD MODE (laboratorio de P1, domingo 15/11).

Uso con el banco:
    python scripts/p1_hard.py --split dev --only "agente actual,CANDIDATO" --market scripts/p1_lab/hard_co2_estructura_cand.py:make

Qué cambia frente a battery.hard_market.MarketCand (la v14): SOLO la regresión del CO2. El precio, los perfiles,
la memoria del train y todos los caminos de respaldo son los de la v14. La regresión del CO2 sigue siendo lineal y
por antelación (3 a 23 h), con pistas nuevas que tienen una razón física:
    zym3   media de la desviación a la hora objetivo en los 3 últimos días (la solar de la red se repite de día en día)
    zy3    la desviación a la hora objetivo hace 3 días
    zm72   nivel medio de las últimas 72 h (los regímenes de viento duran varios días)
    zm168  nivel medio de los últimos 7 días
    pk     la desviación del PRECIO que prevé la v14 para la hora objetivo (el precio se prevé mejor y baja con la
           renovable, igual que el CO2)
    zn/zs  nivel de las últimas 24 h solo en horas de noche (viento) / solo en horas de sol (solar)
y, opcionalmente, una regresión por tramo de la hora OBJETIVO (noche, mañana, mediodía, tarde).
Si falta alguna pista nueva, esa hora se prevé exactamente como la v14.

La clase Co2Estructura solo usa numpy, pandas y math (se puede empaquetar). El ajuste es del laboratorio.

RESULTADO (domingo 15/11, 08:16): NINGUNA variante cumple el criterio (ganar a la v14 en 4 de las 5 ventanas de
diseño, media >= +0,03 y ninguna peor que -0,02). La mejor media es +0,014 (W_pk) y la que mejor se defiende por
razones (B_pk, la que devuelve `make`) da +0,007 con 2 ventanas de 5. No integrar. Números:
results/p1_hard/co2_estructura_banco.csv (banco), co2_estructura_error.txt (error de previsión y cota de la familia
lineal) y co2_estructura_oficial_*.csv (banco oficial con B_pk).
"""
import math
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
for _p in (str(REPO / "src"), str(REPO / "scripts"), str(REPO / "scripts" / "p1_lab")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from battery.hard_market import KNOWN_HOURS, LEADS, Z_CLIP, MarketCand, window_mean  # noqa: E402

X_BASE = ("z0", "z1", "z2", "zm24", "zm6", "zy", "zyL", "zy2", "zd", "zyd", "o2", "om24", "oy")
X_EXTRA = ("zy3", "zym3", "zm72", "zm168", "pk", "zn", "zs", "zs_sun", "zn_night", "zym3n", "zm72n")
# Tramos de la hora objetivo: 0 = noche (22-6 h, manda el viento), 1 = mañana (7-10 h, rampa), 2 = mediodía
# (11-16 h, manda la solar de la red), 3 = tarde (17-21 h, rampa y punta).
BLOCK_OF_HOUR = np.array([0] * 7 + [1] * 4 + [2] * 6 + [3] * 5 + [0] * 2, dtype=int)
NIGHT_MASK = BLOCK_OF_HOUR == 0
SUN_MASK = BLOCK_OF_HOUR == 2


def masked_mean(w: np.ndarray, mask: np.ndarray, min_count: int) -> float:
    """Media de w[mask] sin contar huecos (NaN con menos de `min_count` valores)."""
    v = w[mask]
    ok = np.isfinite(v)
    n = int(ok.sum())
    return float(v[ok].sum() / n) if n >= min_count and n > 0 else float("nan")


class Co2Estructura(MarketCand):
    """La v14 con otra regresión para el CO2. prior["co2x"] = {"feats": [F nombres], "coef": [21][F+1] o
    [21][24][F+1] (por hora objetivo)}. Si falta o falla algo, decide como la v14."""

    def __init__(self, prior: Optional[dict] = None, **kwargs):
        super().__init__(prior, **kwargs)
        self.x_ok = False
        self.x_feats, self.x_coef, self.x_price = (), None, None
        try:
            c = prior["co2x"]
            self.x_feats = tuple(c["feats"])
            coef = np.asarray(c["coef"], dtype=float)
            if coef.ndim == 2:
                coef = np.repeat(coef[:, None, :], 24, axis=1)
            if coef.shape != (LEADS, 24, len(self.x_feats) + 1) or not np.isfinite(coef).all():
                raise ValueError("tablas con otra forma o con huecos")
            if not all(f in X_BASE or f in X_EXTRA for f in self.x_feats):
                raise ValueError("pista desconocida")
            self.x_coef = coef
            self.x_ok = bool(self.cand_ok)
        except Exception:
            self.x_ok = False

    def predict(self, name: str, other: str, sc: dict, i: int, ks: np.ndarray, hours: np.ndarray) -> np.ndarray:
        base = super().predict(name, other, sc, i, ks, hours)
        if not self.x_ok:
            return base
        if name == "price":
            self.x_price = (i, np.array(ks), np.array(base))      # la previsión del precio es una pista del CO2
            return base
        try:
            zhat = self.co2_structured(sc, i, ks, hours)
            return np.where(np.isfinite(zhat), np.clip(zhat, -Z_CLIP, Z_CLIP), base)
        except Exception:
            return base

    def co2_structured(self, sc: dict, i: int, ks: np.ndarray, hours: np.ndarray) -> np.ndarray:
        own, oth = sc["co2"], sc["price"]
        z, zo = self.z["co2"], self.z["price"]
        need = self.x_feats
        vals = {"z0": own["0"], "z1": own["1"], "z2": own["2"], "zm24": own["m24"], "zm6": own["m6"],
                "zyL": own["yL"], "zd": own["d"], "zyd": own["yd"], "zy": z[i + ks - 24], "zy2": z[i + ks - 48],
                "o2": oth["2"], "om24": oth["m24"], "oy": zo[i + ks - 24]}
        if "zy3" in need:
            vals["zy3"] = z[i + ks - 72]
        if "zym3" in need:
            vals["zym3"] = (z[i + ks - 24] + z[i + ks - 48] + z[i + ks - 72]) / 3.0
        if "zm72" in need:
            vals["zm72"] = window_mean(z, i - 71, i + 1, 36)
        if "zm168" in need:
            vals["zm168"] = window_mean(z, i - 167, i + 1, 84)
        if "zym3n" in need:        # media de los días que haya (ayer tiene que estar)
            stack3 = np.vstack([z[i + ks - 24], z[i + ks - 48], z[i + ks - 72]])
            fin = np.isfinite(stack3)
            vals["zym3n"] = np.where(fin[0], np.where(fin, stack3, 0.0).sum(axis=0) / np.maximum(fin.sum(axis=0), 1), np.nan)
        if "zm72n" in need:
            vals["zm72n"] = window_mean(z, i - 71, i + 1, 12)
        if "pk" in need:
            pi, pks, pz = self.x_price
            if pi != i or len(pks) != len(ks) or not (pks == ks).all():
                raise ValueError("la previsión del precio no es de esta hora")
            vals["pk"] = pz
        if "zn" in need or "zs" in need:
            hour_now = int((int(hours[0]) - int(ks[0])) % 24)
            w = z[i - 23:i + 1]
            hh = (hour_now - 23 + np.arange(24)) % 24
            vals["zn"] = masked_mean(w, NIGHT_MASK[hh], 3)
            vals["zs"] = masked_mean(w, SUN_MASK[hh], 3)
        if "zs_sun" in need or "zn_night" in need:
            hour_now = int((int(hours[0]) - int(ks[0])) % 24)
            w = z[i - 23:i + 1]
            hh = (hour_now - 23 + np.arange(24)) % 24
            vals["zs_sun"] = np.where(SUN_MASK[hours], masked_mean(w, SUN_MASK[hh], 3), 0.0)
            vals["zn_night"] = np.where(NIGHT_MASK[hours], masked_mean(w, NIGHT_MASK[hh], 3), 0.0)
        X = np.empty((len(ks), len(need)))
        for j, f in enumerate(need):
            X[:, j] = vals[f]
        C = self.x_coef[ks - KNOWN_HOURS, hours]
        return (X * C[:, :-1]).sum(axis=1) + C[:, -1]


# ------------------------------------------------------------------------------- ajuste (laboratorio)
def z_series(prior: dict, exclude=None) -> tuple:
    """Desviaciones z = log(real / perfil) del train, una por hora del calendario, con el perfil de `prior`
    (interpolado entre meses igual que en el agente). NaN donde no hay dato o está excluido."""
    from hard_market_cand import day_types, dense_market
    from p1_hard import blend_lookup
    d = dense_market(exclude)
    idx = d.index
    mo, hr, day = idx.month.to_numpy() - 1, idx.hour.to_numpy(), idx.day.to_numpy(float)
    typ = day_types(idx)
    z = {}
    for name in ("price", "co2"):
        prof = blend_lookup(prior[name], mo, day, typ, hr, prior.get("day_center"))
        v = d[name].to_numpy(float)
        z[name] = np.clip(np.log(np.clip(v, 1e-6, None) / np.clip(prof, 1e-6, None)), -Z_CLIP, Z_CLIP)
        z["prof_" + name] = np.asarray(prof, dtype=float)
    ym = idx.year.to_numpy() * 12 + mo
    return idx, hr, ym, z


def fixed_features(z: dict, hr: np.ndarray) -> dict:
    """Pistas que no dependen de la antelación, para las dos variables."""
    from hard_market_cand import at, day_means, roll_mean
    out = {}
    for name, other in (("price", "co2"), ("co2", "price")):
        zz, zo = z[name], z[other]
        today, yday = day_means(zz, hr)
        out[name] = {"z0": zz, "z1": at(zz, 1), "z2": at(zz, 2), "zm24": roll_mean(zz, 24, 12),
                     "zm6": roll_mean(zz, 6, 3), "zyL": at(zz, -22), "o2": at(zo, 2), "om24": roll_mean(zo, 24, 12),
                     "zd": at(today, 2), "zyd": at(yday, 2)}
    zc = z["co2"]
    out["co2"]["zm72"] = roll_mean(zc, 72, 36)
    out["co2"]["zm72n"] = roll_mean(zc, 72, 12)
    out["co2"]["zm168"] = roll_mean(zc, 168, 84)
    out["co2"]["zn"] = roll_mean(np.where(NIGHT_MASK[hr], zc, np.nan), 24, 3)
    out["co2"]["zs"] = roll_mean(np.where(SUN_MASK[hr], zc, np.nan), 24, 3)
    return out


def lead_features(fx: dict, z: dict, k: int, prior: dict, hr: np.ndarray) -> dict:
    """Todas las pistas del CO2 para la antelación `k` (las de siempre y las nuevas)."""
    from hard_market_cand import at
    zc, zp = z["co2"], z["price"]
    f = dict(fx["co2"])
    f["zy"], f["zy2"], f["oy"] = at(zc, k - 24), at(zc, k - 48), at(zp, k - 24)
    f["zy3"] = at(zc, k - 72)
    f["zym3"] = (f["zy"] + f["zy2"] + f["zy3"]) / 3.0
    stack3 = np.vstack([f["zy"], f["zy2"], f["zy3"]])
    fin = np.isfinite(stack3)
    f["zym3n"] = np.where(fin[0], np.where(fin, stack3, 0.0).sum(axis=0) / np.maximum(fin.sum(axis=0), 1), np.nan)
    # la previsión del precio de la v14 para la hora objetivo (misma regresión que usa el agente)
    pf = dict(fx["price"])
    pf["zy"], pf["zy2"], pf["oy"] = at(zp, k - 24), at(zp, k - 48), at(zc, k - 24)
    pc = np.asarray(prior["cand"]["full"]["price"], dtype=float)
    if pc.ndim != 2:
        raise ValueError("la regresión del precio no es común por antelación")
    c = pc[k - KNOWN_HOURS]
    Xp = np.vstack([pf[n] for n in prior["cand"]["feats"]]).T
    f["pk"] = np.clip(Xp @ c[:-1] + c[-1], -Z_CLIP, Z_CLIP)
    ht = (hr + k) % 24
    f["zs_sun"] = np.where(SUN_MASK[ht], f["zs"], 0.0)
    f["zn_night"] = np.where(NIGHT_MASK[ht], f["zn"], 0.0)
    return f


def fit_rows(X: np.ndarray, y: np.ndarray, hour_t: np.ndarray, cfg: dict, w=None):
    """Mínimos cuadrados. Con cfg["blocks"], una regresión por tramo de la hora objetivo, encogida hacia la común
    con cfg["block_ridge"] (0 = sin encoger). Con pesos `w`, mínimos cuadrados ponderados. Devuelve [F+1] o [24][F+1]."""
    A = np.c_[X, np.ones(len(X))]
    if w is not None:
        sw = np.sqrt(w / w.mean())
        A, y = A * sw[:, None], y * sw
    nf = A.shape[1]
    if cfg.get("harm"):
        # Coeficientes que cambian SUAVEMENTE con la hora objetivo (primer armónico del día): b(h) = a + b*cos + c*sin.
        # Es la versión sin escalones de "una regresión por tramo". Se guarda como tabla por hora objetivo [24][F+1].
        ang = 2.0 * math.pi * np.asarray(hour_t, dtype=float) / 24.0
        sw = np.ones(len(A)) if w is None else np.sqrt(w / w.mean())
        co, si = np.cos(ang), np.sin(ang)
        base = np.c_[X, np.ones(len(X))]
        D = np.c_[base, base * co[:, None], base * si[:, None]] * sw[:, None]
        yy = y if w is not None else y * 1.0          # con pesos, `y` ya viene ponderada
        beta = np.linalg.solve(D.T @ D + 1e-6 * np.eye(3 * nf), D.T @ yy)
        hh = 2.0 * math.pi * np.arange(24) / 24.0
        return (beta[:nf][None, :] + np.cos(hh)[:, None] * beta[nf:2 * nf][None, :]
                + np.sin(hh)[:, None] * beta[2 * nf:][None, :]).tolist()
    common = np.linalg.solve(A.T @ A + 1e-6 * np.eye(nf), A.T @ y)
    if not cfg.get("blocks"):
        return common.tolist()
    lam = float(cfg.get("block_ridge", 0.0))
    out = np.tile(common, (24, 1))
    blk = BLOCK_OF_HOUR[hour_t]
    for b in range(4):
        sel = blk == b
        if sel.sum() >= 8 * nf:
            Ab, yb = A[sel], y[sel]
            cb = np.linalg.solve(Ab.T @ Ab + (lam + 1e-6) * np.eye(nf), Ab.T @ yb + lam * common)
            out[BLOCK_OF_HOUR == b] = cb
    return out.tolist()


def fit_co2x(exclude, prior: dict, cfg: dict) -> dict:
    """Tablas de la regresión del CO2 (clave "co2x"), ajustadas con el train sin las horas de `exclude`."""
    from hard_market_cand import at
    feats = tuple(cfg["feats"])
    idx, hr, ym, z = z_series(prior, exclude)
    fx = fixed_features(z, hr)
    coef, gram = [], []
    for k in range(KNOWN_HOURS, KNOWN_HOURS + LEADS):
        f = lead_features(fx, z, k, prior, hr)
        y = at(z["co2"], k)
        same = at(ym.astype(float), k) == ym
        X = np.vstack([f[n] for n in feats]).T
        ok = same & np.isfinite(y) & np.isfinite(X).all(axis=1)
        w = None
        if cfg.get("wls"):          # el error que cuenta es en kg/kWh, no en %: cada fila pesa (perfil de la hora objetivo)^2
            pt = at(z["prof_co2"], k)
            ok = ok & np.isfinite(pt)
            w = pt[ok] ** 2
        coef.append(fit_rows(X[ok], y[ok], ((hr + k) % 24)[ok], cfg, w))
        A = np.c_[X[ok], np.ones(int(ok.sum()))]
        gram.append((A.T @ A, A.T @ y[ok]))
    lam = float(cfg.get("lead_ridge", 0.0))
    if lam > 0 and not cfg.get("blocks") and not cfg.get("harm"):
        coef = joint_leads(gram, lam).tolist()
    return {"feats": list(feats), "coef": coef}


def joint_leads(gram: list, lam: float) -> np.ndarray:
    """Las 21 regresiones ajustadas a la vez, penalizando que los coeficientes de antelaciones vecinas difieran:
    min sum_k ||y_k - A_k b_k||^2 + lam * sum_k ||b_(k+1) - b_k||^2. Devuelve [21][F+1]."""
    n, nf = len(gram), gram[0][0].shape[0]
    M = np.zeros((n * nf, n * nf))
    r = np.zeros(n * nf)
    eye = np.eye(nf)
    for k, (G, g) in enumerate(gram):
        sl = slice(k * nf, (k + 1) * nf)
        deg = (1 if k > 0 else 0) + (1 if k < n - 1 else 0)
        M[sl, sl] = G + (lam * deg + 1e-6) * eye
        r[sl] = g
        if k > 0:
            M[sl, (k - 1) * nf:k * nf] = -lam * eye
        if k < n - 1:
            M[sl, (k + 1) * nf:(k + 2) * nf] = -lam * eye
    return np.linalg.solve(M, r).reshape(n, nf)


VARIANTS = {
    "base": {"feats": X_BASE},                                              # comprobación: tiene que dar la v14
    "A_mem": {"feats": X_BASE + ("zym3", "zm72")},                          # memoria más larga
    "B_pk": {"feats": X_BASE + ("pk",)},                                    # la previsión del precio como pista
    "C_blk": {"feats": X_BASE, "blocks": True},                             # una regresión por tramo de la hora objetivo
    "D_mem_pk": {"feats": X_BASE + ("zym3", "zm72", "pk")},                 # A + B
    "E_reg_blk": {"feats": X_BASE + ("zn", "zs"), "blocks": True},          # nivel de noche y de sol, por tramos
    "F_all_blk": {"feats": X_BASE + ("zym3", "zm72", "pk"), "blocks": True, "block_ridge": 30.0},
    "G_mem7": {"feats": X_BASE + ("zym3", "zm72", "zm168")},                # memoria de 7 días
    "H_few_blk": {"feats": ("z0", "z1", "z2", "zm24", "zy", "zym3", "zm72", "pk"), "blocks": True},   # pocas pistas por tramo
    "I_pk_blk": {"feats": X_BASE + ("pk",), "blocks": True, "block_ridge": 30.0},   # B por tramos, encogida hacia la común
    "J30": {"feats": X_BASE + ("pk",), "lead_ridge": 30.0},                 # B con antelaciones vecinas atadas
    "J300": {"feats": X_BASE + ("pk",), "lead_ridge": 300.0},
    "J3000": {"feats": X_BASE + ("pk",), "lead_ridge": 3000.0},
    "K300": {"feats": X_BASE, "lead_ridge": 300.0},                         # la v14 con antelaciones vecinas atadas
    "N_reg": {"feats": X_BASE + ("pk", "zs_sun", "zn_night")},              # nivel de sol / de noche solo para su tramo
    "N2_reg": {"feats": X_BASE + ("zs_sun", "zn_night")},
    "W_base": {"feats": X_BASE, "wls": True},                               # las pistas de la v14, ajuste ponderado por nivel
    "W_pk": {"feats": X_BASE + ("pk",), "wls": True},                       # B con ajuste ponderado por nivel
    "E0_reg": {"feats": X_BASE + ("zn", "zs")},                             # nivel de noche y de sol, regresión común
    "E0n": {"feats": X_BASE + ("zn",)},                                     # solo el nivel sin sol (viento)
    "E0n_pk": {"feats": X_BASE + ("zn", "pk")},
    "H1_base": {"feats": X_BASE, "harm": True},                             # coeficientes suaves en la hora objetivo
    "H1_pk": {"feats": X_BASE + ("pk",), "harm": True},
    "A2_mem": {"feats": X_BASE + ("zym3n", "zm72n")},                       # A sin perder filas: usa los días que haya
    "P_lvl": {"feats": X_BASE + ("zm72n",)},                                # solo el nivel de 72 h
    "Q_shape": {"feats": X_BASE + ("zym3n",)},                              # solo la media de 3 días a la hora objetivo
    "D2_mem_pk": {"feats": X_BASE + ("zym3n", "zm72n", "pk")},              # A2 + B
}
CHOSEN = "B_pk"      # la que mejor se defiende por razones; NO cumple el criterio (ver results/p1_hard/co2_estructura_banco.csv)


def build(key: str, exclude, prior: dict):
    """Previsor de la variante `key`. Si el ajuste falla, la v14 tal cual."""
    try:
        return Co2Estructura({**prior, "co2x": fit_co2x(exclude, prior, VARIANTS[key])})
    except Exception:
        return MarketCand(prior)


def make(exclude, prior):
    """Fábrica para el banco: scripts/p1_hard.py --market scripts/p1_lab/hard_co2_estructura_cand.py:make"""
    return build(CHOSEN, exclude, prior)


def make_A_mem(exclude, prior):
    return build("A_mem", exclude, prior)


def make_B_pk(exclude, prior):
    return build("B_pk", exclude, prior)


def make_C_blk(exclude, prior):
    return build("C_blk", exclude, prior)


def make_D_mem_pk(exclude, prior):
    return build("D_mem_pk", exclude, prior)


def make_G_mem7(exclude, prior):
    return build("G_mem7", exclude, prior)
