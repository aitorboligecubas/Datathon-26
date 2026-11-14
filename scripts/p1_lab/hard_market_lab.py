"""Laboratorio del encargo "mercado": error de previsión del precio y del CO2 SIN pasar por el LP.

Recorre las semanas de dev como el banco (3 horas conocidas, 24 de plan) y compara la previsión con
lo real. Sirve para descartar variantes en segundos; la decisión final se toma con el score del banco.

    python scripts/p1_lab/hard_market_lab.py                 # variantes del candidato en dev
    python scripts/p1_lab/hard_market_lab.py --cv            # elegir el encogimiento por hora SOLO con el train
"""
import argparse
import sys
import time
from collections import namedtuple
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "scripts")); sys.path.insert(0, str(Path(__file__).resolve().parent))

import hard_market_cand as C  # noqa: E402
import p1_hard as B  # noqa: E402
from battery.hard import LAST_MONTHS, ONE_HOUR  # noqa: E402
from battery.hard_market import MarketForecaster  # noqa: E402
from battery.optimizer import score_weights  # noqa: E402

MiniObs = namedtuple("MiniObs", "price co2")


def horizon_times(ts, horizon=24):
    last = (ts.year, ts.month) in LAST_MONTHS
    times, t = [], ts
    for _ in range(horizon):
        times.append(t)
        nxt = t + ONE_HOUR
        if nxt.month != t.month:
            if last:
                break
            nxt = nxt + ONE_HOUR * (24 * (nxt.days_in_month - 7))
        t = nxt
    return times


def split_frame(full, split):
    """dev: días 8 a 14 (como el banco). dev0: días 1 a 7, otro tramo de diseño que no toca la validación
    (ahí no hay semilla: los días anteriores son del test, así que mide las demás piezas en frío)."""
    if split == "dev0":
        return full[full.timestamp.dt.day <= 7].reset_index(drop=True)
    if split.startswith("d") and split[1:].isdigit():      # dN: días N a N+6 (ventanas desplazadas, sin tocar la validación si N <= 8)
        n = int(split[1:])
        return full[(full.timestamp.dt.day >= n) & (full.timestamp.dt.day <= n + 6)].reset_index(drop=True)
    return B.split_frame(full, split)


def setup(split="dev"):
    full = B.hard_table()
    df = split_frame(full, split)
    exclude = set(df.timestamp)
    prior = B.fit_market(exclude, full[~full.timestamp.isin(exclude)])
    return df, exclude, prior


def run(fc, df, prior):
    """Devuelve una tabla con una fila por (hora, antelación >= 3): error del peso, primera jornada o no."""
    w_co2, w_cost = score_weights(prior["co2_ref_kg_per_h"], prior["cost_ref_eur_per_h"])
    m = B.market_frame()
    tp, tc = m.price.to_dict(), m.co2.to_dict()
    price = df.price_eur_kwh.to_numpy(float); co2 = df.co2_kg_kwh.to_numpy(float); ts = list(df.timestamp)
    n = len(df); rows = []; cap = []; t_fc = 0.0
    week_start = 0
    for t in range(n):
        if t > 0 and (ts[t] - ts[t - 1]) != ONE_HOUR:
            week_start = t
        times = horizon_times(ts[t])
        obs = MiniObs(price[t:t + 3], co2[t:t + 3])
        t0 = time.perf_counter()
        p, c = fc.forecast(obs, times, None)
        t_fc += time.perf_counter() - t0
        month = ts[t].month
        w_hat = w_co2 * c + w_cost * p
        w_true = np.array([w_co2 * tc.get(x, np.nan) + w_cost * tp.get(x, np.nan) if x.month == month else np.nan for x in times])
        for k in range(3, len(times)):
            if np.isfinite(w_true[k]):
                rows.append((t - week_start, k, w_hat[k] - w_true[k], w_true[k]))
        if len(times) == 24 and np.isfinite(w_true).all():
            o = np.argsort(w_hat, kind="stable"); ot = np.argsort(w_true, kind="stable")
            cap.append((t - week_start, w_true[o[-4:]].mean() - w_true[o[:4]].mean(), w_true[ot[-4:]].mean() - w_true[ot[:4]].mean()))
    r = pd.DataFrame(rows, columns=["h_week", "lead", "err", "true"]); cp = pd.DataFrame(cap, columns=["h_week", "got", "best"])
    r["err"] = 100 * r.err / r.true.mean()          # error del peso, en % del peso medio
    first = r.h_week < 24; cf = cp.h_week < 24
    return {"rmse": float(np.sqrt((r.err ** 2).mean())), "rmse_d1": float(np.sqrt((r.err[first] ** 2).mean())),
            "rmse_resto": float(np.sqrt((r.err[~first] ** 2).mean())), "rmse_3_8": float(np.sqrt((r.err[r.lead <= 8] ** 2).mean())),
            "rmse_9_23": float(np.sqrt((r.err[r.lead > 8] ** 2).mean())), "sesgo": float(r.err.mean()),
            "tramo": float(cp.got.sum() / cp.best.sum()), "tramo_d1": float(cp.got[cf].sum() / cp.best[cf].sum()),
            "ms": 1000 * t_fc / n}


def variants(exclude, prior):
    def cand(**cfg):
        return lambda: C.MarketCand({**prior, "cand": C.fit_cand(exclude, cfg)})
    base6 = ("z0", "z1", "z2", "zm24", "zm6", "zy")
    cross = ("o2", "om24", "oy")
    v = {"agente actual": lambda: MarketForecaster(prior),
         "A mismas pistas, sin semilla": cand(feats=base6, ridge_hour=-1, seed_hours=0),
         "B + semilla": cand(feats=base6, ridge_hour=-1),
         "M1 B + por hora": cand(feats=base6),
         "M2 B + zyL": cand(feats=base6 + ("zyL",), ridge_hour=-1),
         "M3 B + otra variable": cand(feats=base6 + cross, ridge_hour=-1),
         "M4 B + zy2": cand(feats=base6 + ("zy2",), ridge_hour=-1),
         "N todas, comun": cand(feats=C.FEATS, ridge_hour=-1),
         "G todas, por hora 30": cand(feats=C.FEATS),
         "G10": cand(feats=C.FEATS, ridge_hour=10.0),
         "G100": cand(feats=C.FEATS, ridge_hour=100.0),
         "G300": cand(feats=C.FEATS, ridge_hour=300.0),
         "J = G + sesgo log": cand(feats=C.FEATS, smear=True),
         "L = G + zy2": cand(feats=C.FEATS + ("zy2",)),
         "F = G con perfil cruzado": cand(feats=C.FEATS, crossfit=True),
         "G sin semilla": cand(feats=C.FEATS, seed_hours=0),
         "P = G + dia": cand(feats=C.FEATS + ("zd", "zyd")),
         "P10": cand(feats=C.FEATS + ("zd", "zyd"), ridge_hour=10.0),
         "P3": cand(feats=C.FEATS + ("zd", "zyd"), ridge_hour=3.0),
         "Q = base6 + dia, por hora": cand(feats=base6 + ("zd", "zyd")),
         "Q10": cand(feats=base6 + ("zd", "zyd"), ridge_hour=10.0),
         "R = P + zy2": cand(feats=C.FEATS + ("zd", "zyd", "zy2")),
         "S = P comun": cand(feats=C.FEATS + ("zd", "zyd"), ridge_hour=-1),
         "T = base6 + dia, comun": cand(feats=base6 + ("zd", "zyd"), ridge_hour=-1),
         "U = S + zy2": cand(feats=C.FEATS + ("zd", "zyd", "zy2"), ridge_hour=-1),
         "W = S + sesgo log": cand(feats=C.FEATS + ("zd", "zyd"), ridge_hour=-1, smear=True),
         "X = S sin otra variable": cand(feats=base6 + ("zyL", "zd", "zyd"), ridge_hour=-1),
         "Y = S sin zyL": cand(feats=base6 + cross + ("zd", "zyd"), ridge_hour=-1),
         "Z = S sin semilla": cand(feats=C.FEATS + ("zd", "zyd"), ridge_hour=-1, seed_hours=0)}
    return v


def bench_one(args):
    """Score del banco (mismo camino que scripts/p1_hard.py) para una variante. Devuelve también el coste por día de la semana."""
    name, split = args
    from battery.sim import baseline_totals, score
    full = B.hard_table()
    df = split_frame(full, split)
    exclude = set(df.timestamp)
    fit_df = full[~full.timestamp.isin(exclude)]
    prior = B.fit_market(exclude, fit_df)
    solar_prior = B.fit_solar(fit_df)
    base = baseline_totals(df)
    if name == "real 24 h":
        ag = B.perfect_market_agent(prior, df, solar_prior)
    else:
        ag = B.hard_agent(prior, solar_prior)
        ag.policy.market = variants(exclude, prior)[name]()
    totals, log = B.simulate_hard(ag, df)
    sc = score(totals, base)
    w_co2, w_cost = score_weights(base["co2_kg"] / len(df), base["cost_eur"] / len(df))
    cost = log.import_kw.to_numpy() * (w_co2 * df.co2_kg_kwh.to_numpy() + w_cost * df.price_eur_kwh.to_numpy())
    day = (np.arange(len(df)) % 168) // 24
    by_day = [float(100 * cost[day == d].sum() / len(df)) for d in range(7)]       # en puntos de score (más = peor)
    week = np.arange(len(df)) // 168
    by_week = [float(100 * cost[week == d].sum() / len(df)) for d in range(len(df) // 168)]
    return name, sc["score_raw"], totals["export_kwh"], 1000 * totals["runtime_s"] / len(df), by_day, by_week


def bench(names, split="dev"):
    from multiprocessing import Pool
    with Pool(4) as pool:
        res = pool.map(bench_one, [(n, split) for n in names])
    ref = [r for r in res if r[0] == "agente actual"]
    for name, sc, ex, ms, by_day, by_week in res:
        extra = ""
        if ref:
            extra = (f" | gana {sc - ref[0][1]:+.3f} | por semana: " + " ".join(f"{b - a:+.2f}" for a, b in zip(by_week, ref[0][5])))
        print(f"{name:28s} {sc:7.3f} vert {ex:5.0f} {ms:4.1f} ms{extra}")


def cv_ridge(exclude):
    """Elige el encogimiento por hora dejando fuera un mes cada vez (solo filas de ajuste, nada de dev)."""
    d = C.dense_market(exclude)
    for crossfit in (True,):
        rows = C.training_rows(d, C.FEATS, crossfit)
        # mes de cada fila: se reconstruye repitiendo el ajuste por meses (más simple: plegar por orden)
        for lam in (-1, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0):
            se, n = 0.0, 0
            for name in C.NAMES:
                for X, Xc, y, hour in rows[name]:
                    ok = np.isfinite(X).all(axis=1)
                    X, y, hour = X[ok], y[ok], hour[ok]
                    fold = (np.arange(len(y)) * 6) // max(len(y), 1)       # 6 pliegues seguidos en el tiempo (2 meses cada uno)
                    for f in range(6):
                        tr, te = fold != f, fold == f
                        coef = C.ridge_by_hour(X[tr], y[tr], hour[tr], lam)
                        pred = (X[te] * coef[hour[te], :-1]).sum(axis=1) + coef[hour[te], -1]
                        se += float(((pred - y[te]) ** 2).sum()); n += int(te.sum())
            print(f"crossfit={crossfit} ridge_hour={lam:>7}: RMSE de z fuera de muestra {np.sqrt(se / n):.4f} ({n} filas)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cv", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--bench", default="", help="variantes (separadas por ;) que se pasan por el banco")
    ap.add_argument("--split", default="dev")
    args = ap.parse_args()
    if args.bench:
        bench(args.bench.split(";"), args.split)
        return
    df, exclude, prior = setup(args.split)
    if args.cv:
        cv_ridge(exclude)
        return
    out = []
    for name, fac in variants(exclude, prior).items():
        if args.only and not any(s in name for s in args.only.split(",")):
            continue
        t0 = time.perf_counter(); fc = fac(); fit_s = time.perf_counter() - t0
        out.append({"variante": name, **run(fc, df, prior), "ajuste_s": fit_s})
    print(pd.DataFrame(out).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
