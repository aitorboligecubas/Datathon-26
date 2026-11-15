"""Revisión "perdidas": qué veía el agente (previsión de consumo neto, margen y pesos) en cada hora.

Owner: P1 (laboratorio). NO se empaqueta.
    python scripts/p1_lab/hard_rev_perdidas_diag.py val     -> results/p1_hard/rev_perdidas_diag_val.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
for extra in (str(REPO / "src"), str(REPO / "scripts")):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import p1_hard as bench  # noqa: E402
import battery.hard as hard  # noqa: E402
from battery.hard import HardPolicy  # noqa: E402
from battery.hard_market import KNOWN_HOURS  # noqa: E402

LOG = []


class DiagPolicy(HardPolicy):
    def plan_scenarios(self, obs):
        nl = self.netload
        if self.no_data_block or self.elapsed_s > self.time_budget_s:
            return None
        times = self.horizon_times(obs)
        if times and len(obs.price) < KNOWN_HOURS:
            times = times[:len(obs.price)]
        if not times or times[0] is None:
            return None
        load, pv, margin = nl.scenarios(times)
        price, co2 = self.market.forecast(obs, times, self.weather)
        weight = self.w_co2 * co2 + self.w_cost * price
        a = HardPolicy.plan_scenarios(self, obs)
        row = {"timestamp": times[0], "f_load": load[0], "f_pv": pv[0], "f_margin": margin[0], "plan": a,
               "w0": weight[0], "H": len(times)}
        for k in range(1, min(len(weight), 12)):
            row[f"w{k}"] = weight[k]
            row[f"n{k}"] = load[k] - pv[k]
        LOG.append(row)
        return a


def main(split: str) -> None:
    full = bench.hard_table()
    df = bench.split_frame(full, split)
    exclude = set(df.timestamp)
    fit_df = full[~full.timestamp.isin(exclude)]
    prior = bench.fit_market(exclude, fit_df)
    solar_prior = bench.fit_solar(fit_df)
    agent = bench.hard_agent(prior, solar_prior)
    agent.policy.__class__ = DiagPolicy
    totals, log = bench.simulate_hard(agent, df)
    d = pd.DataFrame(LOG).merge(log, on="timestamp", how="right")
    d["price"] = df.price_eur_kwh.to_numpy(); d["co2"] = df.co2_kg_kwh.to_numpy()
    d["w_true"] = agent.policy.w_co2 * d.co2 + agent.policy.w_cost * d.price
    d.to_csv(REPO / "results" / "p1_hard" / f"rev_perdidas_diag_{split}.csv", index=False)
    print(split, "hecho", len(d), totals)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "val")
