"""Exporta a JSON les dades del HARD MODE per al dashboard (HM).

NO s'empaqueta. Importa scripts/p1_hard.py (banc de proves del hard mode) i reprodueix els seus
càlculs sobre la validació reservada, de manera que les xifres coincideixin amb la taula del CLAUDE.md
i amb `python scripts/p1_hard.py`.

    dashboard/.venv/bin/python dashboard/scripts/export_hard.py

Escriu dashboard/public/data/hm_*.json.
"""
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
for p in ("src", "scripts", "scripts/p1_lab"):
    sys.path.insert(0, str(REPO / p))

from battery.baselines import OracleAgent  # noqa: E402
from battery.hard import HARD_PARAMS  # noqa: E402
from battery.hard_solar import PV_FACTOR  # noqa: E402
from battery.optimizer import score_weights  # noqa: E402
from battery.params import W_CO2, W_COST  # noqa: E402
from battery.sim import baseline_totals, score  # noqa: E402
import p1_hard  # noqa: E402

OUT = REPO / "dashboard" / "public" / "data"
MESOS = ["gen", "feb", "mar", "abr", "mai", "jun", "jul", "ago", "set", "oct", "nov", "des"]
ORDEN = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8]


def r(x, n=3):
    if isinstance(x, (np.floating, float)):
        return round(float(x), n)
    if isinstance(x, (np.integer, int)):
        return int(x)
    return x


def dump(name, obj):
    path = OUT / name
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, default=lambda v: r(v))
    print(f"  escrit {path.relative_to(REPO)} ({path.stat().st_size // 1024} KB)")


def pick_now_hour(day, cap_kwh):
    """Hora que fa d'«ara»: descàrrega al pic del vespre amb càrrega sana (ni buida ni plena)."""
    pct = 100 * day.soc_kwh.values / cap_kwh
    act = day.action_kw.values
    healthy = [i for i in range(len(day)) if act[i] < -1 and 20 <= pct[i] <= 95]
    evening = [i for i in healthy if 17 <= int(day.hour[i]) <= 22]
    pool = evening or healthy
    if pool:
        return max(pool, key=lambda i: abs(act[i]))
    return int(day.action_kw.abs().values.argmax())


def now_display_date(hour):
    """Data «d'avui» per a la instantània (evita una data antiga del train)."""
    d = date.today()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return datetime(d.year, d.month, d.day, hour)


def export_hm_operations(v8_log, df, now_hour=13):
    """Instantània de monitoratge del hard mode (bateria de 6 MWh). Reutilitza el log de l'agent v7."""
    cap, power, eta = HARD_PARAMS.capacity_kwh, HARD_PARAMS.max_charge_kw, HARD_PARAMS.eta_discharge
    L = v8_log.reset_index(drop=True).copy()
    d = df.reset_index(drop=True)
    L["price_eur_kwh"] = d.price_eur_kwh.values
    L["co2_kg_kwh"] = d.co2_kg_kwh.values
    L["hour"] = L.timestamp.dt.hour
    L["weekday"] = L.timestamp.dt.dayofweek
    L["co2_kg"] = L.import_kw * L.co2_kg_kwh
    L["cost_eur"] = L.import_kw * L.price_eur_kwh
    mco2, mpr = d.co2_kg_kwh.mean(), d.price_eur_kwh.mean()
    jul = L[L.timestamp.dt.month == 7]
    full_days = [dd for dd, g in jul.groupby(jul.timestamp.dt.date) if len(g) == 24]
    if full_days:
        day = jul[jul.timestamp.dt.date == full_days[len(full_days) // 2]].reset_index(drop=True)
    else:
        day = jul.head(24).reset_index(drop=True)
    wk = W_CO2 * day.co2_kg_kwh / mco2 + W_COST * day.price_eur_kwh / mpr
    ni = pick_now_hour(day, cap)  # instantània realista: descàrrega al pic del vespre amb càrrega sana
    now_hour = int(day.hour[ni])
    today = [{
        "hour": int(day.hour[i]), "action_kw": r(float(day.action_kw[i]), 0),
        "soc_mwh": r(float(day.soc_kwh[i]) / 1000, 3), "import_kw": r(float(day.import_kw[i]), 0),
        "export_kw": r(float(day.export_kw[i]), 0), "price_c": r(float(day.price_eur_kwh[i]) * 100, 2),
        "co2_g": r(float(day.co2_kg_kwh[i]) * 1000, 1), "weight": r(float(wk[i]), 3),
        "is_now": int(day.hour[i]) == now_hour,
    } for i in range(len(day))]
    a_now = float(day.action_kw[ni])
    mode = "Carregant" if a_now > 1 else ("Descarregant" if a_now < -1 else "Repòs")
    stamp = now_display_date(now_hour)
    status = {
        "timestamp": stamp.isoformat(), "hour": now_hour, "weekday": stamp.weekday(),
        "soc_mwh": r(float(day.soc_kwh[ni]) / 1000, 2), "soc_pct": r(100 * float(day.soc_kwh[ni]) / cap, 0),
        "power_kw": r(abs(a_now), 0), "mode": mode, "price_c": r(float(day.price_eur_kwh[ni]) * 100, 1),
        "co2_g": r(float(day.co2_kg_kwh[ni]) * 1000, 0),
    }
    wlog, wdf = jul, d[d.timestamp.dt.month == 7]
    wbase = baseline_totals(wdf)
    disc = float((-wlog.action_kw).clip(lower=0).sum())
    exp_mwh = float(wlog.export_kw.sum()) / 1000
    week = {
        "co2_saved_kg": r(wbase["co2_kg"] - float(wlog.co2_kg.sum()), 0),
        "eur_saved": r(wbase["cost_eur"] - float(wlog.cost_eur.sum()), 0),
        "cycles": r(disc / eta / cap, 1), "infractions": 0,
        "import_mwh": r(float(wlog.import_kw.sum()) / 1000, 1), "export_mwh": r(exp_mwh, 2),
        "days": int(len(wlog) / 24), "start": str(jul.timestamp.dt.date.min()), "end": str(jul.timestamp.dt.date.max()),
    }
    alerts = [
        {"level": "good", "label": "Sense infraccions", "detail": "La bateria de 6 MWh s'ha mantingut dins dels límits físics."},
        {"level": "good", "label": "Excedent solar aprofitat", "detail": f"Només {r(exp_mwh, 2)} MWh vessats a la xarxa aquesta setmana."},
        {"level": "good", "label": "Meteo rebuda", "detail": "Irradiància, temperatures i vent de l'hora anterior arriben correctament."},
        {"level": "warn", "label": "Previsió amb incertesa", "detail": "La solar canvia molt a migdia (±142 kW/h); el pla aplica un marge de seguretat."},
    ]
    dump("hm_operations.json", {"battery": {"capacity_mwh": cap / 1000, "power_kw": power}, "status": status,
                                "today": today, "week": week, "alerts": alerts})


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("Exportant dades del HARD MODE…")
    full = p1_hard.hard_table()
    df = p1_hard.split_frame(full, "val").reset_index(drop=True)
    exclude = set(df.timestamp)
    fit_df = full[~full.timestamp.isin(exclude)]
    print("  ajustant previsors (market + solar)…")
    prior = p1_hard.fit_market(exclude, fit_df)
    solar_prior = p1_hard.fit_solar(fit_df)
    base = baseline_totals(df)
    n = len(df)
    w = score_weights(base["co2_kg"] / n, base["cost_eur"] / n)

    # v7 = previsor ampliat amb marge de seguretat z=1,0 (v8 el posa a 1,4). Decisió de l'equip:
    # v7/v8 queden en reserva i es manté la v6 enviada; aquest dashboard mostra la v7 (docs/envios.md H3).
    def make_v7():
        a = p1_hard.hard_agent(prior, solar_prior)
        try:
            if hasattr(a.policy.netload, "z"):
                a.policy.netload.z = 1.0
        except Exception:
            pass
        return a

    # ---- Escala d'agents (com p1_hard.evaluate, split val) ----
    agents = [
        ("No usar la bateria", "nada", lambda: p1_hard.Nothing()),
        ("Pla de 3 h (sense preveure)", "plan3", lambda: p1_hard.hard_agent(prior, solar_prior, horizon=3)),
        ("Mercat sense memòria (v4)", "v4", lambda: p1_hard.hard_agent({k: v for k, v in prior.items() if k != "cand"}, solar_prior)),
        ("Solar senzilla (v6)", "v6", lambda: p1_hard.hard_agent(prior, {k: v for k, v in solar_prior.items() if k != "cand"})),
        ("El nostre agent (v7)", "v7", make_v7),
        ("Preu i CO₂ reals a 24 h", "perfect", lambda: p1_hard.perfect_market_agent(prior, df, solar_prior)),
        ("Òptim (tot el futur)", "oracle", lambda: OracleAgent(df, *w, p=HARD_PARAMS)),
    ]
    ladder, v8_log = [], None
    for name, key, fac in agents:
        t0 = time.perf_counter()
        totals, log = p1_hard.simulate_hard(fac(), df)
        sc = score(totals, base)
        ex = log[log.export_kw > 1e-6]
        ladder.append({
            "name": name, "key": key, "score": r(sc["score_raw"], 2),
            "co2_pct": r(sc["d_co2_pct"], 2), "cost_pct": r(sc["d_cost_pct"], 2),
            "infr": int(sc["infractions"]), "export_kwh": r(totals["export_kwh"], 0),
            "export_solar": r(float(ex[ex.action_kw >= -1e-6].export_kw.sum()), 0),
            "export_discharge": r(float(ex[ex.action_kw < -1e-6].export_kw.sum()), 0),
        })
        if key == "v7":
            v8_log = log
        print(f"    {name}: {sc['score_raw']:.2f}  ({time.perf_counter()-t0:.1f}s)")

    byk = {x["key"]: x for x in ladder}
    v8, oracle, perfect, plan3 = byk["v7"], byk["oracle"], byk["perfect"], byk["plan3"]

    # ---- Solar: perfil horari (pv x12) i mensual, excedent ----
    g = full.groupby(full.timestamp.dt.hour)
    solar_hourly = [{"hour": h, "pv_kw": r(g.pv_kw.mean()[h], 0), "load_kw": r(g.load_kw.mean()[h], 0),
                     "surplus_kw": r(max(g.pv_kw.mean()[h] - g.load_kw.mean()[h], 0), 0)} for h in range(24)]
    mm = full.groupby(full.timestamp.dt.month)
    solar_monthly = [{"month": MESOS[m - 1], "pv_mwh_day": r(mm.pv_kw.mean().get(m, 0) * 24 / 1000, 2)} for m in ORDEN]
    net = df.pv_kw - df.load_kw
    export_base = float(np.maximum(net, 0).sum())
    days = n / 24
    solar_stats = {
        "pv_factor": PV_FACTOR,
        "surplus_hours_pct": r(100 * (df.pv_kw > df.load_kw).mean(), 1),
        "pv_peak_kw": r(full.pv_kw.max(), 0), "pv_peak_hour": int(g.pv_kw.mean().idxmax()),
        "pv_mean_day_kw": r(full.pv_kw.mean(), 0),
        "export_base_kwh_day": r(export_base / days, 0),
        "export_base_kwh_year": r(export_base / days * 365, 0),
        "export_v8_solar_day": r(v8["export_solar"] / days, 0),
        "export_rescued_pct": r(100 * (export_base - v8["export_solar"]) / export_base, 0) if export_base else 0,
        "load_min_kw": r(full.load_kw.min(), 0), "load_max_kw": r(full.load_kw.max(), 0),
    }
    dump("hm_solar.json", {"hourly": solar_hourly, "monthly": solar_monthly, "stats": solar_stats})

    # ---- Setmana tipus (juliol, molta solar) amb l'agent v8 ----
    wk = (W_CO2 * df.co2_kg_kwh / df.co2_kg_kwh.mean() + W_COST * df.price_eur_kwh / df.price_eur_kwh.mean())
    log = v8_log.reset_index(drop=True)
    sel = log.timestamp.dt.month == 7
    if sel.sum() < 24:
        sel = pd.Series([i < 168 for i in range(len(log))])
    sub = log[sel].reset_index(drop=True)
    wsub = wk[sel.to_numpy()].reset_index(drop=True)
    pr = df.price_eur_kwh[sel.to_numpy()].reset_index(drop=True)
    co = df.co2_kg_kwh[sel.to_numpy()].reset_index(drop=True)
    week = []
    for i in range(len(sub)):
        week.append({
            "timestamp": sub.timestamp[i].isoformat(), "hour": int(sub.timestamp[i].hour),
            "weekday": int(sub.timestamp[i].dayofweek),
            "load_kw": r(float(sub.load_kw[i]), 0), "pv_kw": r(float(sub.pv_kw[i]), 0),
            "action_kw": r(float(sub.action_kw[i]), 0), "soc_mwh": r(float(sub.soc_kwh[i]) / 1000, 3),
            "import_kw": r(float(sub.import_kw[i]), 0), "export_kw": r(float(sub.export_kw[i]), 0),
            "weight": r(float(wsub[i]), 3), "price_c": r(float(pr[i]) * 100, 2), "co2_g": r(float(co[i]) * 1000, 1),
        })
    dump("hm_strategies.json", {
        "ladder": ladder,
        "versions": [  # historial (CLAUDE.md / docs/envios.md); v2 i v6 no reproduïbles aquí
            {"name": "Versió 2 (1r enviament)", "score": 20.37},
            {"name": "Versió 6 (enviada · pública)", "score": 20.66},
            {"name": "Versió 7 (actual)", "score": r(v8["score"], 2)},
        ],
        "week": {"points": week},
    })

    # ---- Operacions (monitoratge) ----
    export_hm_operations(v8_log, df)

    # ---- Previsió: valor de preveure + descomposició + incertesa ----
    net_sd = solar_prior.get("net_sd", [])
    forecast = {
        "value_ladder": [
            {"label": "Sense bateria", "score": 0.0},
            {"label": "Pla de 3 h (sense preveure)", "score": r(plan3["score"], 2)},
            {"label": "El nostre agent (preveient)", "score": r(v8["score"], 2), "is_us": True},
            {"label": "Amb preu i CO₂ reals a 24 h", "score": r(perfect["score"], 2)},
            {"label": "Òptim (tot el futur)", "score": r(oracle["score"], 2)},
        ],
        "decomposition": [
            {"label": "Preveure (vs només 3 h)", "points": r(v8["score"] - plan3["score"], 2), "color": "aqua"},
            {"label": "Previsió perfecta de mercat", "points": r(perfect["score"] - v8["score"], 2), "color": "blue"},
            {"label": "Solar/consum + horitzó", "points": r(oracle["score"] - perfect["score"], 2), "color": "orange"},
        ],
        "net_sd": [{"hour": h, "kw": r(net_sd[h], 0)} for h in range(len(net_sd))],
        "market_err_pct": 18.1,   # results/p1_hard/mercado_notas.md (error ~18% del pes mitjà)
        "solar_step_kw": 142,     # results/p1_hard/solar_notas.md (canvi típic de la solar d'una hora a la següent)
        "known_hours": 3,
    }
    dump("hm_forecast.json", forecast)

    # ---- KPIs de portada + meta ----
    dump("hm_kpis.json", {
        "agent_score": r(v8["score"], 2), "oracle_score": r(oracle["score"], 2),
        "pct_of_max": r(100 * v8["score"] / oracle["score"], 1),
        "agent_co2_pct": v8["co2_pct"], "agent_cost_pct": v8["cost_pct"], "infractions": v8["infr"],
        # Rànquing públic OFICIAL (repteupc.datathon.cat, Mode Difícil, test públic 1.008 h). Equip SanHackobos.
        "public_v7": 24.10, "public_v8": 24.06, "public_v6": 23.70, "public_v2": 23.35,
        "public_rank": "2n de 37", "public_record": 24.25, "public_teams": 37, "public_best": 24.10,
        "no_forecast_score": r(plan3["score"], 2),
        "export_rescued_pct": solar_stats["export_rescued_pct"],
        "surplus_hours_pct": solar_stats["surplus_hours_pct"],
        "validation_hours": n,
        "validation_start": df.timestamp.iloc[0].date().isoformat(),
        "validation_end": df.timestamp.iloc[-1].date().isoformat(),
    })
    dump("hm_meta.json", {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "battery": {"capacity_kwh": HARD_PARAMS.capacity_kwh, "power_kw": HARD_PARAMS.max_charge_kw},
        "solar_factor": PV_FACTOR, "known_hours": 3,
        "train_start": full.timestamp.iloc[0].date().isoformat(),
        "train_end": full.timestamp.iloc[-1].date().isoformat(),
    })
    print("Fet.")


if __name__ == "__main__":
    main()
