"""¿Prevé mejor el CO2 / precio futuro un modelo no lineal? (rama mejora-score-hard). NO se empaqueta.
Validación dejando un mes fuera: R2 de la desviación z = log(real/perfil) por antelación, regresión lineal actual
(13 pistas) frente a LightGBM con las mismas pistas + hora objetivo, antelación, mes y tipo de día."""
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
for extra in (str(REPO / "src"), str(REPO / "scripts"), str(REPO / "scripts" / "p1_lab")):
    sys.path.insert(0, extra)
import hard_market_cand as hc  # noqa: E402


def rows_with_meta(d, feats):
    """Filas de training_rows con mes y tipo de día de la hora objetivo (para el modelo no lineal)."""
    rows = hc.training_rows(d, feats, False)
    return rows


def main():
    import lightgbm as lgb
    feats = tuple(hc.DEFAULT_CFG["feats"])
    d = hc.dense_market(None)
    out = {}
    months = sorted(set(d.index.month))
    for name in ("co2", "price"):
        # filas por antelación, con el mes de la hora actual (aprox. el de la objetivo)
        res_lin, res_lgb, n_all = np.zeros(21), np.zeros(21), np.zeros(21)
        for mo_out in months:
            keep_tr = d.copy(); keep_tr.loc[keep_tr.index.month == mo_out] = np.nan
            keep_te = d.copy(); keep_te.loc[keep_te.index.month != mo_out] = np.nan
            tr = hc.training_rows(keep_tr, feats, False)[name]
            te = hc.training_rows(keep_te, feats, False)[name]
            Xtr_all, ytr_all, Xte_all, yte_all, ltr, lte = [], [], [], [], [], []
            for k in range(21):
                X, _, y, hr = tr[k]; Xt, _, yt, hrt = te[k]
                okt = np.isfinite(Xt).all(axis=1); ok = np.isfinite(X).all(axis=1)
                if ok.sum() < 50 or okt.sum() < 20:
                    continue
                A = np.c_[X[ok], np.ones(ok.sum())]
                coef = np.linalg.lstsq(A, y[ok], rcond=None)[0]
                pred = np.c_[Xt[okt], np.ones(okt.sum())] @ coef
                res_lin[k] += ((yt[okt] - pred) ** 2).sum()
                n_all[k] += ((yt[okt] - yt[okt].mean()) ** 2).sum()
                Xtr_all.append(np.c_[X[ok], hr[ok], np.full(ok.sum(), k)]); ytr_all.append(y[ok])
                Xte_all.append(np.c_[Xt[okt], hrt[okt], np.full(okt.sum(), k)]); yte_all.append(yt[okt]); lte.append(np.full(okt.sum(), k))
            m = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=50,
                                  subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1)
            m.fit(np.vstack(Xtr_all), np.concatenate(ytr_all))
            Xte, yte, lt = np.vstack(Xte_all), np.concatenate(yte_all), np.concatenate(lte)
            p = m.predict(Xte)
            for k in range(21):
                s = lt == k
                res_lgb[k] += ((yte[s] - p[s]) ** 2).sum()
        out[name] = (1 - res_lin / n_all, 1 - res_lgb / n_all)
        print(name, "R2 lineal / LightGBM por antelación (3, 6, 9, 12, 18, 23 h):")
        for k in (0, 3, 6, 9, 15, 20):
            print(f"   {k + 3:2d} h: {out[name][0][k]:.3f} / {out[name][1][k]:.3f}")


if __name__ == "__main__":
    main()
