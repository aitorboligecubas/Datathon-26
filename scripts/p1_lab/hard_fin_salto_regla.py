"""Revisor del SALTO ENTRE SEMANAS, 3.ª parte: cuánto hay como mucho en la frontera y si una regla causal lo captura.

Con el calendario real (CalPolicy), sobre el agente actual (v14):
  - "real tras el salto": TECHO, no causal. Las horas del plan de DESPUÉS del salto llevan el precio y el CO2 reales
    (antes: solo el perfil del mes). Es lo máximo que puede dar cualquier previsión mejor de esas horas.
  - "nivel de la semilla": regla CAUSAL. El perfil de las horas de después del salto se multiplica por
    exp(g * desviación media de las últimas 24 h de la semilla de esa semana), g = 0,6 fijado de antemano (sin ajustar).
    La semilla (7 días del train que preceden a cada semana del test) ya está en la memoria del agente.

    python scripts/p1_lab/hard_fin_salto_regla.py val dev 1-7
"""
import math
import pickle
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
REPO = Path(__file__).resolve().parents[2]
for extra in (str(REPO / "src"), str(REPO / "scripts"), str(REPO / "scripts" / "p1_lab")):
    if extra not in sys.path:
        sys.path.insert(0, extra)
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import p1_hard as B  # noqa: E402
from battery.hard_market import STORE_LEN_H, MarketCand, hour_index  # noqa: E402
from hard_rev_perdidas_salto import CalPolicy  # noqa: E402


class MarketTrueJump(MarketCand):
    """TECHO (no causal): precio y CO2 reales en las horas del plan de después del salto."""
    true = {}

    def cand_forecast(self, obs, times: list):
        out = MarketCand.cand_forecast(self, obs, times)
        if out is None:
            return out
        keys = [hour_index(t) for t in times]
        post = [k for k in range(len(times)) if keys[k] - keys[0] != k]
        if not post:
            return out
        price, co2 = np.array(out[0], dtype=float), np.array(out[1], dtype=float)
        for k in post:
            v = self.true.get(times[k])
            if v is not None:
                price[k], co2[k] = v
        return price, co2


class MarketLevel(MarketCand):
    """Regla causal: el perfil de después del salto, al nivel de las últimas 24 h de la semilla de esa semana."""
    gain = 0.6
    n_jump = 0

    def cand_forecast(self, obs, times: list):
        out = MarketCand.cand_forecast(self, obs, times)
        if out is None:
            return out
        try:
            H = len(times)
            n_known = min(len(obs.price), len(obs.co2), H)
            keys = [hour_index(t) for t in times]
            allpost = [k for k in range(H) if keys[k] - keys[0] != k]
            post = [k for k in allpost if k >= n_known]
            if not post:
                return out
            first = keys[allpost[0]]
            lo, hi = first - 24 - self.h0, first - self.h0
            if lo < 0 or hi > STORE_LEN_H:
                return out
            res = []
            for name, arr in (("price", out[0]), ("co2", out[1])):
                x = np.array(arr, dtype=float)
                z = np.asarray(self.z[name][lo:hi], dtype=float)
                z = z[np.isfinite(z)]
                if len(z) < 12:
                    return out
                x[post] = x[post] * math.exp(self.gain * float(z.mean()))
                res.append(x)
            if np.isfinite(res[0]).all() and np.isfinite(res[1]).all():
                self.n_jump += 1
                return res[0], res[1]
        except Exception:
            pass
        return out


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    full = B.hard_table()
    for win in sys.argv[1:]:
        df = B.split_frame(full, win)
        exclude = set(df.timestamp)
        fit_df = full[~full.timestamp.isin(exclude)]
        market, solar = B.fit_market(exclude, fit_df), B.fit_solar(fit_df)
        base = B.baseline_totals(df)
        ts = list(pd.DatetimeIndex(df.timestamp))
        nxt = dict(zip(ts[:-1], ts[1:]))
        key = np.array([t.year * 12 + t.month for t in ts])
        wk = np.concatenate([[0], np.cumsum(key[1:] != key[:-1])])
        ends = [np.where(wk == j)[0][-1] for j in range(wk.max())]
        MarketTrueJump.true = {t: (float(p), float(c)) for t, p, c in zip(ts, df.price_eur_kwh, df.co2_kg_kwh)}
        rows, logs = [], {}
        for name, cls in (("v14", None), ("v14 + real tras el salto (TECHO, no causal)", MarketTrueJump), ("v14 + nivel de la semilla (causal, g=0,6)", MarketLevel)):
            a = B.hard_agent(market, solar)
            a.policy.__class__ = CalPolicy
            a.policy.nxt = nxt
            if cls is not None:
                a.policy.market.__class__ = cls
            totals, log = B.simulate_hard(a, df)
            sc = B.score(totals, base)
            logs[name] = log
            rows.append({"ventana": win, "agente": name, "score": sc["score_raw"], "co2": sc["d_co2_pct"], "coste": sc["d_cost_pct"],
                         "infr": sc["infractions"], "soc_fin_semana_media": float(log.soc_kwh.to_numpy()[ends].mean()),
                         "n_regla": getattr(a.policy.market, "n_jump", 0)})
            print(win, name, round(sc["score_raw"], 3), "soc fin semana:", np.round(log.soc_kwh.to_numpy()[ends]).astype(int).tolist(), flush=True)
        R = pd.DataFrame(rows)
        R["d_score"] = R.score - R.score.iloc[0]
        R.to_csv(REPO / "results" / "hourly" / f"fin_salto_regla_{win}.csv", index=False)
        pickle.dump(logs, open(REPO / "results" / "hourly" / f"fin_salto_regla_{win}.pkl", "wb"))
        print(R.round(3).to_string(index=False), flush=True)
