"""Revisión "calendario" del HARD MODE: las dos últimas horas de cada semana y el puente a la siguiente. NO se empaqueta.

Episodio con el calendario del test (hard_ataque_comun.episodio_test) y, a diferencia de los ataques, con las
SEMILLAS REETIQUETADAS: los 7 días (mercado) y las 48 h (consumo y solar) anteriores a cada semana de origen se
ponen con la fecha de los días anteriores a la semana del test, como pasa en el test real.

    python scripts/p1_lab/hard_rev_calendario_puente.py [variantes separadas por comas]

Variantes: actual | fixA (22 y 23 h del último día: lo de la semana siguiente, solo con el perfil) |
           puente (fixA + la regresión del mercado con la semilla de la semana siguiente) |
           puente_noche (puente + consumo de la primera noche de la semana siguiente = última lectura de su semilla)
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hard_ataque_comun as c  # noqa: E402
import p1_hard  # noqa: E402
from battery import hard_market as hm  # noqa: E402
from battery.hard import ONE_HOUR  # noqa: E402

OUT = c.REPO / "results" / "p1_hard"


def semillas(df):
    """Semillas de mercado y de consumo/solar con las fechas del episodio (test) y los datos del train de antes
    de cada semana de origen."""
    full = c.tabla().set_index("timestamp")
    market = p1_hard.market_frame()
    mseed, nseed = [], []
    ts = pd.DatetimeIndex(df.timestamp)
    starts = [ts[0]] + [ts[k] for k in range(1, len(ts)) if ts[k] - ts[k - 1] != ONE_HOUR]
    for T0 in starts:
        src0 = next((T0 - pd.Timedelta(days=s) for s in (14, 21, 7) if (T0 - pd.Timedelta(days=s)) in full.index), None)
        if src0 is None:
            continue
        shift = T0 - src0
        hrs = [h for h in pd.date_range(src0 - pd.Timedelta(hours=168), src0 - ONE_HOUR, freq="h")]
        # mercado: tramo final seguido
        good = []
        for h in reversed(hrs):
            if h in market.index:
                good.append(h)
            else:
                break
        good = good[::-1]
        if good:
            mseed.append({"start": int(hm.hour_index(good[0] + shift)),
                          "price": [float(market.price[h]) for h in good], "co2": [float(market.co2[h]) for h in good]})
        good = []
        for h in reversed(hrs[-48:]):
            if h in full.index and np.isfinite(full.load_kw[h]) and np.isfinite(full.pv_kw[h]):
                good.append(h)
            else:
                break
        good = good[::-1]
        if good:
            nseed.append({"start": (good[0] + shift).strftime("%Y-%m-%d %H:%M"),
                          "load": [round(float(full.load_kw[h]), 3) for h in good],
                          "pv": [round(float(full.pv_kw[h]), 3) for h in good]})
    return mseed, nseed


class MarketFix(hm.MarketCand):
    """MarketCand con el arreglo de las dos últimas horas de la semana (fixA) y, si bridge, el puente."""
    bridge = False
    n_fix = 0
    n_bridge = 0

    def cand_forecast(self, obs, times):
        n_known = min(len(obs.price), len(obs.co2), len(times))
        if n_known < hm.KNOWN_HOURS or times[0] is None:
            return None
        H = len(times)
        keys = [hm.hour_index(t) for t in times]
        now = keys[0]
        if self.h0 is None or not (hm.STORE_PAST_H // 2 <= now - self.h0 < hm.STORE_LEN_H - 200):
            self.rebase(now)
        i = now - self.h0
        base = {name: np.array([self.profile(name, t) for t in times]) for name in hm.NAMES}
        for name, arr in (("price", obs.price), ("co2", obs.co2)):
            for k in range(n_known):
                pos = keys[k] - self.h0
                if 0 <= pos < hm.STORE_LEN_H:
                    self.z[name][pos] = hm.log_ratio(float(arr[k]), float(base[name][k]))
        jump_known = any(keys[k] - now != k for k in range(n_known))     # la semana se acaba dentro de lo conocido
        month = times[0].month
        if jump_known:
            ks = np.array([], dtype=int)
            sc = None
            self.n_fix += 1
        else:
            sc = {name: self.scalars(name, i, times[0].hour) for name in hm.NAMES}
            for name in hm.NAMES:
                if not all(math.isfinite(sc[name][j]) for j in ("0", "1", "2")):
                    return None
            ks = np.array([k for k in range(n_known, H) if keys[k] - now == k and times[k].month == month], dtype=int)
            ks = ks[ks < hm.LEADS + hm.KNOWN_HOURS]
        # puente: las horas de la semana siguiente, con la regresión "como si fueran las 21 h de la víspera"
        bidx, bks, bsc, bi = np.array([], dtype=int), None, None, None
        if self.bridge:
            j0 = next((k for k in range(1, H) if keys[k] - keys[k - 1] != 1), None)
            if j0 is not None:
                T0 = keys[j0]
                bi = (T0 - hm.KNOWN_HOURS) - self.h0
                if 72 <= bi < hm.STORE_LEN_H - 60:
                    hour_v = (times[j0].hour - hm.KNOWN_HOURS) % 24
                    bsc = {name: self.scalars(name, bi, hour_v) for name in hm.NAMES}
                    if all(math.isfinite(bsc[name][j]) for name in hm.NAMES for j in ("0", "1", "2")):
                        bidx = np.array([k for k in range(max(j0, n_known), H)
                                         if keys[k] - T0 == k - j0 and (k - j0) < hm.LEADS], dtype=int)
                        bks = bidx - j0 + hm.KNOWN_HOURS
        out = []
        for name, other, arr in (("price", "co2", obs.price), ("co2", "price", obs.co2)):
            b = base[name]
            if not (np.isfinite(b).all() and (b > 0).all()):
                return None
            zhat = np.zeros(H)
            if len(ks):
                hours = np.array([times[k].hour for k in ks], dtype=int)
                zhat[ks] = self.predict(name, other, sc, i, ks, hours)
            if len(bidx):
                hours = np.array([times[k].hour for k in bidx], dtype=int)
                zb = self.predict(name, other, bsc, bi, bks, hours)
                zhat[bidx] = np.where(np.isfinite(zb), zb, 0.0)
            x = b * np.exp(zhat)
            x[:n_known] = np.asarray(arr[:n_known], dtype=float)
            if not np.isfinite(x).all():
                return None
            out.append(np.maximum(x, 0.0))
        if len(bidx):
            self.n_bridge += 1
        return out[0], out[1]


def noche_puente(pol):
    """El consumo de la primera noche de la semana siguiente (00-05 h) es la última lectura de su semilla."""
    nl = pol.netload
    orig = nl.scenarios

    def scen(times):
        load, pv, margin = orig(times)
        try:
            for k in range(1, len(times)):
                if times[k] - times[k - 1] != ONE_HOUR:
                    T0 = times[k]
                    last = pol.netload_seed.get(T0 - ONE_HOUR)
                    if last is not None and T0.hour == 0:
                        kk = k
                        while kk < len(times) and times[kk].hour < 6 and times[kk].day == T0.day:
                            load[kk] = last[0]
                            kk += 1
                    break
        except Exception:
            pass
        return load, pv, margin

    nl.scenarios = scen


def hacer(variante, pm, ps):
    a = c.agente(pm, ps)
    pol = a.policy
    if variante != "actual":
        m = MarketFix(pm)
        m.bridge = variante.startswith("puente")
        pol.market = m
    if variante == "puente_noche":
        noche_puente(pol)
    return a


def main() -> int:
    variantes = (sys.argv[1] if len(sys.argv) > 1 else "actual,fixA,puente,puente_noche").split(",")
    df, origen = c.episodio_test(nov="omitir")
    pm, ps = c.priors(origen)
    mseed, nseed = semillas(df)
    pm = dict(pm, cand=dict(pm["cand"], seed=mseed))
    ps = dict(ps, seed=nseed)
    print(f"episodio: {len(df)} h | semillas de mercado {len(mseed)} | de consumo {len(nseed)}", flush=True)
    ts = pd.DatetimeIndex(df.timestamp)
    last_day = np.array([(t + pd.Timedelta(days=1)).month != t.month for t in ts])
    rows, logs = [], {}
    for v in variantes:
        a = hacer(v, pm, ps)
        r = c.simular(a, df)
        logs[v] = r["log"]
        pol = a.policy
        rows.append({"variante": v, "score": r["score"], "infr": r["infr"], "exc": r["excepciones"],
                     "vert_desc": r["vert_descarga"], "vert_solar": r["vert_solar"], "soc_final": r["soc_final"],
                     "n_scen": pol.n_scen, "seed_mismatch": pol.seed_mismatches,
                     "n_fix": getattr(pol.market, "n_fix", 0), "n_bridge": getattr(pol.market, "n_bridge", 0)})
        print(pd.DataFrame(rows[-1:]).round(4).to_string(index=False), flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "rev_calendario_puente.csv", index=False)
    # qué cambia en las últimas horas de cada semana
    if "actual" in logs and len(logs) > 1:
        base = logs["actual"]
        for v, lg in logs.items():
            if v == "actual":
                continue
            d = (lg.action_kw - base.action_kw).to_numpy()
            sel = last_day & (np.abs(d) > 1.0)
            print(f"\n{v}: horas del último día con acción distinta: {int(sel.sum())}; fuera del último día: "
                  f"{int(((np.abs(d) > 1.0) & ~last_day).sum())}")
            t = pd.DataFrame({"ts": ts[sel], "actual": base.action_kw[sel].round(0), v: lg.action_kw[sel].round(0),
                              "soc_actual": base.soc_kwh[sel].round(0), "soc_" + v: lg.soc_kwh[sel].round(0)})
            print(t[t.ts.dt.hour >= 20].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
