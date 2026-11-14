"""Experimento (encargo de transiciones): ¿cuánto vale descargar en la primera hora de una semana?

En la primera hora de cada semana del test el agente no sabe si el contador está a 0. Para cada inicio
de semana de N episodios "normales" del banco (semillas propias, no las de dev ni las de test) se mide:
    a_libre   lo que haría el plan normal en esa hora (kW)
    gana_N    lo que se pierde, si la semana es normal, por no descargar esa hora (puntos de score)
    pierde_Z  lo que se pierde, si la semana viene a 0, por haber descargado a ciegas (puntos de score):
              la energía tirada hay que reponerla al precio del mejor valle de la semana
NO se empaqueta.

    python scripts/p1_lab/trans_exp_inicio.py 3000 24
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from p1_banco import WEEK, make_episode  # noqa: E402
from battery.optimizer import plan  # noqa: E402
from battery.policy import MPCPolicy  # noqa: E402
from battery.sim import simulate  # noqa: E402

ROWS = []


def objective(actions, soc, load, pv, w, terminal, p):
    net = np.asarray(load) - np.asarray(pv)
    s = soc
    for a in actions:
        s = s + a * p.eta_charge if a >= 0 else s + a / p.eta_discharge
    return float((w * np.maximum(net + actions, 0.0)).sum() - terminal * s)


class Probe(MPCPolicy):
    def plan_action(self, obs):
        first = self.block_hours == 0 and self.prev_ts is not None
        a = super().plan_action(obs)
        if first:
            try:
                H = max(1, min(self.horizon, len(obs.price)))
                load, pv = self.forecaster.forecast(obs, H)
                w = self.w_co2 * obs.co2[:H] + self.w_cost * obs.price[:H]
                term = self.terminal_value(obs, H)
                free = plan(obs.soc_kwh, load, pv, obs.price[:H], obs.co2[:H], self.w_co2, self.w_cost, term, self.p)
                load2, pv2 = load.copy(), pv.copy()
                load2[0], pv2[0] = 0.0, 0.0
                hold = plan(obs.soc_kwh, load2, pv2, obs.price[:H], obs.co2[:H], self.w_co2, self.w_cost, term, self.p)
                hold[0] = max(hold[0], 0.0)
                g = objective(hold, obs.soc_kwh, load, pv, w, term, self.p) - objective(free, obs.soc_kwh, load, pv, w, term, self.p)
                res = self.reserve_weight(7) if len(self.valleys) >= 7 else float("nan")
                ROWS.append(dict(ts=obs.timestamp, soc=obs.soc_kwh, a_libre=free[0], gana_N=100 * g / 2016,
                                 w0=w[0], reserva=res, w_min24=float(np.sort(w)[:4].mean()),
                                 pierde_Z=100 / 2016 * max(-free[0], 0.0) / 0.9 * (res if res == res else float(np.sort(w)[:4].mean()))))
            except Exception as e:  # noqa: BLE001
                ROWS.append(dict(ts=obs.timestamp, error=str(e)))
        return a


class _Agent:
    def __init__(self):
        self.policy = Probe()

    def act(self, obs):
        return self.policy.act(obs)


def main():
    base, n = int(sys.argv[1]), int(sys.argv[2])
    for seed in range(base, base + n):
        df = make_episode(seed, "normal")
        k0 = len(ROWS)
        simulate(_Agent(), df)
        for r in ROWS[k0:]:
            r["seed"] = seed
    out = pd.DataFrame(ROWS)
    out["mes"] = pd.to_datetime(out.ts).dt.month
    out.to_csv(REPO / "results" / "p1_banco" / "trans_exp_inicio.csv", index=False)
    d = out[out.a_libre < -1]
    print(f"inicios de semana: {len(out)} en {n} episodios; el plan normal quiere descargar en {len(d)} ({100 * len(d) / len(out):.0f} %)")
    print(f"coste de no descargar nunca en la primera hora, por episodio normal: {out.gana_N.sum() / n:.5f} puntos")
    print("cuando quiere descargar: gana_N media %.5f, mediana %.5f, máx %.5f | pierde_Z media %.5f" % (
        d.gana_N.mean(), d.gana_N.median(), d.gana_N.max(), d.pierde_Z.mean()))
    for p0 in (1 / 12, 1 / 7, 0.25, 0.5):
        keep = d[(1 - p0) * d.gana_N > p0 * d.pierde_Z]
        print(f"   con p0 = {p0:.3f}: descargaría a ciegas en {len(keep)} de {len(d)}; "
              f"coste en semanas normales de los que se abstiene: {(d.gana_N.sum() - keep.gana_N.sum()) / n:.5f} por episodio")
    print(out.groupby("mes").agg(n=("a_libre", "size"), quiere=("a_libre", lambda x: int((x < -1).sum())),
                                 gana_N=("gana_N", "sum"), pierde_Z=("pierde_Z", "mean")).round(5).to_string())


if __name__ == "__main__":
    main()
