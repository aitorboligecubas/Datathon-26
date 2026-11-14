"""¿Se puede prever mejor el consumo neto de la HORA ACTUAL? (rama mejora-score-hard). NO se empaqueta.

El hueco de consumo y solar del modo difícil está casi entero en la hora actual (+0,43 de +0,55 en el banco). Aquí se
compara, fuera de muestra, el error del previsor actual (SolarCand, antelación 0) con modelos que usan más pistas de
lo que el agente ya sabe a esa hora (lecturas de t-1, t-2, t-24, meteo de t-1, perfil, cielo despejado).

    python scripts/p1_lab/mejora_nowcast.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
for extra in (str(REPO / "src"), str(REPO / "scripts"), str(REPO / "scripts" / "p1_lab")):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import p1_hard as bench  # noqa: E402
from battery.hard_solar import CAMPUS_HOLIDAYS, SolarCand, campus_how  # noqa: E402

H1 = pd.Timedelta(hours=1)
METEO = ("irradiancia_wm2", "temp_ambient_c", "temp_panel_c", "vent_ms")


def features(t: pd.DataFrame, cand_prior: dict) -> pd.DataFrame:
    """Pistas de la hora t con lo que el agente sabe al empezar esa hora. NaN si la hora pedida no existe."""
    t = t.sort_values("timestamp").reset_index(drop=True)
    idx = pd.DatetimeIndex(t.timestamp)
    s = t.set_index("timestamp")
    sc = SolarCand(cand_prior, None)

    def at(col, lag):
        return s[col].reindex(idx - lag * H1).to_numpy(float)

    clear_now, mean_now = np.array([sc.sky_at(ts) for ts in idx]).T
    clear_prev, mean_prev = np.array([sc.sky_at(ts - H1) for ts in idx]).T
    prof = np.array([sc.profile(ts) for ts in idx])
    prof_prev = np.array([sc.profile(ts - H1) for ts in idx])
    f = pd.DataFrame({
        "hour": idx.hour, "month": idx.month, "how": [campus_how(ts) for ts in idx],
        "hol": [int((ts.year, ts.month, ts.day) in set(CAMPUS_HOLIDAYS)) for ts in idx],
        "l1": at("load_kw", 1), "l2": at("load_kw", 2), "l3": at("load_kw", 3), "l24": at("load_kw", 24),
        "l23": at("load_kw", 23), "l25": at("load_kw", 25), "l168": at("load_kw", 168),
        "p1": at("pv_kw", 1), "p2": at("pv_kw", 2), "p3": at("pv_kw", 3), "p24": at("pv_kw", 24), "p25": at("pv_kw", 25),
        "clear": clear_now, "mean": mean_now, "clear1": clear_prev, "mean1": mean_prev, "prof": prof, "prof1": prof_prev,
    }, index=t.index)
    for m in METEO:
        if m in s:
            f["w_" + m] = at(m, 1)
            f["w2_" + m] = at(m, 2)
    f["k1"] = f.p1 / np.where(f.clear1 > 30, f.clear1, np.nan)
    f["k2"] = f.p2 / np.where(f.clear1 > 30, np.array([sc.sky_at(ts - 2 * H1)[0] for ts in idx]), np.nan)
    f["r1"] = f.l1 / f.prof1
    f["net1"] = f.l1 - f.p1
    f["net24"] = f.l24 - f.p24
    f["y_load"], f["y_pv"] = t.load_kw.to_numpy(float), t.pv_kw.to_numpy(float)
    f["y_net"] = f.y_load - f.y_pv
    f["timestamp"] = idx
    return f


def baseline_nowcast(df: pd.DataFrame, prior: dict, solar_prior: dict) -> pd.DataFrame:
    """Previsión de la hora actual del agente actual en el episodio `df` (consumo y solar de antelación 0)."""
    rows = []
    ag = bench.hard_agent(prior, solar_prior)
    nl = ag.policy.netload
    orig = nl.forecast_tables

    def ft(times):
        load, pv_shaded = orig(times)
        return load, pv_shaded

    class Rec:
        def act(self, obs):
            a = ag.act(obs)
            rows.append((pd.Timestamp(obs["timestamp"]), nl.net_lo0, nl.net_lo0_charge))
            return a

    nl.forecast_tables = ft
    bench.simulate_hard(Rec(), df)
    return pd.DataFrame(rows, columns=["timestamp", "net_lo0", "net_lo0_charge"])


def main():
    import lightgbm as lgb
    full = bench.hard_table()
    out = []
    for w in ("val", "8-14", "15-21"):
        df = bench.split_frame(full, w)
        ex = set(df.timestamp)
        fit_df = full[~full.timestamp.isin(ex)]
        sp = bench.fit_solar(fit_df)
        F = features(full, sp["cand"])
        tr, te = F[~F.timestamp.isin(ex)], F[F.timestamp.isin(ex)]
        X = [c for c in F.columns if not c.startswith("y_") and c != "timestamp"]
        tr = tr[np.isfinite(tr.y_net)]
        res = {"ventana": w}
        for q in (0.5, 0.08):
            m = lgb.LGBMRegressor(objective="quantile", alpha=q, n_estimators=400, learning_rate=0.03, num_leaves=31,
                                  min_child_samples=30, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1)
            m.fit(tr[X], tr.y_net)
            pred = m.predict(te[X])
            if q == 0.5:
                res["lgb_mae"] = float(np.nanmean(np.abs(te.y_net - pred)))
            else:
                res["lgb_q08_cubre"] = float(np.nanmean(te.y_net >= pred))
                res["lgb_q08_hueco"] = float(np.nanmean(np.maximum(te.y_net - pred, 0)))
        prior = bench.fit_market(ex, fit_df)
        b = baseline_nowcast(df, prior, sp).merge(te[["timestamp", "y_net"]], on="timestamp")
        res["actual_q_cubre"] = float(np.mean(b.y_net >= b.net_lo0))
        res["actual_q_hueco"] = float(np.mean(np.maximum(b.y_net - b.net_lo0, 0)))
        out.append(res)
        print(res, flush=True)
    print(pd.DataFrame(out).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
