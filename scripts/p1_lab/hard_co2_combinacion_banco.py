"""Laboratorio del encargo "combinacion" (CO2 del HARD MODE). NO se empaqueta.

    python scripts/p1_lab/hard_co2_combinacion_banco.py diag dev          # error de cada previsor, correlación y calibración
    python scripts/p1_lab/hard_co2_combinacion_banco.py score dev make,make_all4   # score del banco (mismas funciones que p1_hard.evaluate)

El modo "score" hace lo mismo que `python scripts/p1_hard.py --split S --market ...:make`, pero con un solo
ajuste para varios candidatos (ahorra tiempo). La cifra final de cada candidato se confirma con el banco oficial.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
for _p in (str(REPO / "src"), str(REPO / "scripts"), str(REPO / "scripts" / "p1_lab")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import p1_hard as B  # noqa: E402
import hard_co2_combinacion_cand as C  # noqa: E402

GROUPS = (("3-5", 3, 5), ("6-11", 6, 11), ("12-17", 12, 17), ("18-23", 18, 23))
ONE_H = pd.Timedelta(hours=1)


def walk(fc, df: pd.DataFrame, truth: dict) -> pd.DataFrame:
    """Pasa el previsor por las horas de `df` como en el test y devuelve una fila por (hora, antelación):
    lo previsto, lo real y el perfil del CO2."""
    rows = []
    for ts in df.timestamp:
        known = [truth.get(ts + j * ONE_H) for j in range(3)]
        if any(v is None for v in known):
            continue
        obs = SimpleNamespace(price=np.array([v[0] for v in known]), co2=np.array([v[1] for v in known]))
        times = [ts + k * ONE_H for k in range(24)]
        _, co2 = fc.forecast(obs, times, None)
        for k in range(3, 24):
            t = times[k]
            real = truth.get(t)
            if real is None or t.month != ts.month or t not in INSIDE:
                continue
            rows.append((ts, k, float(co2[k]), real[1], fc.profile("co2", t)))
    return pd.DataFrame(rows, columns=["ts", "k", "pred", "real", "prof"])


INSIDE = set()


def diag(split: str) -> None:
    full = B.hard_table()
    df = B.split_frame(full, split)
    exclude = set(df.timestamp)
    INSIDE.clear()
    INSIDE.update(exclude)
    prior = B.fit_market(exclude, None)
    truth = {t: (p, c) for t, p, c in zip(full.timestamp, full.price_eur_kwh, full.co2_kg_kwh) if np.isfinite(p) and np.isfinite(c)}
    members = {"reg (v14)": C.make_only("reg"), "knn": C.make_only("knn"), "knn+precio": C.make_only("knn", ctx_price=True),
               "knn delta": C.make_only("knn", delta=True), "nivel 24 h": C.make_only("lvl"), "ayer": C.make_only("yday"),
               "reg+knn": C.make, "reg+knn+precio": C.make_knnp, "reg+knn delta": C.make_delta, "media de 4": C.make_all4,
               "2/3 reg + 1/3 knn": C.make_third}
    out = {}
    for name, fac in members.items():
        out[name] = walk(fac(exclude, prior), df, truth)
    base = out["reg (v14)"]
    print(f"== {split}: {len(base)} previsiones (hora, antelación)")
    print("Error del CO2 (RMSE del logaritmo, en %) por antelación")
    tab = {}
    for name, d in out.items():
        e = np.log(d.pred / d.real)
        tab[name] = {g: 100 * float(np.sqrt((e[(d.k >= a) & (d.k <= b)] ** 2).mean())) for g, a, b in GROUPS}
        tab[name]["todas"] = 100 * float(np.sqrt((e ** 2).mean()))
    print(pd.DataFrame(tab).T.round(2).to_string())
    solo = ["reg (v14)", "knn", "knn+precio", "knn delta", "nivel 24 h", "ayer"]
    errs = pd.DataFrame({name: np.log(out[name].pred / out[name].real).to_numpy() for name in solo})
    sel = (base.k >= 6).to_numpy()
    print("Correlación de los errores (antelaciones 6-23)")
    print(errs[sel].corr().round(2).to_string())
    print("Calibración: pendiente de z real frente a z previsto (1 = en su punto; < 1 = se pasa de confiada)")
    cal = {}
    for name in ("reg (v14)", "knn", "reg+knn"):
        d = out[name]
        zp, zr = np.log(d.pred / d.prof), np.log(d.real / d.prof)
        cal[name] = {}
        for g, a, b in GROUPS:
            s = ((d.k >= a) & (d.k <= b)).to_numpy()
            cal[name][g] = float(np.cov(zr[s], zp[s])[0, 1] / np.var(zp[s], ddof=1))
    print(pd.DataFrame(cal).T.round(3).to_string())


def diag2(split: str, names: list) -> None:
    """Error del CO2 por antelación (con detalle en las cortas, que son las que dan score) de las fábricas dadas."""
    full = B.hard_table()
    df = B.split_frame(full, split)
    exclude = set(df.timestamp)
    INSIDE.clear()
    INSIDE.update(exclude)
    prior = B.fit_market(exclude, None)
    truth = {t: (p, c) for t, p, c in zip(full.timestamp, full.price_eur_kwh, full.co2_kg_kwh) if np.isfinite(p) and np.isfinite(c)}
    groups = (("3", 3, 3), ("4", 4, 4), ("5", 5, 5), ("6-8", 6, 8), ("9-11", 9, 11), ("12-23", 12, 23))
    tab = {}
    for name in ["v14"] + names:
        fc = B.MarketCand(prior) if name == "v14" else getattr(C, name)(exclude, prior)
        d = walk(fc, df, truth)
        e = np.log(d.pred / d.real)
        ea = d.pred - d.real
        tab[name] = {g: 100 * float(np.sqrt((e[(d.k >= a) & (d.k <= b)] ** 2).mean())) for g, a, b in groups}
        s35 = (d.k >= 3) & (d.k <= 5)
        tab[name]["abs 3-5 (g/kWh)"] = 1000 * float(np.sqrt((ea[s35] ** 2).mean()))
    print(f"DIAG2 {split}: RMSE del logaritmo (%) por antelación, y error absoluto a 3-5 h")
    print(pd.DataFrame(tab).T.round(2).to_string(), flush=True)


def score(split: str, names: list) -> None:
    full = B.hard_table()
    df = B.split_frame(full, split)
    exclude = set(df.timestamp)
    fit_df = full[~full.timestamp.isin(exclude)]
    prior = B.fit_market(exclude, fit_df)
    solar_prior = B.fit_solar(fit_df)
    base = B.baseline_totals(df)
    res = {}
    for name in ["agente actual"] + names:
        a = B.hard_agent(prior, solar_prior)
        if name != "agente actual":
            a.policy.market = getattr(C, name)(exclude, prior)
        totals, _ = B.simulate_hard(a, df)
        sc = B.score(totals, base)
        res[name] = sc["score_raw"]
        print(f"SCORE {split} | {name} | {sc['score_raw']:.3f} | dif {sc['score_raw'] - res['agente actual']:+.3f} | "
              f"infr {sc['infractions']} | ms/paso {1000 * totals['runtime_s'] / len(df):.2f}", flush=True)


if __name__ == "__main__":
    mode, split = sys.argv[1], sys.argv[2]
    if mode == "diag":
        diag(split)
    elif mode == "diag2":
        diag2(split, sys.argv[3].split(","))
    else:
        score(split, sys.argv[3].split(","))
