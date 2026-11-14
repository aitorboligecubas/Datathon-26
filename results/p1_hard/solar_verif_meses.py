"""Verificación independiente del candidato 'solar' (HARD MODE): ¿la mejora es real o ruido?

    python results/p1_hard/solar_verif_meses.py            # dev y val, por meses y por días
    python results/p1_hard/solar_verif_meses.py --piezas   # además, cada pieza apagada (dev y val)

Compara, en la misma ejecución, el agente de partida ("solar sencilla (v6)": la política actual con el
previsor sencillo) y el CANDIDATO (scripts/p1_lab/hard_solar_cand.py:make), con las mismas tablas que usa
el banco (scripts/p1_hard.py). Reparte el score por meses y por días (la suma de las partes es el score),
mira la carga con la que acaba cada agente y cuenta cuántas veces el retoque `uncap` descarga más de lo
que pedía el plan. No se empaqueta. No toca nada del repo.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import p1_hard as bench  # noqa: E402
from battery.sim import baseline_totals, score  # noqa: E402

CAND = str(REPO / "scripts" / "p1_lab" / "hard_solar_cand.py") + ":make"
PIEZAS = ("reg", "quant", "uncap", "pvreg", "freeze", "shade_now")


def instrument(agent):
    """Apunta, hora a hora, lo que pide el plan, lo que deja el tope de la política y lo que sale del retoque."""
    pol = agent.policy
    rec = {"plan": [], "capped": [], "adjusted": []}
    plan0, adj0 = pol.plan_action, pol.netload.adjust_action

    def plan_action(obs):
        v = plan0(obs)
        rec["plan"].append(float(v))
        return v

    def adjust_action(action_kw, obs, p):
        v = adj0(action_kw, obs, p)
        rec["capped"].append(float(action_kw)); rec["adjusted"].append(float(v))
        return v

    pol.plan_action = plan_action
    pol.netload.adjust_action = adjust_action
    return rec


def run(split: str, make, piezas: bool):
    full = bench.hard_table()
    df = bench.split_frame(full, split)
    exclude = set(df.timestamp)
    fit_df = full[~full.timestamp.isin(exclude)]
    prior = bench.fit_market(exclude, fit_df)
    solar_prior = bench.fit_solar(fit_df)
    simple = {k: v for k, v in solar_prior.items() if k != "cand"}
    base = baseline_totals(df)

    def cand(**opts):
        a = bench.hard_agent(prior, solar_prior)
        a.policy.netload = make(exclude, a.policy.forecaster, **opts)
        return a

    agents = {"partida (v6)": lambda: bench.hard_agent(prior, simple), "CANDIDATO": cand}
    if piezas:
        for name in PIEZAS:
            agents["sin " + name] = (lambda n=name: cand(**{n: False}))
        agents["sin sky"] = lambda: cand(sky=False)
    co2 = df.co2_kg_kwh.to_numpy(float); price = df.price_eur_kwh.to_numpy(float)
    base_imp = np.maximum(df.load_kw.to_numpy(float) - df.pv_kw.to_numpy(float), 0.0)
    ts = pd.DatetimeIndex(df.timestamp)
    parts, rows, recs, logs = {}, [], {}, {}
    for name, fac in agents.items():
        ag = fac()
        rec = instrument(ag)
        totals, log = bench.simulate_hard(ag, df)
        sc = score(totals, base)
        imp = log.import_kw.to_numpy(float)
        # parte del score de cada hora: la suma de todas es el score
        part = 100 * (0.7 * (base_imp - imp) * co2 / base["co2_kg"] + 0.3 * (base_imp - imp) * price / base["cost_eur"])
        parts[name], recs[name], logs[name] = part, rec, log
        ex = log[log.export_kw > 1e-6]
        rows.append({"agente": name, "score": sc["score_raw"], "suma_partes": float(part.sum()), "infr": sc["infractions"],
                     "vert_descarga": float(ex[ex.action_kw < -1e-6].export_kw.sum()),
                     "vert_solar": float(ex[ex.action_kw >= -1e-6].export_kw.sum()),
                     "carga_final_kwh": totals["final_soc_kwh"], "respaldos": ag.policy.n_fallbacks,
                     "ms_paso": 1000 * totals["runtime_s"] / len(df)})
    out = pd.DataFrame(rows)
    print(f"\n================ {split}: {len(df)} h ================")
    print(out.round(4).to_string(index=False))

    a, b = parts["partida (v6)"], parts["CANDIDATO"]
    d = pd.Series(b - a, index=ts)
    month = d.index.to_period("M")
    pm = pd.DataFrame({"partida": pd.Series(a, index=ts).groupby(month).sum(), "candidato": pd.Series(b, index=ts).groupby(month).sum()})
    pm["dif"] = pm.candidato - pm.partida
    # carga al acabar cada mes (lo que un agente deja en la batería lo ha pagado ese mes y lo usa el siguiente)
    soc_a = pd.Series(logs["partida (v6)"].soc_kwh.to_numpy(float), index=ts).groupby(month).last()
    soc_b = pd.Series(logs["CANDIDATO"].soc_kwh.to_numpy(float), index=ts).groupby(month).last()
    pm["carga_fin_partida"], pm["carga_fin_cand"] = soc_a, soc_b
    print("\nPor meses (parte del score; la suma es el score):")
    print(pm.round(4).to_string())
    n_win = int((pm.dif > 0).sum())
    se = pm.dif.std(ddof=1) / np.sqrt(len(pm))
    print(f"meses que gana el candidato: {n_win} de {len(pm)} | suma {pm.dif.sum():+.4f} | media por mes {pm.dif.mean():+.4f} "
          f"± {se:.4f} (t = {pm.dif.mean() / se:.2f}) | mayor mes: {pm.dif.max():+.4f} ({100 * pm.dif.max() / pm.dif.sum():.0f} % del total)")
    day = d.groupby(d.index.normalize()).sum()
    rng = np.random.default_rng(0)
    boot = np.array([rng.choice(day.to_numpy(), len(day)).sum() for _ in range(5000)])
    print(f"por días: gana {int((day > 0).sum())} de {len(day)} | suma {day.sum():+.4f} | remuestreo de días (5.000): "
          f"IC 90 % [{np.quantile(boot, 0.05):+.4f}, {np.quantile(boot, 0.95):+.4f}], P(dif <= 0) = {(boot <= 0).mean():.4f}")
    wk = d.groupby([month, (d.index.day - d.index.day.min()) // 7]).sum()
    boot_m = np.array([rng.choice(pm.dif.to_numpy(), len(pm)).sum() for _ in range(5000)])
    print(f"remuestreo de meses (5.000): IC 90 % [{np.quantile(boot_m, 0.05):+.4f}, {np.quantile(boot_m, 0.95):+.4f}], "
          f"P(dif <= 0) = {(boot_m <= 0).mean():.4f}")
    # ¿cuánto vale la diferencia de carga final? Se valora al peso medio de compra, con el rendimiento de descarga.
    w_mean = float((0.7 * co2 / base["co2_kg"] + 0.3 * price / base["cost_eur"]).mean()) * 100
    dsoc = float(soc_b.iloc[-1] - soc_a.iloc[-1])
    print(f"carga final: partida {soc_a.iloc[-1]:.0f} kWh, candidato {soc_b.iloc[-1]:.0f} kWh; la diferencia ({dsoc:+.0f} kWh) "
          f"vale unos {dsoc * 0.9487 * w_mean:+.4f} puntos al peso medio")
    # uncap: ¿descarga más de lo que pedía el plan?
    r = recs["CANDIDATO"]
    if len(r["plan"]) == len(df) and len(r["adjusted"]) == len(df):
        plan, capped, adj = np.array(r["plan"]), np.array(r["capped"]), np.array(r["adjusted"])
        cap_on = (plan < -1e-6) & (capped > plan + 1e-6)
        raised = (adj < capped - 1e-6)
        over = (adj < plan - 1e-6)
        print(f"tope de la política: actúa {int(cap_on.sum())} h | el retoque sube la descarga {int(raised.sum())} h "
              f"({-(adj - capped)[raised].sum():.0f} kWh) | descarga MÁS que el plan {int(over.sum())} h ({-(adj - plan)[over].sum():.0f} kWh, "
              f"máx {(-(adj - plan)[over]).max() if over.any() else 0:.0f} kW)")
        chg = (plan >= -1e-6) & (adj > plan + 1e-6)
        print(f"el retoque sube la carga por encima del plan {int(chg.sum())} h ({(adj - plan)[chg].sum():.0f} kWh)")
    return out, pm, d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--piezas", action="store_true")
    ap.add_argument("--splits", default="dev,val")
    args = ap.parse_args()
    make = bench.load_factory(CAND)
    res = {}
    for split in args.splits.split(","):
        res[split] = run(split, make, args.piezas)
    if "dev" in res and "val" in res:
        d_dev, d_val = res["dev"][2], res["val"][2]
        common = d_dev.index.intersection(d_val.index)
        print(f"\nHoras que comparten dev y val: {len(common)} ({common.min()} a {common.max()})" if len(common) else "\ndev y val no comparten horas")
        if len(common):
            rest = d_val[~d_val.index.isin(common)]
            print(f"val: ganancia en las horas compartidas con dev {d_val[common].sum():+.4f} | en el resto ({len(rest)} h, nunca vistas) {rest.sum():+.4f}")
            m = rest.groupby(rest.index.to_period('M')).sum()
            print(f"val sin las horas compartidas: gana {int((m > 0).sum())} de {len(m)} meses")
    return 0


if __name__ == "__main__":
    sys.exit(main())
