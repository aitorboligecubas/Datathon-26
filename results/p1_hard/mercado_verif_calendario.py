"""Verificación del candidato "mercado" con el CALENDARIO DEL TEST (P1, sábado 14/11). No se empaqueta.

El banco (dev y val) no reproduce lo que pasa en el test al acabar cada semana: allí la semana acaba con el
mes y la política salta a la última semana del mes siguiente. Aquí se coge la validación reservada (últimas
168 h de cada mes del train) y se le cambia la fecha 7 días hacia delante: cada semana queda en los últimos
7 días de su mes, como en el test. La memoria del train ("semilla") se mueve igual, para que siga pegada a
su semana. Se quita agosto (sus datos acaban el día 16 y no llegan a fin de mes): el episodio acaba el
31 de julio, que la política trata como final del test. El 25/12 deja de contar como festivo: los datos de
ese día son los de un jueves normal (18/12).

    python results/p1_hard/mercado_verif_calendario.py
    python results/p1_hard/mercado_verif_calendario.py --nov    # añade la semana de noviembre con el contador a 0

Con --nov se añade la semana del 24 al 30 de noviembre con el contador a 0 (en el train, noviembre no tiene
datos de contador): precio y CO2 del 17 al 23 de noviembre (que también se quitan del ajuste), consumo y solar
a 0 y la meteo de la semana de octubre.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
for _p in (str(REPO / "src"), str(REPO / "scripts"), str(REPO / "scripts" / "p1_lab"), str(Path(__file__).resolve().parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import p1_hard as B  # noqa: E402
import hard_market_cand as L  # noqa: E402
import battery.hard_market as HM  # noqa: E402
from battery.hard_market import hour_index  # noqa: E402
from battery.sim import baseline_totals, score  # noqa: E402
from mercado_verif_meses import by_month  # noqa: E402

SHIFT_D = 7


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nov", action="store_true", help="añade la semana de noviembre con el contador a 0")
    args = ap.parse_args()
    full = B.hard_table()
    val = B.split_frame(full, "val")
    exclude = set(val.timestamp)
    nov_src = pd.date_range("2025-11-17", periods=168, freq="h")
    if args.nov:
        exclude |= set(nov_src)
    fit_df = full[~full.timestamp.isin(exclude)]
    prior = B.fit_market(exclude, fit_df)               # trae "cand" = fit_cand(exclude)
    solar_prior = B.fit_solar(fit_df)
    ep = val[val.timestamp < "2026-08-01"].copy().reset_index(drop=True)
    if args.nov:
        market = B.market_frame().reindex(nov_src)
        octw = ep[ep.timestamp.dt.month == 10].reset_index(drop=True)
        novw = octw.copy()                              # la meteo, la de octubre
        novw["timestamp"] = nov_src
        novw["load_kw"], novw["pv_kw"] = 0.0, 0.0
        novw["price_eur_kwh"], novw["co2_kg_kwh"] = market.price.to_numpy(), market.co2.to_numpy()
        ep = pd.concat([ep, novw]).sort_values("timestamp").reset_index(drop=True)
    first = {hour_index(t) for t in ep.groupby([ep.timestamp.dt.year, ep.timestamp.dt.month]).timestamp.min()}
    ep["timestamp"] = ep.timestamp + pd.Timedelta(days=SHIFT_D)
    seeds = []
    for seg in prior["cand"]["seed"]:
        if seg["start"] + len(seg["price"]) in first:        # el tramo que acaba justo antes de una semana evaluada
            seeds.append({**seg, "start": seg["start"] + 24 * SHIFT_D})
    print(f"episodio: {len(ep)} h, de {ep.timestamp.min()} a {ep.timestamp.max()} | tramos de semilla movidos: {len(seeds)}")
    HM.NATIONAL_HOLIDAYS = tuple(h for h in HM.NATIONAL_HOLIDAYS if h != (2025, 12, 25))
    base = baseline_totals(ep)

    def agent(seed):
        a = B.hard_agent({k: v for k, v in prior.items() if k != "cand"}, solar_prior)
        if seed is not None:
            a.policy.market = L.MarketCand({**prior, "cand": {**prior["cand"], "seed": seed}})
        return a

    agents = {"v4 (sin memoria)": lambda: agent(None), "candidato": lambda: agent(seeds),
              "candidato sin semilla": lambda: agent([]),
              "precio y CO2 reales": lambda: B.perfect_market_agent(prior, ep, solar_prior)}
    res, tot, used = {}, {}, {}
    for name, fac in agents.items():
        a = fac()
        m = a.policy.market
        calls = {"cand": 0, "base": 0}
        if isinstance(m, L.MarketCand) and m.cand_ok:
            orig = m.cand_forecast

            def spy(obs, times, _orig=orig, _calls=calls):
                out = _orig(obs, times)
                _calls["cand" if out is not None else "base"] += 1
                return out
            m.cand_forecast = spy
        totals, log = B.simulate_hard(a, ep)
        tot[name] = score(totals, base)
        res[name] = by_month(ep, log, base)
        used[name] = calls
        print(f"{name:24s} score {tot[name]['score_raw']:.3f} | CO2 {tot[name]['d_co2_pct']:.3f} % | coste {tot[name]['d_cost_pct']:.3f} % | "
              f"infr {tot[name]['infractions']} | vertido {totals['export_kwh']:.0f} kWh | carga final {totals['final_soc_kwh']:.0f} kWh | "
              f"{1000 * totals['runtime_s'] / len(ep):.2f} ms/paso | previsiones con el candidato {calls['cand']}, con la receta base {calls['base']}")
    out = pd.DataFrame({"v4": res["v4 (sin memoria)"].aport, "cand": res["candidato"].aport,
                        "cand_sin_semilla": res["candidato sin semilla"].aport})
    out["dif"] = out.cand - out.v4
    out["dif_sin_semilla"] = out.cand_sin_semilla - out.v4
    out["hueco"] = res["precio y CO2 reales"].aport - out.v4
    print(out.round(3).to_string())
    d = out.dif.to_numpy()
    print(f"candidato - v4: {d.sum():+.3f} | meses que gana {int((d > 1e-9).sum())} / pierde {int((d < -1e-9).sum())} de {len(d)} | "
          f"sin semilla: {out.dif_sin_semilla.sum():+.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
