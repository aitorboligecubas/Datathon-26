"""Verificación del candidato "mercado" MES A MES (P1, sábado 14/11). No se empaqueta.

El banco (scripts/p1_hard.py) solo da el score total. Aquí se reparte por meses:
    aportación del mes = 100 * (0,7 * CO2 ahorrado en el mes / CO2 de referencia de TODO el episodio
                                + 0,3 * euros ahorrados en el mes / euros de referencia de TODO el episodio)
La suma de las aportaciones de los meses es exactamente el score del banco.
Se compara el agente de antes ("v4": sin la clave "cand") con el candidato del laboratorio
(scripts/p1_lab/hard_market_cand.py:make), con las mismas tablas y en la misma ejecución.

    python results/p1_hard/mercado_verif_meses.py                       # dev y val
    python results/p1_hard/mercado_verif_meses.py --ventanas 15-21,12-18   # otras ventanas de 7 días del mes
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
for _p in (str(REPO / "src"), str(REPO / "scripts"), str(REPO / "scripts" / "p1_lab")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import p1_hard as B  # noqa: E402
import hard_market_cand as L  # noqa: E402
from battery.sim import baseline_totals, score  # noqa: E402


def window_frame(full: pd.DataFrame, name: str) -> pd.DataFrame:
    """'dev', 'val' o 'a-b' (días a..b de cada mes)."""
    if name in ("dev", "val"):
        return B.split_frame(full, name)
    a, b = (int(v) for v in name.split("-"))
    d = full[(full.timestamp.dt.day >= a) & (full.timestamp.dt.day <= b)]
    return d.reset_index(drop=True)


def by_month(df: pd.DataFrame, log: pd.DataFrame, base: dict) -> pd.DataFrame:
    """CO2, euros y aportación al score de cada mes del episodio."""
    ym = pd.DatetimeIndex(df.timestamp).strftime("%Y-%m")
    ref = np.maximum(df.load_kw.to_numpy() - df.pv_kw.to_numpy(), 0.0)
    co2, price = df.co2_kg_kwh.to_numpy(), df.price_eur_kwh.to_numpy()
    imp = log.import_kw.to_numpy()
    t = pd.DataFrame({"ym": ym, "ref_co2": ref * co2, "ref_eur": ref * price, "co2": imp * co2, "eur": imp * price,
                      "soc": log.soc_kwh.to_numpy()})
    g = t.groupby("ym").agg(ref_co2=("ref_co2", "sum"), ref_eur=("ref_eur", "sum"), co2=("co2", "sum"),
                            eur=("eur", "sum"), soc_fin=("soc", "last"))
    g["ap_co2"] = 70.0 * (g.ref_co2 - g.co2) / base["co2_kg"]
    g["ap_eur"] = 30.0 * (g.ref_eur - g.eur) / base["cost_eur"]
    g["aport"] = g.ap_co2 + g.ap_eur
    g["propio"] = 70.0 * (g.ref_co2 - g.co2) / g.ref_co2 + 30.0 * (g.ref_eur - g.eur) / g.ref_eur
    return g


def compare(full: pd.DataFrame, name: str, with_ceiling: bool = False) -> pd.DataFrame:
    df = window_frame(full, name)
    exclude = set(df.timestamp)
    fit_df = full[~full.timestamp.isin(exclude)]
    prior = B.fit_market(exclude, fit_df)
    solar_prior = B.fit_solar(fit_df)
    base = baseline_totals(df)

    def cand():
        a = B.hard_agent(prior, solar_prior)
        a.policy.market = L.make(exclude, prior)
        return a

    agents = {"v4": lambda: B.hard_agent({k: v for k, v in prior.items() if k != "cand"}, solar_prior), "cand": cand}
    if with_ceiling:
        agents["techo"] = lambda: B.perfect_market_agent(prior, df, solar_prior)
    res, tot = {}, {}
    for key, fac in agents.items():
        totals, log = B.simulate_hard(fac(), df)
        tot[key] = score(totals, base)
        res[key] = by_month(df, log, base)
    out = pd.DataFrame({"horas": df.groupby(pd.DatetimeIndex(df.timestamp).strftime("%Y-%m")).size(),
                        "v4": res["v4"].aport, "cand": res["cand"].aport})
    out["dif"] = out.cand - out.v4
    out["dif_co2"] = res["cand"].ap_co2 - res["v4"].ap_co2
    out["dif_eur"] = res["cand"].ap_eur - res["v4"].ap_eur
    out["dif_propio"] = res["cand"].propio - res["v4"].propio          # con la referencia del propio mes
    out["soc_fin_v4"] = res["v4"].soc_fin
    out["soc_fin_cand"] = res["cand"].soc_fin
    if with_ceiling:
        out["hueco"] = res["techo"].aport - res["v4"].aport           # lo que ganaría la previsión perfecta
    d = out.dif.to_numpy()
    n = len(d)
    se = float(d.std(ddof=1) / np.sqrt(n)) if n > 1 else float("nan")
    print(f"\n=== ventana {name}: {len(df)} h, {n} meses ===")
    print(out.round(3).to_string())
    line = (f"total v4 {tot['v4']['score_raw']:.3f} | candidato {tot['cand']['score_raw']:.3f} | "
            f"diferencia {tot['cand']['score_raw'] - tot['v4']['score_raw']:+.3f} "
            f"(CO2 {out.dif_co2.sum():+.3f}, euros {out.dif_eur.sum():+.3f})")
    if with_ceiling:
        line += f" | techo {tot['techo']['score_raw']:.3f}"
    print(line)
    print(f"meses que gana {int((d > 1e-9).sum())} / pierde {int((d < -1e-9).sum())} / igual {int((np.abs(d) <= 1e-9).sum())} de {n} | "
          f"media por mes {d.mean():+.4f}, error típico {se:.4f}, t = {d.mean() / se if se > 0 else float('nan'):.2f} | "
          f"sin el mejor mes {d.sum() - d.max():+.3f} | sin el peor {d.sum() - d.min():+.3f}")
    out.insert(0, "ventana", name)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ventanas", default="dev,val")
    ap.add_argument("--techo", action="store_true", help="añade la previsión perfecta de precio y CO2")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    full = B.hard_table()
    parts = [compare(full, w.strip(), args.techo) for w in args.ventanas.split(",") if w.strip()]
    if args.out:
        pd.concat(parts).to_csv(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
