"""Encargo "coste" (ronda 3): ¿qué cambio legítimo da más coste con el CO2 igual? Simulaciones del banco.

    python scripts/p1_lab/hard_r3_coste_sim.py dev            # también 1-7 y val
    python scripts/p1_lab/hard_r3_coste_sim.py val base,diag,wc

Guarda, tras cada simulación, results/hourly/r3_coste_<ventana>.pkl con el ahorro hora a hora de cada variante
(para las máscaras) y los errores de la previsión de precio y CO2. Las tablas: hard_r3_coste_tablas.py.
NO se usa nada del test: los techos "precio real" y "CO2 real" son solo de diagnóstico.
"""
import pickle
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
from battery.hard import HardPolicy  # noqa: E402

OUT = REPO / "results" / "p1_hard"
PKL = OUT.parent / "hourly"      # los .pkl pesan 5 MB cada uno: van a results/hourly/, que git ignora
PKL.mkdir(parents=True, exist_ok=True)
win = sys.argv[1]
groups = (sys.argv[2] if len(sys.argv) > 2 else "base,diag,wc,z").split(",")
full = B.hard_table()
df = B.split_frame(full, win)
exclude = set(df.timestamp)
fit_df = full[~full.timestamp.isin(exclude)]
t0 = time.time()
old_market = B.fit_market(exclude, fit_df, blend=False, weekend=False)      # mercado de v5 a v12
new_market = B.fit_market(exclude, fit_df)                                   # v14
solar = B.fit_solar(fit_df)
print(f"{win}: ajustes en {time.time() - t0:.0f} s", flush=True)
ROW = {t: i for i, t in enumerate(df.timestamp)}
PRICE, CO2 = df.price_eur_kwh.to_numpy(float), df.co2_kg_kwh.to_numpy(float)


class ScaledPolicy(HardPolicy):
    """HardPolicy con la incertidumbre del plan (el margen de los cuantiles) multiplicada por `scen_scale`."""
    scen_scale = 1.0

    def plan_scenarios(self, obs):
        nl = self.netload
        orig = nl.scenarios
        scale = self.scen_scale

        def scaled(times):
            load, pv, margin = orig(times)
            return load, pv, np.asarray(margin, dtype=float) * scale

        nl.scenarios = scaled
        try:
            return HardPolicy.plan_scenarios(self, obs)
        finally:
            del nl.scenarios


class MixMarket:
    """Diagnóstico (tramposo): la previsión del agente, con el precio y/o el CO2 REALES de las filas siguientes."""

    def __init__(self, inner, real_price: bool, real_co2: bool):
        self.inner, self.real_price, self.real_co2 = inner, real_price, real_co2

    def forecast(self, obs, times, weather=None):
        p, c = self.inner.forecast(obs, times, weather)
        p, c = np.array(p, dtype=float), np.array(c, dtype=float)
        i = ROW.get(times[0])
        if i is not None:
            H = len(times)
            for on, real, dst in ((self.real_price, PRICE, p), (self.real_co2, CO2, c)):
                if on:
                    r = real[i:i + H]
                    dst[:len(r)] = r
                    if len(r) < H:
                        dst[len(r):] = r[-1]
        return p, c


class RecMarket:
    """Apunta la previsión de cada hora (para medir dónde falla)."""

    def __init__(self, inner):
        self.inner, self.rec = inner, {}

    def forecast(self, obs, times, weather=None):
        p, c = self.inner.forecast(obs, times, weather)
        if len(times) == 24:
            self.rec[times[0]] = (list(times), np.array(p, dtype=float), np.array(c, dtype=float))
        return p, c


def v10(z=None, wc=1.0, real=None, rec=False):
    a = B.hard_agent(old_market, solar, use_scenarios=False)
    return tune(a, z, wc, real, rec)


def v14(scale=None, wc=1.0, real=None, rec=False):
    a = B.hard_agent(new_market, solar)
    if scale is not None:
        a.policy.__class__ = ScaledPolicy
        a.policy.scen_scale = scale
    return tune(a, None, wc, real, rec)


def tune(a, z, wc, real, rec):
    pol = a.policy
    if z is not None:
        pol.netload.z = pol.netload.z_plan = pol.netload.z_default = z
    pol.w_cost = pol.w_cost * wc
    if real:
        pol.market = MixMarket(pol.market, "p" in real, "c" in real)
    if rec:
        pol.market = RecMarket(pol.market)
    return a


V = []
if "base" in groups:
    V += [("v10", lambda: v10(rec=True)), ("v14", lambda: v14(rec=True))]
if "diag" in groups:
    V += [("v14 precio real", lambda: v14(real="p")), ("v14 CO2 real", lambda: v14(real="c")),
          ("v14 los dos reales", lambda: v14(real="pc")), ("v10 precio real", lambda: v10(real="p")),
          ("v10 CO2 real", lambda: v10(real="c"))]
if "wc" in groups:
    for m in (1.5, 2.0, 0.75, 3.0, 0.5):
        V += [(f"v10 coste x{m:g}", lambda m=m: v10(wc=m)), (f"v14 coste x{m:g}", lambda m=m: v14(wc=m))]
if "z" in groups:
    V += [("v10 margen 0.8", lambda: v10(z=0.8)), ("v14 incert. x0.7", lambda: v14(scale=0.7)),
          ("v10 margen 0.6", lambda: v10(z=0.6)), ("v14 incert. x0.5", lambda: v14(scale=0.5)),
          ("v10 margen 1.2", lambda: v10(z=1.2)), ("v14 incert. x1.3", lambda: v14(scale=1.3))]
if "wc2" in groups:      # combinaciones (solo si los grupos anteriores apuntan a ellas)
    for m in (1.25, 4.0):
        V += [(f"v10 coste x{m:g}", lambda m=m: v10(wc=m)), (f"v14 coste x{m:g}", lambda m=m: v14(wc=m))]

path = PKL / f"r3_coste_{win}.pkl"
state = pickle.load(open(path, "rb")) if path.exists() else {"out": {}, "rec": {}}
base_imp = np.maximum(df.load_kw - df.pv_kw, 0).to_numpy(float)
state.update({"base_co2": base_imp * CO2, "base_eur": base_imp * PRICE, "timestamp": df.timestamp.to_numpy()})
mk = B.market_frame()
TRUE_P, TRUE_C = mk.price.to_dict(), mk.co2.to_dict()
for name, make in V:
    if name in state["out"]:
        continue
    t0 = time.time()
    a = make()
    totals, log = B.simulate_hard(a, df)
    imp = log.import_kw.to_numpy(float)
    o = {"co2": (base_imp - imp) * CO2, "eur": (base_imp - imp) * PRICE, "action": log.action_kw.to_numpy(float),
         "infr": totals["infractions"], "export": totals["export_kwh"]}
    state["out"][name] = o
    m = a.policy.market
    if isinstance(m, RecMarket):
        rows = []
        for t_now, (times, p, c) in m.rec.items():
            for k in range(3, 24):
                tp, tc = TRUE_P.get(times[k]), TRUE_C.get(times[k])
                if tp is not None and tc is not None:
                    rows.append((t_now, k, times[k], p[k], tp, c[k], tc))
        state["rec"][name] = pd.DataFrame(rows, columns=["now", "k", "target", "p_fc", "p", "c_fc", "c"])
    sc_co2 = 100 * o["co2"].sum() / state["base_co2"].sum()
    sc_eur = 100 * o["eur"].sum() / state["base_eur"].sum()
    print(f"{win:5s} {name:22s} score {0.7 * sc_co2 + 0.3 * sc_eur:7.3f}  CO2 {sc_co2:6.3f}  coste {sc_eur:6.3f}  infr {o['infr']}  "
          f"vertido {o['export']:.0f}  ({time.time() - t0:.0f} s)", flush=True)
    pickle.dump(state, open(path, "wb"))
