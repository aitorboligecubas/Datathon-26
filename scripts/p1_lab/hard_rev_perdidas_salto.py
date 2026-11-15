"""Revisión "perdidas": la previsión de precio y CO2 de las horas de DESPUÉS del salto de semana.

Owner: P1 (laboratorio). NO se empaqueta.

Qué se mira. En las últimas 23 horas de cada semana del test el plan de 24 h ya incluye horas de la semana
siguiente (un mes después). Para esas horas `MarketCand.cand_forecast` usa SOLO el perfil del mes (zhat = 0,
hard_market.py línea 345), aunque la memoria ya tiene la semilla: el precio y el CO2 reales de los 7 días del
train que preceden a esa semana (acaban justo una hora antes de su primera hora). El candidato prevé esas horas
con la misma regresión de siempre, "puesta de pie" en las tres últimas horas conocidas antes de cada una.

El banco normal no ejercita el salto (el agente cree que la semana sigue en el día siguiente). Aquí el agente
recibe el calendario REAL del episodio (qué fecha viene después de cada una), igual que en el test conoce el suyo.

    python scripts/p1_lab/hard_rev_perdidas_salto.py dev        # A banco normal, B calendario real, C + semilla
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
for extra in (str(REPO / "src"), str(REPO / "scripts")):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import p1_hard as bench  # noqa: E402
from battery.hard import ONE_HOUR, HardPolicy  # noqa: E402
from battery.hard_market import KNOWN_HOURS, LEADS, NAMES, STORE_LEN_H, MarketCand, hour_index  # noqa: E402


class CalPolicy(HardPolicy):
    """La política actual, pero las fechas del plan siguen el calendario real del episodio del banco."""
    nxt = {}

    def horizon_times(self, obs) -> list:
        ts = obs.timestamp
        if ts is None:
            return []
        times, t = [], ts
        for _ in range(self.horizon):
            times.append(t)
            n = self.nxt.get(t)
            t = n if n is not None else t + ONE_HOUR       # el final del episodio no se conoce (como en el banco)
        return times


class MarketJump(MarketCand):
    """MarketCand + previsión con la semilla de las horas de después del salto (antes: solo el perfil)."""
    jump_gain = 1.0
    n_jump = 0

    def cand_forecast(self, obs, times: list):
        out = MarketCand.cand_forecast(self, obs, times)
        if out is None:
            return out
        try:
            H = len(times)
            n_known = min(len(obs.price), len(obs.co2), H)
            keys = [hour_index(t) for t in times]
            now = keys[0]
            post = [k for k in range(H) if keys[k] - now != k]
            if not post:
                return out
            k0 = post[0]
            first = keys[k0]
            known_post = [k for k in range(k0, n_known)]
            vnow = first - KNOWN_HOURS if not known_post else keys[known_post[-1]] - (KNOWN_HOURS - 1)
            i = vnow - self.h0
            if not (60 <= i and i + KNOWN_HOURS + LEADS + 2 < STORE_LEN_H):
                return out
            sc = {name: self.scalars(name, i, vnow % 24) for name in NAMES}
            for name in NAMES:
                if not all(math.isfinite(sc[name][j]) for j in ("0", "1", "2")):
                    return out
            idx = np.array([k for k in post if k >= n_known and keys[k] - first == k - k0
                            and KNOWN_HOURS <= keys[k] - vnow < LEADS + KNOWN_HOURS], dtype=int)
            if not len(idx):
                return out
            ks = np.array([keys[k] - vnow for k in idx], dtype=int)
            hours = np.array([times[k].hour for k in idx], dtype=int)
            price, co2 = np.array(out[0], dtype=float), np.array(out[1], dtype=float)
            zp = self.predict("price", "co2", sc, i, ks, hours)
            zc = self.predict("co2", "price", sc, i, ks, hours)
            price[idx] = price[idx] * np.exp(self.jump_gain * zp)
            co2[idx] = co2[idx] * np.exp(self.jump_gain * zc)
            if np.isfinite(price).all() and np.isfinite(co2).all():
                self.n_jump += 1
                return np.maximum(price, 0.0), np.maximum(co2, 0.0)
        except Exception:
            pass
        return out


def run(split: str) -> pd.DataFrame:
    full = bench.hard_table()
    df = bench.split_frame(full, split)
    exclude = set(df.timestamp)
    fit_df = full[~full.timestamp.isin(exclude)]
    prior = bench.fit_market(exclude, fit_df)
    solar_prior = bench.fit_solar(fit_df)
    base = bench.baseline_totals(df)
    ts = list(pd.DatetimeIndex(df.timestamp))
    nxt = dict(zip(ts[:-1], ts[1:]))

    def mk(cal: bool, jump: bool):
        a = bench.hard_agent(prior, solar_prior)
        if cal:
            a.policy.__class__ = CalPolicy
            a.policy.nxt = nxt
        if jump:
            a.policy.market.__class__ = MarketJump
        return a

    rows = []
    for name, cal, jump in (("A banco normal", False, False), ("B calendario real", True, False),
                            ("C calendario real + semilla tras el salto", True, True)):
        ag = mk(cal, jump)
        totals, log = bench.simulate_hard(ag, df)
        sc = bench.score(totals, base)
        blk = (log.timestamp.diff() > pd.Timedelta(hours=6)).cumsum()
        soc_end = log.groupby(blk).soc_kwh.last().to_numpy()[:-1]
        rows.append({"ventana": split, "agente": name, "score": sc["score_raw"], "co2_pct": sc["d_co2_pct"],
                     "coste_pct": sc["d_cost_pct"], "infr": sc["infractions"], "vertido_kwh": totals["export_kwh"],
                     "soc_fin_semana": float(np.mean(soc_end)), "n_salto": getattr(ag.policy.market, "n_jump", 0),
                     "s": totals["runtime_s"]})
    out = pd.DataFrame(rows)
    out.to_csv(REPO / "results" / "p1_hard" / f"rev_perdidas_salto_{split}.csv", index=False)
    print(out.round(3).to_string(index=False))
    return out


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    for s in (sys.argv[1:] or ["dev"]):
        run(s)
