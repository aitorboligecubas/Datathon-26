"""Encargo "calibracion" (ronda 3), punto 3: fallos que harían que una versión rinda peor en el servidor sin que
el banco lo vea. NO se empaqueta. Owner: P1.

    python scripts/p1_lab/hard_r3_calibracion_tiempo.py tiempo     # presupuesto de tiempo (servidor k veces más lento)
    python scripts/p1_lab/hard_r3_calibracion_tiempo.py solver     # empates del LP: otro algoritmo de HiGHS
    python scripts/p1_lab/hard_r3_calibracion_tiempo.py semilla    # la semilla de cada semana no casa con el test

tiempo:  el agente pasa a la regla de respaldo cuando su tiempo acumulado supera time_budget_s (40 s). Un servidor
         k veces más lento con 40 s equivale, en esta máquina, a un presupuesto de 40/k s. Se mide con v10, v12 y v14
         en la ventana de validación (2.016 h, como el test).
solver:  se cambia el orden de los métodos del LP (highs-ipm primero): si hay empates, el punto interior devuelve otra
         solución. Lo que cambie la nota es lo máximo que podría cambiar por la versión de scipy/HiGHS.
semilla: v10, v12 y v14 con la semilla desactivada (como si no casara y se olvidara en la segunda hora).
"""
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
REPO = Path(__file__).resolve().parents[2]
for extra in (str(REPO / "src"), str(REPO / "scripts")):
    if extra not in sys.path:
        sys.path.insert(0, extra)
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import p1_hard as B  # noqa: E402

mode = sys.argv[1] if len(sys.argv) > 1 else "tiempo"
win = sys.argv[2] if len(sys.argv) > 2 else "val"
OUT = REPO / "results" / "p1_hard"
full = B.hard_table()
df = B.split_frame(full, win)
exclude = set(df.timestamp)
fit_df = full[~full.timestamp.isin(exclude)]
old_market = B.fit_market(exclude, fit_df, blend=False, weekend=False)
new_market = B.fit_market(exclude, fit_df)
solar = B.fit_solar(fit_df)
MAKE = {"v10": lambda **k: B.hard_agent(old_market, solar, use_scenarios=False, **k),
        "v12": lambda **k: B.hard_agent(old_market, solar, **k),
        "v14": lambda **k: B.hard_agent(new_market, solar, **k)}
base_imp = np.maximum(df.load_kw - df.pv_kw, 0).to_numpy(float)
co2, eur = df.co2_kg_kwh.to_numpy(float), df.price_eur_kwh.to_numpy(float)
N = len(df)


class Timed:
    def __init__(self, agent):
        self.agent, self.ms = agent, []

    def act(self, obs):
        t0 = time.perf_counter()
        a = self.agent.act(obs)
        self.ms.append(1000 * (time.perf_counter() - t0))
        return a


def run(agent):
    w = Timed(agent)
    totals, log = B.simulate_hard(w, df)
    imp = log.import_kw.to_numpy(float)
    sc = 70 * ((base_imp - imp) * co2).sum() / (base_imp * co2).sum() + 30 * ((base_imp - imp) * eur).sum() / (base_imp * eur).sum()
    pol = getattr(agent, "policy", None)
    return {"score": float(sc), "infr": totals["infractions"], "ms": np.array(w.ms), "fallbacks": getattr(pol, "n_fallbacks", -1),
            "n_scen": getattr(pol, "n_scen", -1), "elapsed_s": getattr(pol, "elapsed_s", float("nan")),
            "mismatch": getattr(pol, "seed_mismatches", -1)}


rows = []
if mode == "tiempo":
    for name, make in MAKE.items():
        b = run(make())
        cum = np.cumsum(b["ms"]) / 1000.0
        print(f"{name}: score {b['score']:.3f}  ms/paso medio {b['ms'].mean():.2f}  p99 {np.percentile(b['ms'], 99):.1f}  max {b['ms'].max():.1f}  "
              f"total {cum[-1]:.1f} s (elapsed_s del agente {b['elapsed_s']:.1f})  respaldos {b['fallbacks']}  pasos con plan de cuantiles {b['n_scen']}", flush=True)
        rows.append({"version": name, "k": 1.0, "presupuesto_s": 40.0, "ms_paso": b["ms"].mean(), "total_s": cum[-1], "pasos_respaldo_previstos": 0,
                     "pasos_respaldo": b["fallbacks"], "score": b["score"], "dif": 0.0, "infr": b["infr"]})
        for k in (3, 4, 5, 6, 8, 12):
            over = np.nonzero(cum * k > 40.0)[0]
            pred = int(N - (over[0] + 1)) if len(over) else 0
            if pred == 0:
                print(f"   servidor x{k}: tiempo total {cum[-1] * k:5.1f} s -> no se agota el presupuesto", flush=True)
                rows.append({"version": name, "k": k, "presupuesto_s": 40.0 / k, "ms_paso": b["ms"].mean() * k, "total_s": cum[-1] * k,
                             "pasos_respaldo_previstos": 0, "pasos_respaldo": 0, "score": b["score"], "dif": 0.0, "infr": b["infr"]})
                continue
            r = run(make(time_budget_s=40.0 / k))
            print(f"   servidor x{k}: tiempo total {cum[-1] * k:5.1f} s -> respaldo previsto en {pred} pasos; simulado: {r['fallbacks']} pasos, "
                  f"score {r['score']:.3f} ({r['score'] - b['score']:+.3f})  infr {r['infr']}", flush=True)
            rows.append({"version": name, "k": k, "presupuesto_s": 40.0 / k, "ms_paso": b["ms"].mean() * k, "total_s": cum[-1] * k,
                         "pasos_respaldo_previstos": pred, "pasos_respaldo": r["fallbacks"], "score": r["score"], "dif": r["score"] - b["score"], "infr": r["infr"]})
        # ¿cuántos pasos en respaldo al FINAL del episodio cuestan 0,2 y 0,45 puntos?
        for lost in (10, 20, 30, 50, 80, 120):
            budget = float(cum[N - lost - 1])
            r = run(make(time_budget_s=budget))
            print(f"   respaldo en los últimos ~{lost} pasos: simulado {r['fallbacks']} pasos, score {r['score']:.3f} ({r['score'] - b['score']:+.3f})", flush=True)
            rows.append({"version": name, "k": float("nan"), "presupuesto_s": budget, "ms_paso": b["ms"].mean(), "total_s": cum[-1],
                         "pasos_respaldo_previstos": lost, "pasos_respaldo": r["fallbacks"], "score": r["score"], "dif": r["score"] - b["score"], "infr": r["infr"]})
    pd.DataFrame(rows).to_csv(OUT / f"r3_calibracion_tiempo_{win}.csv", index=False)
elif mode == "solver":
    import battery.hard as H
    import battery.optimizer as O
    for name, make in MAKE.items():
        res = {}
        for label, methods in (("highs (por defecto)", ("highs", "highs-ds", "highs-ipm")), ("highs-ds", ("highs-ds", "highs", "highs-ipm")),
                               ("highs-ipm", ("highs-ipm", "highs", "highs-ds"))):
            O.LP_METHODS = methods
            H.LP_METHODS = methods
            r = run(make())
            res[label] = r["score"]
            print(f"{name} {label:20s} score {r['score']:.4f} ({r['score'] - res['highs (por defecto)']:+.4f})  ms/paso {r['ms'].mean():.2f}  infr {r['infr']}  respaldos {r['fallbacks']}", flush=True)
            rows.append({"version": name, "metodo": label, "score": r["score"], "dif": r["score"] - res["highs (por defecto)"], "ms_paso": r["ms"].mean(), "infr": r["infr"]})
    pd.DataFrame(rows).to_csv(OUT / f"r3_calibracion_solver_{win}.csv", index=False)
elif mode == "semilla":
    for name, make in MAKE.items():
        b = run(make())
        r = run(make(use_seed=False))
        print(f"{name}: con semilla {b['score']:.4f} (semillas que no casan: {b['mismatch']})   sin semilla {r['score']:.4f} ({r['score'] - b['score']:+.4f})", flush=True)
        rows.append({"version": name, "con_semilla": b["score"], "sin_semilla": r["score"], "dif": r["score"] - b["score"], "no_casan": b["mismatch"]})
    pd.DataFrame(rows).to_csv(OUT / f"r3_calibracion_semilla_{win}.csv", index=False)
