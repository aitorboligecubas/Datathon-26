"""Laboratorio del encargo "estructura" (previsión del CO2, HARD MODE). No se empaqueta.

    python scripts/p1_lab/hard_co2_estructura_lab.py error                      # error de previsión por antelación y tramo
    python scripts/p1_lab/hard_co2_estructura_lab.py banco dev A_mem,B_pk       # score del banco de varias variantes en una ventana

Las dos cosas ajustan SIN las horas de la ventana. La ventana val está reservada: no se ejecuta aquí.
"""
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
for _p in (str(REPO / "src"), str(REPO / "scripts"), str(REPO / "scripts" / "p1_lab")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hard_co2_estructura_cand as C  # noqa: E402
import p1_hard as B  # noqa: E402
from battery.hard_market import KNOWN_HOURS, LEADS  # noqa: E402
from hard_market_cand import at  # noqa: E402

WINDOWS = {"dev": (8, 14), "1-7": (1, 7), "3-9": (3, 9), "12-18": (12, 18), "15-21": (15, 21)}
LEAD_GROUPS = ((3, 5), (6, 11), (12, 17), (18, 23))
BLOCK_NAMES = ("noche", "mañana", "mediodía", "tarde")


def error_table(keys) -> None:
    """Error de la desviación prevista del CO2 (raíz del error cuadrático medio de z, en %), fuera de muestra:
    se ajusta sin la ventana y se mide en ella, con la historia real (como en el banco)."""
    m = B.market_frame()
    se = {key: np.zeros((len(LEAD_GROUPS), 4)) for key in ["v14"] + list(keys)}
    cnt = np.zeros((len(LEAD_GROUPS), 4))
    per_win = {key: [] for key in se}
    lev = {key: np.zeros(len(LEAD_GROUPS)) for key in se}      # error en nivel (kg/kWh), que es lo que ve el plan
    lev_n, lev_sum = np.zeros(len(LEAD_GROUPS)), np.zeros(len(LEAD_GROUPS))
    for wname, (a, b) in WINDOWS.items():
        in_win_idx = m.index[(m.index.day >= a) & (m.index.day <= b)]
        exclude = set(in_win_idx)
        prior = B.fit_market(exclude, None)
        tabs = {key: C.fit_co2x(exclude, prior, C.VARIANTS[key]) for key in keys}
        if "base" in tabs:      # comprobación: la variante "base" tiene que ser la regresión de la v14
            dif = np.abs(np.asarray(tabs["base"]["coef"]) - np.asarray(prior["cand"]["full"]["co2"])).max()
            print(f"{wname}: diferencia máxima de coeficientes base frente a la v14 = {dif:.2e}")
        idx, hr, ym, z = C.z_series(prior, None)
        inw = (idx.day >= a) & (idx.day <= b)
        fx = C.fixed_features(z, hr)
        v14 = np.asarray(prior["cand"]["full"]["co2"], dtype=float)
        tot = {key: 0.0 for key in se}
        n_tot = 0
        for k in range(KNOWN_HOURS, KNOWN_HOURS + LEADS):
            f = C.lead_features(fx, z, k, prior, hr)
            y = at(z["co2"], k)
            Xb = np.vstack([f[n] for n in C.X_BASE]).T
            pb = Xb @ v14[k - KNOWN_HOURS][:-1] + v14[k - KNOWN_HOURS][-1]
            rows = inw & (at(inw.astype(float), k) == 1.0) & (at(ym.astype(float), k) == ym) & np.isfinite(y) & np.isfinite(pb)
            ht = (hr + k) % 24
            blk = C.BLOCK_OF_HOUR[ht]
            g = [j for j, (lo, hi) in enumerate(LEAD_GROUPS) if lo <= k <= hi][0]
            preds = {"v14": pb}
            for key in keys:
                t = tabs[key]
                coef = np.asarray(t["coef"][k - KNOWN_HOURS], dtype=float)
                X = np.vstack([f[n] for n in t["feats"]]).T
                cc = coef[ht] if coef.ndim == 2 else np.tile(coef, (len(X), 1))
                p = (X * cc[:, :-1]).sum(axis=1) + cc[:, -1]
                preds[key] = np.where(np.isfinite(p), p, pb)
            pt = at(z["prof_co2"], k)
            real = pt[rows] * np.exp(y[rows])
            lev_n[g] += rows.sum()
            lev_sum[g] += real.sum()
            for key, p in preds.items():
                lev[key][g] += float(((pt[rows] * np.exp(p[rows]) - real) ** 2).sum())
            for bi in range(4):
                sel = rows & (blk == bi)
                cnt[g, bi] += sel.sum()
                for key, p in preds.items():
                    e2 = float(((p[sel] - y[sel]) ** 2).sum())
                    se[key][g, bi] += e2
                    tot[key] += e2
            n_tot += int(rows.sum())
        for key in se:
            per_win[key].append(100 * np.sqrt(tot[key] / max(n_tot, 1)))
    print("\nError de z del CO2 (%), por antelación (filas) y total; todas las ventanas de diseño juntas")
    head = "variante".ljust(12) + "".join(f"{lo}-{hi} h".rjust(9) for lo, hi in LEAD_GROUPS) + "   total |" + "".join(n.rjust(10) for n in BLOCK_NAMES) + " | por ventana (" + ", ".join(WINDOWS) + ")"
    print(head)
    for key in se:
        by_lead = 100 * np.sqrt(se[key].sum(axis=1) / cnt.sum(axis=1))
        by_blk = 100 * np.sqrt(se[key].sum(axis=0) / cnt.sum(axis=0))
        total = 100 * np.sqrt(se[key].sum() / cnt.sum())
        print(key.ljust(12) + "".join(f"{v:9.2f}" for v in by_lead) + f"{total:8.2f} |" + "".join(f"{v:10.2f}" for v in by_blk)
              + " | " + " ".join(f"{v:6.2f}" for v in per_win[key]))
    print("\nError en NIVEL (raíz del error cuadrático medio en kg/kWh, en % del CO2 medio), por antelación y total")
    for key in se:
        by_lead = 100 * np.sqrt(lev[key] / lev_n) / (lev_sum / lev_n)
        total = 100 * np.sqrt(lev[key].sum() / lev_n.sum()) / (lev_sum.sum() / lev_n.sum())
        print(key.ljust(12) + "".join(f"{v:9.2f}" for v in by_lead) + f"{total:8.2f}")
    print("\nv14: error por antelación (filas) y tramo de la hora objetivo (columnas)")
    e = 100 * np.sqrt(se["v14"] / np.maximum(cnt, 1))
    for g, (lo, hi) in enumerate(LEAD_GROUPS):
        print(f"{lo}-{hi} h".ljust(12) + "".join(f"{v:10.2f}" for v in e[g]))


def bound_table() -> None:
    """Cota de la familia lineal: la regresión ajustada EN la propia ventana (trampa: ve lo que va a prever), con
    todas las pistas, común y por tramos. Y el sesgo y el error de la v14 por tipo de día de la hora objetivo."""
    from battery.hard_market import market_day_type
    m = B.market_frame()
    all_feats = C.X_BASE + ("pk", "zym3n", "zm72n")
    acc = {name: np.zeros(len(LEAD_GROUPS)) for name in ("v14", "trampa común 13", "trampa común 16", "trampa por tramos 16")}
    n = np.zeros(len(LEAD_GROUPS))
    typ_sum, typ_cnt, typ_sq, typ_n = np.zeros((5, 3)), np.zeros((5, 3)), np.zeros(3), np.zeros(3)
    for wi, (wname, (a, b)) in enumerate(WINDOWS.items()):
        exclude = set(m.index[(m.index.day >= a) & (m.index.day <= b)])
        prior = B.fit_market(exclude, None)
        idx, hr, ym, z = C.z_series(prior, None)
        inw = (idx.day >= a) & (idx.day <= b)
        typ = np.array([market_day_type(t) for t in idx])
        fx = C.fixed_features(z, hr)
        v14 = np.asarray(prior["cand"]["full"]["co2"], dtype=float)
        for k in range(KNOWN_HOURS, KNOWN_HOURS + LEADS):
            f = C.lead_features(fx, z, k, prior, hr)
            y = at(z["co2"], k)
            Xb = np.vstack([f[nm] for nm in C.X_BASE]).T
            Xa = np.vstack([f[nm] for nm in all_feats]).T
            pb = Xb @ v14[k - KNOWN_HOURS][:-1] + v14[k - KNOWN_HOURS][-1]
            rows = (inw & (at(inw.astype(float), k) == 1.0) & (at(ym.astype(float), k) == ym) & np.isfinite(y)
                    & np.isfinite(pb) & np.isfinite(Xa).all(axis=1))
            g = [j for j, (lo, hi) in enumerate(LEAD_GROUPS) if lo <= k <= hi][0]
            ht = ((hr + k) % 24)[rows]
            yy = y[rows]
            n[g] += rows.sum()
            acc["v14"][g] += float(((pb[rows] - yy) ** 2).sum())
            for name, X, cfg in (("trampa común 13", Xb[rows], {}), ("trampa común 16", Xa[rows], {}),
                                 ("trampa por tramos 16", Xa[rows], {"blocks": True})):
                coef = np.asarray(C.fit_rows(X, yy, ht, cfg), dtype=float)
                cc = coef[ht] if coef.ndim == 2 else np.tile(coef, (len(X), 1))
                acc[name][g] += float((((X * cc[:, :-1]).sum(axis=1) + cc[:, -1] - yy) ** 2).sum())
            tt = at(typ.astype(float), k)[rows].astype(int)
            res = pb[rows] - yy
            for t in range(3):
                typ_sum[wi, t] += res[tt == t].sum()
                typ_cnt[wi, t] += (tt == t).sum()
            np.add.at(typ_sq, tt, res ** 2)
            np.add.at(typ_n, tt, 1)
        typ_sum[wi] /= np.maximum(typ_cnt[wi], 1)
    print("Cota de la familia lineal (error de z del CO2 en %, por antelación y total)")
    for name, v in acc.items():
        print(name.ljust(24) + "".join(f"{x:9.2f}" for x in 100 * np.sqrt(v / n)) + f"{100 * np.sqrt(v.sum() / n.sum()):8.2f}")
    print("v14: error por tipo de día de la hora objetivo (laborable, sábado, domingo/festivo): "
          + " ".join(f"{x:.2f}" for x in 100 * np.sqrt(typ_sq / np.maximum(typ_n, 1))))
    print("v14: sesgo medio aproximado (previsto - real, %) por ventana y tipo de día:")
    for wi, wname in enumerate(WINDOWS):
        print("   " + wname.ljust(8) + " ".join(f"{100 * x:7.2f}" for x in typ_sum[wi]))


def bench(split: str, keys) -> None:
    """Score del banco (misma receta que p1_hard.evaluate) de la v14 y de varias variantes en una ventana."""
    full = B.hard_table()
    df = B.split_frame(full, split)
    exclude = set(df.timestamp)
    fit_df = full[~full.timestamp.isin(exclude)]
    prior = B.fit_market(exclude, fit_df)
    solar_prior = B.fit_solar(fit_df)
    base = B.baseline_totals(df)
    out = REPO / "results" / "p1_hard" / "co2_estructura_banco.csv"

    def sim(name, market=None):
        ag = B.hard_agent(prior, solar_prior)
        if market is not None:
            ag.policy.market = market
        totals, _ = B.simulate_hard(ag, df)
        sc = B.score(totals, base)
        line = f"{split},{name},{sc['score_raw']:.4f},{sc['infractions']},{1000 * totals['runtime_s'] / len(df):.2f}"
        print(line, flush=True)
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(line + f",{time.strftime('%H:%M:%S')}\n")
        return sc["score_raw"]

    s0 = sim("v14")
    for key in keys:
        s = sim(key, C.build(key, exclude, prior))
        print(f"   {split} {key}: {s - s0:+.4f}", flush=True)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "error":
        error_table(sys.argv[2].split(",") if len(sys.argv) > 2 else [k for k in C.VARIANTS])
    elif mode == "cota":
        bound_table()
    elif mode == "banco":
        if sys.argv[2] == "val":
            raise SystemExit("la ventana val está reservada")
        bench(sys.argv[2], sys.argv[3].split(","))
