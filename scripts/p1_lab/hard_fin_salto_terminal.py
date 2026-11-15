"""Revisor del SALTO ENTRE SEMANAS, 6.ª parte: UNA regla causal para la carga con la que se cruza el salto.

Hoy, lo que queda en la batería al final del plan de 24 h vale el cuantil 25 % de los pesos del propio plan. En las
últimas 24 h de cada semana ese plan mezcla horas de esta semana y de la siguiente (un mes después, con otro nivel de
precio y CO2). REGLA: cuando el plan cruza el salto, lo que quede vale el cuantil 25 % (el mismo parámetro, sin ajustar)
de los pesos previstos para las PRIMERAS 24 h de la semana siguiente: su perfil, al nivel de las últimas 24 h de su
semilla (g = 0,6 fijado de antemano). Todo lo que usa lo tiene ya el agente (perfil y semilla). Calendario real.

    python scripts/p1_lab/hard_fin_salto_terminal.py val dev 1-7
"""
import math
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
from battery.hard import ONE_HOUR, plan_scen  # noqa: E402
from battery.hard_market import KNOWN_HOURS, NAMES, STORE_LEN_H, hour_index  # noqa: E402
from battery.safety import clip_action  # noqa: E402
from hard_fin_salto_regla import MarketLevel  # noqa: E402
from hard_rev_perdidas_salto import CalPolicy  # noqa: E402


class JumpTerminal(CalPolicy):
    gain = 0.6
    n_rule = 0
    use_level = True

    def next_week_terminal(self, times):
        keys = [hour_index(t) for t in times]
        post = [k for k in range(len(times)) if keys[k] - keys[0] != k]
        if not post:
            return None
        m = self.market
        first_t = times[post[0]]
        first = keys[post[0]]
        lo, hi = first - 24 - m.h0, first - m.h0
        t24 = [first_t + ONE_HOUR * j for j in range(24)]
        fc = {}
        for name in NAMES:
            lvl = 1.0
            if self.use_level and lo >= 0 and hi <= STORE_LEN_H:
                z = np.asarray(m.z[name][lo:hi], dtype=float)
                z = z[np.isfinite(z)]
                if len(z) >= 12:
                    lvl = math.exp(self.gain * float(z.mean()))
            fc[name] = np.array([m.profile(name, t) for t in t24], dtype=float) * lvl
        w24 = self.w_co2 * fc["co2"] + self.w_cost * fc["price"]
        if not np.isfinite(w24).all():
            return None
        return float(np.quantile(w24, self.terminal_quantile)) * self.p.eta_discharge

    def plan_scenarios(self, obs):
        nl = self.netload
        if self.no_data_block or self.elapsed_s > self.time_budget_s:
            return None
        times = self.horizon_times(obs)
        if times and len(obs.price) < KNOWN_HOURS:
            times = times[:len(obs.price)]
        if not times or times[0] is None:
            return None
        H = len(times)
        load, pv, margin = nl.scenarios(times)
        price, co2 = self.market.forecast(obs, times, self.weather)
        weight = self.w_co2 * co2 + self.w_cost * price
        ends = H < self.horizon
        terminal = 0.0 if ends else float(np.quantile(weight, self.terminal_quantile)) * self.p.eta_discharge
        if not ends:
            try:
                tv = self.next_week_terminal(times)
                if tv is not None and math.isfinite(tv):
                    terminal = tv
                    self.n_rule += 1
            except Exception:
                pass
        net = load - pv
        nodes = net[:, None] + margin[:, None] * nl.scen_u[None, :]
        if not (np.isfinite(nodes).all() and np.isfinite(weight).all() and math.isfinite(obs.soc_kwh)):
            return None
        actions = plan_scen(obs.soc_kwh, nodes, nl.scen_tail, nl.scen_head, weight, terminal, self.p)
        return clip_action(float(actions[0]), obs.soc_kwh, self.p)


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
        ends_ = [np.where(wk == j)[0][-1] for j in range(wk.max())]
        rows = []
        for name, cls, lvl, mlevel in (("v14", CalPolicy, False, False), ("v14 + valor de la carga con la semana siguiente (perfil + nivel de la semilla)", JumpTerminal, True, False),
                                       ("v14 + valor de la carga con la semana siguiente (solo perfil)", JumpTerminal, False, False),
                                       ("v14 + valor de la carga (perfil + nivel) + previsión al nivel de la semilla", JumpTerminal, True, True)):
            a = B.hard_agent(market, solar)
            a.policy.__class__ = cls
            a.policy.nxt = nxt
            if cls is JumpTerminal:
                a.policy.use_level = lvl
            if mlevel:
                a.policy.market.__class__ = MarketLevel
            totals, log = B.simulate_hard(a, df)
            sc = B.score(totals, base)
            rows.append({"ventana": win, "agente": name, "score": sc["score_raw"], "co2": sc["d_co2_pct"], "coste": sc["d_cost_pct"], "infr": sc["infractions"],
                         "soc_fin_semana_media": float(log.soc_kwh.to_numpy()[ends_].mean()), "n_regla": getattr(a.policy, "n_rule", 0), "n_scen": a.policy.n_scen})
            print(win, name, round(sc["score_raw"], 3), "soc fin semana:", np.round(log.soc_kwh.to_numpy()[ends_]).astype(int).tolist(), flush=True)
        R = pd.DataFrame(rows)
        R["d_score"] = R.score - R.score.iloc[0]
        R.to_csv(REPO / "results" / "p1_hard" / f"fin_salto_terminal_{win}.csv", index=False)
        print(R.round(3).to_string(index=False), flush=True)
