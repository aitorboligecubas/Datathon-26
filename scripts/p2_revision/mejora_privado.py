"""Compara candidatos del modo difícil en los MESES DEL PRIVADO (mar-ago) y del público (sep-feb). NO se empaqueta.

Para cada ventana se ajusta todo SIN sus horas y se simula cada candidato. Además de las ventanas del banco usa dos
episodios con el calendario del test (hard_ataque_comun.episodio_test con datos de 14 y 7 días antes: "ep14", "ep7").
La nota de cada mitad se calcula con su propia referencia sin batería (igual que el ranking).

    python scripts/p1_lab/mejora_privado.py fichero_cands.py [--procs 2] [--keys val,1-7,...]
fichero_cands.py define CANDS = {"base": fábrica, "otro": fábrica, ...}, fábrica(prior, solar_prior, exclude) -> agente.
"""
import argparse
import importlib.util
import sys
from multiprocessing import Pool
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
for extra in (str(REPO / "src"), str(REPO / "scripts"), str(REPO / "scripts" / "p1_lab")):
    if extra not in sys.path:
        sys.path.insert(0, extra)
import p1_hard as b  # noqa: E402
from battery.sim import baseline_totals, score  # noqa: E402

PRIVADO, PUBLICO = (3, 4, 5, 6, 7, 8), (9, 10, 11, 12, 1, 2)
KEYS = ["val", "1-7", "3-9", "5-11", "8-14", "10-16", "12-18", "15-21", "16-22", "18-24", "ep14", "ep7"]
ST = {}


def prep(key):
    full = b.hard_table()
    if key.startswith("ep"):
        import hard_ataque_comun as c
        df, ex = c.episodio_test("copia", desfases=(14, 21, 7) if key == "ep14" else (7, 14, 21))
    else:
        df = b.split_frame(full, key)
        ex = set(df.timestamp)
    fit_df = full[~full.timestamp.isin(ex)]
    return df, ex, b.fit_market(ex, fit_df), b.fit_solar(fit_df)


def half(df, log, months):
    m = df.timestamp.dt.month.isin(months).to_numpy()
    d, l = df[m], log[m]
    if not len(d):
        return float("nan")
    return score({"co2_kg": float((l.import_kw * d.co2_kg_kwh).sum()), "cost_eur": float((l.import_kw * d.price_eur_kwh).sum()),
                  "infractions": 0}, baseline_totals(d))["score_raw"]


def run(args):
    key, name = args
    df, ex, prior, sp = ST[key]
    tot, log = b.simulate_hard(ST["cands"][name](prior, sp, ex), df)
    return key, name, half(df, log, PRIVADO), half(df, log, PUBLICO), tot["infractions"], 1000 * tot["runtime_s"] / len(df)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cands")
    ap.add_argument("--procs", type=int, default=2)
    ap.add_argument("--keys", default=",".join(KEYS))
    a = ap.parse_args()
    spec = importlib.util.spec_from_file_location("cands_mod", a.cands)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ST["cands"] = dict(mod.CANDS)
    keys = a.keys.split(",")
    for k in keys:
        ST[k] = prep(k)
    with Pool(a.procs) as p:
        res = p.map(run, [(k, n) for k in keys for n in ST["cands"]])
    t = pd.DataFrame(res, columns=["key", "cand", "priv", "pub", "infr", "ms"])
    for col, label in (("priv", "PRIVADO (mar-ago)"), ("pub", "PÚBLICO (sep-feb)")):
        piv = t.pivot(index="cand", columns="key", values=col)[keys]
        d = piv.sub(piv.loc["base"], axis=1)
        d["media"] = d[keys].mean(axis=1)
        d["peor"] = d[keys].min(axis=1)
        d["gana"] = (d[keys] > 0.005).sum(axis=1)
        d["pierde"] = (d[keys] < -0.005).sum(axis=1)
        print(f"\n{label}: diferencia frente a base")
        print(d.round(3).sort_values("media", ascending=False).to_string())
    print("\ninfracciones:", t.groupby("cand").infr.sum().to_dict(), "| ms/paso máx:", t.groupby("cand").ms.max().round(1).to_dict())


if __name__ == "__main__":
    main()
