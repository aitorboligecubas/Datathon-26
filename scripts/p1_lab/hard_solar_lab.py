"""Laboratorio del encargo "solar" del HARD MODE. NO se empaqueta.

Owner: P1. Compara variantes de scripts/p1_lab/hard_solar_cand.py en una ventana de días de cada mes,
con todo lo que se aprende ajustado SIN esa ventana (como hace scripts/p1_hard.py).

    python scripts/p1_lab/hard_solar_lab.py --days 8-14 --variants base,cand           # dev
    python scripts/p1_lab/hard_solar_lab.py --days 1-7  --variants base,cand --perfect # con precio y CO2 reales
    python scripts/p1_lab/hard_solar_lab.py --days 8-14 --variants base --diag         # dónde se pierde, por hora

No usa nunca el split val (últimas 168 h de cada mes).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "p1_lab"))

import p1_hard as bench  # noqa: E402
from battery.baselines import OracleAgent  # noqa: E402
from battery.hard import HARD_PARAMS  # noqa: E402
from battery.optimizer import score_weights  # noqa: E402
from battery.sim import baseline_totals, score  # noqa: E402


def window(full: pd.DataFrame, days: str) -> pd.DataFrame:
    a, b = [int(x) for x in days.split("-")]
    d = full.timestamp.dt.day
    return full[(d >= a) & (d <= b)].reset_index(drop=True)


class TrueNet:
    """Previsor tramposo (solo para medir techos): conoce el consumo y la solar reales.
    mode "now": solo los de la hora actual; "all": los de todo el horizonte."""

    def __init__(self, inner, df: pd.DataFrame, mode: str):
        self.inner, self.mode = inner, mode
        self.load = dict(zip(df.timestamp, df.load_kw)); self.pv = dict(zip(df.timestamp, df.pv_kw))

    def new_block(self):
        self.inner.new_block()

    def update(self, obs, weather=None):
        self.inner.update(obs, weather)

    def forecast(self, obs, times):
        load, pv = self.inner.forecast(obs, times)
        load, pv = np.array(load, dtype=float), np.array(pv, dtype=float)
        last = len(times) if self.mode == "all" else 1
        for k in range(last):
            if times[k] in self.load:
                load[k], pv[k] = self.load[times[k]], self.pv[times[k]]
        self.inner.net_lo0 = self.inner.net_lo0_charge = float(load[0] - pv[0])
        return load, pv

    def adjust_action(self, action_kw, obs, p):
        return self.inner.adjust_action(action_kw, obs, p)


def run(days: str, variants: list, perfect: bool, diag: bool, opts: dict) -> pd.DataFrame:
    import hard_solar_cand as cand
    full = bench.hard_table()
    df = window(full, days)
    exclude = set(df.timestamp)
    fit_df = full[~full.timestamp.isin(exclude)]
    prior = bench.fit_market(exclude, fit_df)
    solar_prior = bench.fit_solar(fit_df)
    # "base" es el agente de partida (solar sencilla): sin las tablas `cand` que el banco añade desde la v7.
    solar_prior = {k: v for k, v in solar_prior.items() if k != "cand"}
    base = baseline_totals(df)
    w = score_weights(base["co2_kg"] / len(df), base["cost_eur"] / len(df))
    weight = w[0] * df.co2_kg_kwh.to_numpy() + w[1] * df.price_eur_kwh.to_numpy()
    rows = []
    for name in variants:
        if name == "oracle":
            ag = OracleAgent(df, *w, p=HARD_PARAMS)
        else:
            ag = bench.perfect_market_agent(prior, df, solar_prior) if perfect else bench.hard_agent(prior, solar_prior)
            if name != "base":
                kw = dict(opts.get(name, {}))
                cheat = kw.pop("cheat", "")
                if kw.pop("sin_tope", False):        # medir cuánto cuesta el tope de descarga de la política
                    ag.policy.cap_discharge = lambda action_kw, obs: action_kw
                ag.policy.netload = cand.make(exclude, ag.policy.forecaster, **kw)
                if cheat:
                    ag.policy.netload = TrueNet(ag.policy.netload, df, cheat)
        totals, log = bench.simulate_hard(ag, df)
        sc = score(totals, base)
        ex = log[log.export_kw > 1e-6]
        rows.append({"variante": name, "score": sc["score_raw"], "co2_pct": sc["d_co2_pct"], "coste_pct": sc["d_cost_pct"],
                     "infr": sc["infractions"], "vert_descarga": float(ex[ex.action_kw < -1e-6].export_kw.sum()),
                     "vert_solar": float(ex[ex.action_kw >= -1e-6].export_kw.sum()),
                     "ms_paso": 1000 * totals["runtime_s"] / len(df)})
        if diag:
            log = log.assign(hour=log.timestamp.dt.hour, w=weight, net=log.load_kw - log.pv_kw)
            log["desc"] = (-log.action_kw).clip(lower=0); log["carga"] = log.action_kw.clip(lower=0)
            log["vd"] = np.where(log.action_kw < -1e-6, log.export_kw, 0.0); log["vs"] = np.where(log.action_kw >= -1e-6, log.export_kw, 0.0)
            log["carga_red"] = np.minimum(log.carga, log.import_kw)
            log["sin_cubrir"] = np.where(log.action_kw < -1e-6, log.import_kw, 0.0)     # lo que se compró descargando
            g = log.groupby("hour").agg(w=("w", "mean"), net=("net", "mean"), desc=("desc", "sum"), vd=("vd", "sum"),
                                        sin_cubrir=("sin_cubrir", "sum"), carga=("carga", "sum"), carga_red=("carga_red", "sum"),
                                        vs=("vs", "sum"), soc=("soc_kwh", "mean"))
            g["w"] = g.w / weight.mean()
            print(f"--- {name}: por hora del día (kWh en toda la ventana)")
            print(g.round(2).T.to_string())
            pass
    out = pd.DataFrame(rows)
    print(f"días {days} ({len(df)} h){' | precio y CO2 REALES' if perfect else ''}")
    print(out.round(3).to_string(index=False))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", default="8-14")
    ap.add_argument("--variants", default="base,cand")
    ap.add_argument("--perfect", action="store_true", help="con precio y CO2 reales a 24 h (aísla la parte solar)")
    ap.add_argument("--diag", action="store_true")
    ap.add_argument("--opts", default="{}", help='JSON: {"variante": {opciones de make}}')
    args = ap.parse_args()
    run(args.days, args.variants.split(","), args.perfect, args.diag, json.loads(args.opts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
