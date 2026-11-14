"""Verificación del candidato "mercado": fugas de datos y error de previsión (P1, sábado 14/11). No se empaqueta.

1. AJUSTE. Se estropean a propósito el precio y el CO2 de las horas excluidas y se repite el ajuste: las tablas
   tienen que salir idénticas. Después se mira qué horas lleva la memoria del train ("semilla").
2. INFERENCIA. Se quitan de la semilla los tramos que no acaban justo antes de una semana evaluada: las
   acciones tienen que ser idénticas (el candidato solo usa el pasado inmediato de cada semana).
3. SIN SEMILLA. Las primeras 25 horas de cada semana tienen que ser idénticas a las del previsor base.
4. ERROR DE PREVISIÓN (no score) del previsor base y del candidato.

    python results/p1_hard/mercado_verif_fugas.py            # dev y val, unos 2 minutos
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
for _p in (str(REPO / "src"), str(REPO / "scripts"), str(REPO / "scripts" / "p1_lab")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import p1_hard as B  # noqa: E402
import hard_market_cand as L  # noqa: E402
from battery.hard_market import MarketForecaster, hour_index  # noqa: E402
from battery.obs import Obs  # noqa: E402
from battery.optimizer import score_weights  # noqa: E402
from battery.sim import baseline_totals, score  # noqa: E402


def mk_obs(ts, price, co2) -> Obs:
    return Obs(hour=int(ts.hour), weekday=int(ts.dayofweek), soc_kwh=3000.0, price=price, co2=co2,
               load_prev_kw=1000.0, pv_prev_kw=0.0, timestamp=ts)


def fit_leak(full: pd.DataFrame, split: str) -> None:
    df = B.split_frame(full, split)
    exclude = set(df.timestamp)
    fit_df = full[~full.timestamp.isin(exclude)]
    m0 = B.market_frame()
    orig = B.market_frame
    try:
        B.market_frame = lambda: m0
        a, pa = L.fit_cand(exclude), B.fit_market(exclude, fit_df)
        m1 = m0.copy()
        sel = m1.index.isin(list(exclude))
        rng = np.random.default_rng(0)
        m1.loc[sel, "price"] = m1.loc[sel, "price"] * rng.uniform(0.2, 5.0, int(sel.sum()))
        m1.loc[sel, "co2"] = m1.loc[sel, "co2"] * rng.uniform(0.2, 5.0, int(sel.sum()))
        B.market_frame = lambda: m1
        b, pb = L.fit_cand(exclude), B.fit_market(exclude, fit_df)
    finally:
        B.market_frame = orig
    same = json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    same_all = json.dumps(pa, sort_keys=True) == json.dumps(pb, sort_keys=True)
    print(f"{split}: {int(sel.sum())} horas excluidas estropeadas | fit_cand idéntico: {same} | fit_market entero idéntico: {same_all}")
    ex_keys = {hour_index(t) for t in exclude}
    di = pd.DatetimeIndex(df.timestamp)
    weeks = pd.DataFrame({"ts": di}).groupby(di.year * 100 + di.month).ts.agg(["min", "max"])
    spans = [(hour_index(r["min"]), hour_index(r["max"])) for _, r in weeks.iterrows()]
    for seg in a["seed"]:
        keys = [seg["start"] + j for j in range(len(seg["price"]))]
        n_ex = sum(k in ex_keys for k in keys)
        n_in = sum(any(lo <= k <= hi for lo, hi in spans) for k in keys)
        if n_ex or n_in:
            t0 = pd.Timestamp.fromordinal(seg["start"] // 24) + pd.Timedelta(hours=seg["start"] % 24)
            print(f"   tramo de semilla {t0} ({len(keys)} h): {n_ex} horas excluidas, {n_in} dentro de una semana evaluada")
    print(f"   tramos de semilla: {len(a['seed'])}")


def inference_leak(full: pd.DataFrame, split: str) -> None:
    df = B.split_frame(full, split)
    exclude = set(df.timestamp)
    fit_df = full[~full.timestamp.isin(exclude)]
    prior, solar_prior = B.fit_market(exclude, fit_df), B.fit_solar(fit_df)
    base = baseline_totals(df)
    first = {hour_index(t) for t in df.groupby([df.timestamp.dt.year, df.timestamp.dt.month]).timestamp.min()}
    seeds = prior["cand"]["seed"]
    before = [s for s in seeds if s["start"] + len(s["price"]) in first]

    def run(seed):
        a = B.hard_agent(prior, solar_prior)
        a.policy.market = L.MarketCand({**prior, "cand": {**prior["cand"], "seed": seed}})
        totals, log = B.simulate_hard(a, df)
        return score(totals, base)["score_raw"], log.action_kw.to_numpy()

    s_all, a_all = run(seeds)
    s_bef, a_bef = run(before)
    print(f"{split}: semilla completa ({len(seeds)} tramos) {s_all:.9f} | solo los tramos pegados antes de cada semana "
          f"({len(before)}) {s_bef:.9f} | acciones idénticas: {bool(np.array_equal(a_all, a_bef))}")
    # sin semilla, frente al previsor base
    w_co2, w_cost = score_weights(prior["co2_ref_kg_per_h"], prior["cost_ref_eur_per_h"])
    fc = {"base": MarketForecaster(prior), "cand": L.make(exclude, prior),
          "cand sin semilla": L.MarketCand({**prior, "cand": {**prior["cand"], "seed": []}})}
    ts = pd.DatetimeIndex(df.timestamp)
    price, co2 = df.price_eur_kwh.to_numpy(), df.co2_kg_kwh.to_numpy()
    true_w = w_co2 * co2 + w_cost * price
    pos = {t: j for j, t in enumerate(ts)}
    week_start = np.r_[0, np.flatnonzero((ts[1:] - ts[:-1]) > pd.Timedelta(hours=30)) + 1]
    wk = np.searchsorted(week_start, np.arange(len(df)), side="right") - 1
    rows, first_diff = [], {}
    for t in range(len(df) - 2):
        if wk[t + 2] != wk[t] or (ts[t + 2] - ts[t]) != pd.Timedelta(hours=2):
            continue                      # sin las 2 últimas horas de cada semana ni los huecos (ahí el banco etiqueta mal)
        times = [ts[t] + pd.Timedelta(hours=k) for k in range(24)]
        obs = mk_obs(ts[t], price[t:t + 3], co2[t:t + 3])
        out = {k: f.forecast(obs, times, {}) for k, f in fc.items()}
        d = max(float(np.abs(out["cand sin semilla"][0] - out["base"][0]).max()), float(np.abs(out["cand sin semilla"][1] - out["base"][1]).max()))
        if d > 1e-12 and wk[t] not in first_diff:
            first_diff[wk[t]] = int((ts[t] - ts[week_start[wk[t]]]) / pd.Timedelta(hours=1))
        for k in range(3, 24):
            j = pos.get(times[k])
            if j is None or wk[j] != wk[t]:
                continue
            r = {"h_sem": t - week_start[wk[t]], "k": k, "w": true_w[j], "p": price[j], "c": co2[j]}
            for name, (p, c) in out.items():
                r["w_" + name], r["p_" + name], r["c_" + name] = w_co2 * c[k] + w_cost * p[k], p[k], c[k]
            rows.append(r)
    print(f"   sin semilla: primera hora de reloj de cada semana en que deja de coincidir con el previsor base: {sorted(set(first_diff.values()))}")
    e = pd.DataFrame(rows)
    print(f"   error absoluto medio de la previsión, en % de la media real ({len(e)} previsiones; peso = 0,7 CO2 + 0,3 precio, lo que entra en el plan)")

    def table(sel, label):
        d = e[sel]
        line = f"     {label:32s} n={len(d):6d}"
        for name in fc:
            line += (f" | {name}: peso {100 * (d['w_' + name] - d.w).abs().mean() / d.w.mean():5.2f} "
                     f"precio {100 * (d['p_' + name] - d.p).abs().mean() / d.p.mean():5.2f} CO2 {100 * (d['c_' + name] - d.c).abs().mean() / d.c.mean():5.2f}")
        print(line)

    table(e.k > 0, "todas las antelaciones (3-23 h)")
    table(e.k <= 8, "antelación 3-8 h")
    table(e.k >= 9, "antelación 9-23 h")
    table(e.h_sem < 24, "primer día de cada semana")
    table((e.h_sem >= 24) & (e.h_sem < 48), "segundo día")
    table(e.h_sem >= 48, "del tercer día en adelante")


def main() -> int:
    full = B.hard_table()
    print("--- 1. Fugas en el ajuste")
    for split in ("dev", "val"):
        fit_leak(full, split)
    print("--- 2-4. Fugas en la inferencia, sin semilla y error de previsión")
    for split in ("dev", "val"):
        inference_leak(full, split)
    return 0


if __name__ == "__main__":
    sys.exit(main())
