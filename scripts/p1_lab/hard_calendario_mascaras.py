"""Las 7 versiones enviadas con el CALENDARIO REAL del episodio (salto de un mes entre semanas, como en el test),
hora a hora, y qué máscaras de "50 % de cada semana" reproducen lo que salió en la web.

    python scripts/p1_lab/hard_calendario_mascaras.py sim val     # simula y guarda results/hourly/calcal_<ventana>.pkl
    python scripts/p1_lab/hard_calendario_mascaras.py tabla       # compara las máscaras con la web
"""
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

OUT = REPO / "results" / "hourly"
OUT.mkdir(parents=True, exist_ok=True)
VERS = ["v6", "v7", "v8", "v9", "v10", "v12", "v14"]
WEB_CO2 = 100 * np.array([13607.2, 13776.6, 13789.2, 13822.8, 13809.7, 13815.8, 13772.5]) / 60255.0
WEB_COST = 100 * np.array([24974.56, 25636.04, 25442.25, 25468.67, 25665.85, 25511.18, 25525.83]) / 94985.0
REF = VERS.index("v10")

if sys.argv[1] == "sim":
    import p1_hard as B
    from hard_rev_perdidas_salto import CalPolicy
    win = sys.argv[2]
    full = B.hard_table()
    df = B.split_frame(full, win)
    exclude = set(df.timestamp)
    fit_df = full[~full.timestamp.isin(exclude)]
    old_market = B.fit_market(exclude, fit_df, blend=False, weekend=False)
    new_market = B.fit_market(exclude, fit_df)
    solar = B.fit_solar(fit_df)
    simple = {k: v for k, v in solar.items() if k not in ("cand", "scen", "seed")}
    ts = list(pd.DatetimeIndex(df.timestamp))
    nxt = dict(zip(ts[:-1], ts[1:]))
    SPEC = {"v6": (old_market, simple, None, False, False), "v7": (old_market, solar, None, False, False),
            "v8": (old_market, solar, 1.4, False, False), "v9": (old_market, solar, 1.4, False, True),
            "v10": (old_market, solar, None, False, True), "v12": (old_market, solar, None, True, True),
            "v14": (new_market, solar, None, True, True)}
    base_imp = np.maximum(df.load_kw - df.pv_kw, 0).to_numpy(float)
    co2, eur = df.co2_kg_kwh.to_numpy(float), df.price_eur_kwh.to_numpy(float)
    out = {}
    for name, (market, sol, z, scen, seed) in SPEC.items():
        a = B.hard_agent(market, sol, use_scenarios=scen, use_seed=seed)
        if z is not None:
            a.policy.netload.z = a.policy.netload.z_plan = a.policy.netload.z_default = z
        a.policy.__class__ = CalPolicy
        a.policy.nxt = nxt
        totals, log = B.simulate_hard(a, df)
        imp = log.import_kw.to_numpy(float)
        out[name] = {"co2": (base_imp - imp) * co2, "eur": (base_imp - imp) * eur}
        sc = 70 * out[name]["co2"].sum() / (base_imp * co2).sum() + 30 * out[name]["eur"].sum() / (base_imp * eur).sum()
        print(f"{win:6s} {name:4s} calendario real: score {sc:.3f} infr {totals['infractions']}", flush=True)
    pickle.dump({"out": out, "base_co2": base_imp * co2, "base_eur": base_imp * eur}, open(OUT / f"calcal_{win}.pkl", "wb"))
else:
    wins = [w for w in ("val", "dev", "1-7", "3-9", "12-18", "15-21") if (OUT / f"calcal_{w}.pkl").exists()]
    data = {w: pickle.load(open(OUT / f"calcal_{w}.pkl", "rb")) for w in wins}
    web = 0.7 * (WEB_CO2 - WEB_CO2[REF]) + 0.3 * (WEB_COST - WEB_COST[REF])

    def masks_for(n):
        hw = np.arange(n) % 168
        day, hour = hw // 24, hw % 24
        m = {"todo": np.ones(n, bool), "primera mitad de la semana": hw < 84, "segunda mitad de la semana": hw >= 84,
             "días pares": day % 2 == 0, "días impares": day % 2 == 1, "horas pares": hour % 2 == 0, "horas impares": hour % 2 == 1,
             "mañana (0-11 h)": hour < 12, "tarde (12-23 h)": hour >= 12}
        for b in (3, 6):
            m[f"bloques de {b} h pares"] = (hw // b) % 2 == 0
            m[f"bloques de {b} h impares"] = (hw // b) % 2 == 1
        return m

    def scores(d, mask):
        return np.array([70 * d["out"][v]["co2"][mask].sum() / d["base_co2"][mask].sum()
                         + 30 * d["out"][v]["eur"][mask].sum() / d["base_eur"][mask].sum() for v in VERS])

    print("WEB frente a la v10:        " + "  ".join(f"{VERS[i]} {web[i]:+.2f}" for i in range(len(VERS))))
    print(f"Con el calendario real del episodio, ventanas {wins}:")
    rows = []
    for label in masks_for(168):
        d = np.mean([scores(data[w], masks_for(len(data[w]["base_co2"]))[label]) for w in wins], axis=0)
        d = d - d[REF]
        others = [i for i in range(len(VERS)) if i != REF]
        signs = sum(np.sign(d[i]) == np.sign(web[i]) for i in others)
        dist = float(np.sqrt(np.mean((d[others] - web[others]) ** 2)))
        rows.append((dist, label, signs, d))
    for dist, label, signs, d in sorted(rows):
        print(f"  {label:28s} signos {signs}/6  distancia {dist:.2f} | " + "  ".join(f"{VERS[i]} {d[i]:+.2f}" for i in range(len(VERS))))
