"""Revisor del previsor de precio y CO2 (cierre): cuánto cuesta que a las 22 y 23 h del último día de cada semana
el previsor caiga en la clase madre (perfil x nivel de la semana que acaba) en vez de dar solo el perfil a la semana
siguiente, que es lo que hace de 02 a 21 h. Banco con el calendario real (CalPolicy), una ventana.

    python scripts/p1_lab/hard_rc_mercado_2223.py val
"""
import sys, time, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
REPO = Path(__file__).resolve().parents[2]
for extra in (str(REPO / "src"), str(REPO / "scripts"), str(REPO / "scripts" / "p1_lab")):
    if extra not in sys.path:
        sys.path.insert(0, extra)
import numpy as np
import pandas as pd
import p1_hard as B
from hard_rev_perdidas_salto import CalPolicy
from battery.hard_market import MarketCand, KNOWN_HOURS, hour_index


class MarketFix(MarketCand):
    """Si el salto de semana cae dentro de las 3 horas conocidas, la semana siguiente va solo con el perfil."""
    n_fix = 0

    def cand_forecast(self, obs, times):
        out = MarketCand.cand_forecast(self, obs, times)
        if out is not None:
            return out
        n_known = min(len(obs.price), len(obs.co2), len(times))
        if n_known < KNOWN_HOURS or times[0] is None or len(times) <= n_known:
            return None
        keys = [hour_index(t) for t in times]
        if all(keys[k] - keys[0] == k for k in range(n_known)):
            return None
        res = []
        for name, arr in (("price", obs.price), ("co2", obs.co2)):
            b = np.array([self.profile(name, t) for t in times])
            if not (np.isfinite(b).all() and (b > 0).all()):
                return None
            x = b.copy()
            x[:n_known] = np.asarray(arr[:n_known], dtype=float)
            if not np.isfinite(x).all():
                return None
            res.append(np.maximum(x, 0.0))
        MarketFix.n_fix += 1
        return res[0], res[1]


win = sys.argv[1] if len(sys.argv) > 1 else "val"
t0 = time.time()
full = B.hard_table()
df = B.split_frame(full, win)
exclude = set(df.timestamp)
fit_df = full[~full.timestamp.isin(exclude)]
market = B.fit_market(exclude, fit_df)
solar = B.fit_solar(fit_df)
base = B.baseline_totals(df)
ts = list(pd.DatetimeIndex(df.timestamp))
nxt = dict(zip(ts[:-1], ts[1:]))
print("ajuste %.0f s, horas %d" % (time.time() - t0, len(df)), flush=True)
logs = {}
for name, fix in (("v14 tal cual", False), ("v14 + 22-23h solo perfil", True)):
    a = B.hard_agent(market, solar)
    a.policy.__class__ = CalPolicy
    a.policy.nxt = nxt
    if fix:
        a.policy.market.__class__ = MarketFix
    t1 = time.time()
    totals, log = B.simulate_hard(a, df)
    sc = B.score(totals, base)
    logs[name] = log
    print("%s %-26s score %.4f co2 %.3f coste %.3f infr %d (%.0f s) n_fix=%d" % (win, name, sc["score_raw"], sc["d_co2_pct"], sc["d_cost_pct"], sc["infractions"], time.time() - t1, MarketFix.n_fix), flush=True)
a, b = logs["v14 tal cual"], logs["v14 + 22-23h solo perfil"]
d = (a.action_kw - b.action_kw).abs()
ch = a[d > 1.0]
print("horas con otra accion: %d" % len(ch))
for i in ch.index[:40]:
    print("  %s  tal cual %.0f kW | arreglo %.0f kW" % (a.timestamp[i], a.action_kw[i], b.action_kw[i]))

# Reparto por semana de la diferencia de score (arreglo - tal cual): ¿es una sola transición o varias?
price = df["price_eur_kwh"].to_numpy(float); co2 = df["co2_kg_kwh"].to_numpy(float)
wk = np.arange(len(df)) // 168
dsc = 100.0 * (0.7 * (a.import_kw.to_numpy() - b.import_kw.to_numpy()) * co2 / base["co2_kg"]
               + 0.3 * (a.import_kw.to_numpy() - b.import_kw.to_numpy()) * price / base["cost_eur"])
per = pd.Series(dsc).groupby(wk).sum()
print("diferencia de score por semana (arreglo - tal cual), una por semana del episodio:")
print("  " + " ".join("%+.3f" % v for v in per.to_numpy()) + "  | suma %+.3f" % per.sum())
