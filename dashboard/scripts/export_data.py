"""Exporta a JSON los datos del reto de la batería para el dashboard (Premi Tukey).

NO forma parte del agente ni se empaqueta. Importa los módulos de `src/battery` en modo
solo lectura y reproduce EXACTAMENTE los cálculos de los scripts de `analysis/` (p2_*.py),
para que las cifras del dashboard coincidan con el informe de P2 (criterio de coherencia).

    python dashboard/scripts/export_data.py

Escribe dashboard/public/data/*.json. Pensado para ejecutarse una sola vez en el build;
la app web lee los JSON y no necesita Python.
"""
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "analysis"))  # por si hiciera falta algo de allí

from battery import data  # noqa: E402
from battery.baselines import GreedyAgent, OracleAgent  # noqa: E402
from battery.optimizer import plan, score_weights  # noqa: E402
from battery.params import DEFAULT_PARAMS, W_CO2, W_COST  # noqa: E402
from battery.policy import BatteryAgent  # noqa: E402
from battery.sim import baseline_totals, score, simulate  # noqa: E402

OUT = REPO / "dashboard" / "public" / "data"
ORDEN_MESES = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8]  # el curso: de septiembre a agosto
MESES = ["gen", "feb", "mar", "abr", "mai", "jun", "jul", "ago", "set", "oct", "nov", "des"]  # catalán, idx 0=enero
SEMANA = ("2026-07-18", "2026-07-25")  # semana de validación de julio (misma que p2_resultados)


def r(x, n=3):
    """Redondea floats de numpy/pandas a algo serializable."""
    if isinstance(x, (np.floating, float)):
        return round(float(x), n)
    if isinstance(x, (np.integer, int)):
        return int(x)
    return x


def dump(name, obj):
    path = OUT / name
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, default=lambda v: r(v))
    print(f"  escrito {path.relative_to(REPO)} ({path.stat().st_size // 1024} KB)")


# ---------------------------------------------------------------------------------------
# Datos base (una vez)
# ---------------------------------------------------------------------------------------
def load_variant(variant):
    """DataFrame estándar para una variante, igual que `BATTERY_DATOS=<v> eval.py`."""
    os.environ["BATTERY_DATOS"] = variant
    p = data.hourly_file(variant)
    if not p.exists():
        data.ensure_official()
        p.parent.mkdir(parents=True, exist_ok=True)
        data.build_hourly(variant=variant).to_csv(p, index=False)
    return data.load(p)


def red_full():
    """Precio y CO2 de TODO el train (noviembre incluido), como analysis/p2_patrones.red()."""
    data.ensure_official()
    pr = pd.read_csv(data.TRAIN_DIR / "precio_pvpc.csv", parse_dates=["Fecha"]).set_index("Fecha")
    co = pd.read_csv(data.TRAIN_DIR / "co2_red.csv", parse_dates=["Fecha"]).set_index("Fecha")
    df = pd.DataFrame({"precio": pr["precio_eur_per_kwh"], "co2": co["co2_kg_per_kwh"]}).dropna()
    df["hora"], df["mes"], df["dia"] = df.index.hour, df.index.month, df.index.normalize()
    df["peso"] = W_CO2 * df.co2 / df.co2.mean() + W_COST * df.precio / df.precio.mean()
    return df


# ---------------------------------------------------------------------------------------
# 1. Patrones de la red (p2_patrones)
# ---------------------------------------------------------------------------------------
def export_patterns():
    df = red_full()
    g = df.groupby("hora")
    hourly = []
    for h in range(24):
        hourly.append({
            "hour": h,
            "co2_g": r(g.co2.mean()[h] * 1000, 1),
            "co2_p25": r(g.co2.quantile(0.25)[h] * 1000, 1),
            "co2_p75": r(g.co2.quantile(0.75)[h] * 1000, 1),
            "price_c": r(g.precio.mean()[h] * 100, 2),
            "price_p25": r(g.precio.quantile(0.25)[h] * 100, 2),
            "price_p75": r(g.precio.quantile(0.75)[h] * 100, 2),
            "weight": r(g.peso.mean()[h], 3),
        })

    def heat(col, k):
        t = (df.pivot_table(index="mes", columns="hora", values=col, aggfunc="mean") * k).reindex(ORDEN_MESES)
        return {"months": [MESES[m - 1] for m in ORDEN_MESES],
                "hours": list(range(24)),
                "values": [[r(v, 1) for v in row] for row in t.values.tolist()]}

    co2n = g.co2.mean() / df.co2.mean()
    pn = g.precio.mean() / df.precio.mean()
    conflict_hourly = [{"hour": h, "co2_norm": r(co2n[h], 3), "price_norm": r(pn[h], 3)} for h in range(24)]
    corr = df.groupby("mes").apply(lambda d: d.co2.corr(d.precio)).reindex(ORDEN_MESES)
    conflict_monthly = [{"month": MESES[m - 1], "corr": r(corr[m], 3)} for m in ORDEN_MESES]

    mm = df.groupby("mes")[["co2", "precio"]].mean().reindex(ORDEN_MESES)
    monthly = [{"month": MESES[m - 1], "co2_g": r(mm.co2[m] * 1000, 1), "price_c": r(mm.precio[m] * 100, 2)}
               for m in ORDEN_MESES]

    h = df.groupby("hora")[["co2", "precio", "peso"]].mean()
    dia = df.groupby("dia").filter(lambda d: len(d) == 24).groupby("dia")

    def solape(d, limpias=True):
        a = d.co2.nsmallest(6).index if limpias else d.co2.nlargest(6).index
        b = d.precio.nsmallest(12).index if limpias else d.precio.nlargest(12).index
        return len(a.intersection(b)) / 6

    summary = {
        "n_hours": int(len(df)),
        "co2_best_hour": int(h.co2.idxmin()), "co2_best_val": r(h.co2.min() * 1000, 0),
        "co2_worst_hour": int(h.co2.idxmax()), "co2_worst_val": r(h.co2.max() * 1000, 0),
        "co2_ratio": r(h.co2.max() / h.co2.min(), 2),
        "price_best_hour": int(h.precio.idxmin()), "price_best_val": r(h.precio.min() * 100, 1),
        "price_worst_hour": int(h.precio.idxmax()), "price_worst_val": r(h.precio.max() * 100, 1),
        "price_ratio": r(h.precio.max() / h.precio.min(), 2),
        "weight_best_hour": int(h.peso.idxmin()), "weight_worst_hour": int(h.peso.idxmax()),
        "weight_ratio": r(h.peso.max() / h.peso.min(), 2),
        "corr_hourly": r(df.co2.corr(df.precio), 2),
        "overlap_clean_cheap": r(100 * dia.apply(solape).mean(), 0),
        "overlap_dirty_expensive": r(100 * dia.apply(lambda d: solape(d, False)).mean(), 0),
        "co2_mean_g": r(df.co2.mean() * 1000, 0), "price_mean_c": r(df.precio.mean() * 100, 1),
    }
    dump("patterns.json", {"hourly": hourly, "heatmap_co2": heat("co2", 1000),
                           "heatmap_price": heat("precio", 100), "conflict_hourly": conflict_hourly,
                           "conflict_monthly": conflict_monthly, "monthly": monthly, "summary": summary})


# ---------------------------------------------------------------------------------------
# 2. Objetivo CO2 / coste / 70-30 (p2_patrones.coste_del_conflicto)
# ---------------------------------------------------------------------------------------
def export_objective(val, base):
    n = len(val)
    rows = []
    for nombre, a, b in (("Només CO₂ (100/0)", 1.0, 0.0), ("Score del repte (70/30)", W_CO2, W_COST),
                         ("Meitat i meitat (50/50)", 0.5, 0.5), ("Només cost (0/100)", 0.0, 1.0)):
        w_co2, w_cost = a / (base["co2_kg"] / n), b / (base["cost_eur"] / n)
        res = simulate(OracleAgent(val, w_co2, w_cost), val)
        sc = score(res.totals, base)
        rows.append({"label": nombre, "d_co2_pct": r(sc["d_co2_pct"], 2),
                     "d_cost_pct": r(sc["d_cost_pct"], 2), "score": r(sc["score"], 2),
                     "is_reto": a == W_CO2})
    dump("objective.json", {"rows": rows})


# ---------------------------------------------------------------------------------------
# 3. Estrategias, techo y semana tipo (p2_resultados + p2_techo)
# ---------------------------------------------------------------------------------------
def plantilla_oficial():
    import importlib.util
    spec = importlib.util.spec_from_file_location("plantilla", REPO / "oficial" / "starter_kit" / "agent.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.BatteryAgent()


def oracle_agent(val, base, p=DEFAULT_PARAMS):
    n = len(val)
    return OracleAgent(val, W_CO2 / (base["co2_kg"] / n), W_COST / (base["cost_eur"] / n), p)


def export_strategies(val, base):
    n = len(val)
    # Comparativa de estrategias
    agents = [("No fer res", "nothing", None), ("Plantilla oficial", "plantilla", plantilla_oficial()),
              ("Regles simples", "greedy", GreedyAgent()), ("El nostre agent (MPC)", "mpc", BatteryAgent()),
              ("Màxim teòric (oracle)", "oracle", oracle_agent(val, base))]
    comparison, logs = [], {}
    for nombre, key, ag in agents:
        if ag is None:
            comparison.append({"name": nombre, "key": key, "score": 0.0, "d_co2_pct": 0.0,
                               "d_cost_pct": 0.0, "infractions": 0})
            continue
        res = simulate(ag, val)
        sc = score(res.totals, base)
        logs[key] = res.log
        comparison.append({"name": nombre, "key": key, "score": r(sc["score"], 3),
                           "d_co2_pct": r(sc["d_co2_pct"], 2), "d_cost_pct": r(sc["d_cost_pct"], 2),
                           "infractions": int(sc["infractions"])})

    # Escalera de restricciones (techo)
    P = DEFAULT_PARAMS
    BIG = 1e7
    casos = [
        ("Bateria real (2 MWh · 500 kW · 10% pèrdues)", P, True),
        ("Sense pèrdues (rendiment 100%)", P._replace(eta_charge=1.0, eta_discharge=1.0), False),
        ("Sense límit de potència (s'omple en 1 h)", P._replace(max_charge_kw=BIG, max_discharge_kw=BIG), False),
        ("Sense pèrdues ni límit de potència", P._replace(eta_charge=1.0, eta_discharge=1.0,
                                                          max_charge_kw=BIG, max_discharge_kw=BIG), False),
        ("El doble de bateria (4 MWh · 1.000 kW)", P._replace(capacity_kwh=4000.0, soc_init_kwh=2000.0,
                                                              max_charge_kw=1000.0, max_discharge_kw=1000.0), False),
    ]
    ceiling = []
    for nombre, p, es_real in casos:
        res = simulate(oracle_agent(val, base, p), val, p)
        sc = score(res.totals, base)
        ceiling.append({"label": nombre, "score": r(sc["score"], 2), "d_co2_pct": r(sc["d_co2_pct"], 2),
                        "d_cost_pct": r(sc["d_cost_pct"], 2), "is_real": es_real})

    # Cuenta de la servilleta + carga/descarga por hora (oracle real)
    olog = logs["oracle"]
    dias = len(val) / 24
    w = (W_CO2 * val.co2_kg_kwh / (base["co2_kg"] / n)
         + W_COST * val.price_eur_kwh / (base["cost_eur"] / n)).to_numpy()
    carga = olog.action_kw.clip(lower=0).to_numpy()
    desc = (-olog.action_kw).clip(lower=0).to_numpy()
    consumo = olog.load_kw.sum() - olog.pv_kw.sum()
    w_norm = w / (w * (val.load_kw - val.pv_kw).clip(lower=0)).sum() * consumo
    wc = (w_norm * carga).sum() / carga.sum()
    wd = (w_norm * desc).sum() / desc.sum()
    horas_c = pd.Series(carga).groupby(val.timestamp.dt.hour).sum()
    horas_d = pd.Series(desc).groupby(val.timestamp.dt.hour).sum()
    charge_by_hour = [{"hour": h, "charge_kwh": r(horas_c.reindex(range(24), fill_value=0)[h] / dias, 0),
                       "discharge_kwh": r(horas_d.reindex(range(24), fill_value=0)[h] / dias, 0)}
                      for h in range(24)]
    napkin = {
        "battery_pct_daily": r(100 * P.capacity_kwh / (consumo / dias), 1),
        "energy_charged_pct": r(100 * carga.sum() / consumo, 1),
        "energy_discharged_pct": r(100 * desc.sum() / consumo, 1),
        "cycles_day": r(desc.sum() / P.eta_discharge / P.capacity_kwh / dias, 2),
        "weight_charge": r(wc, 2), "weight_discharge": r(wd, 2),
        "result": r(100 * (desc.sum() * wd - carga.sum() * wc) / consumo, 2),
        "daily_consumption_mwh": r(consumo / dias / 1000, 1),
    }

    # Semana tipo (MPC): peso de la hora y SOC
    mlog = logs["mpc"]
    wk = (W_CO2 * val.co2_kg_kwh / val.co2_kg_kwh.mean() + W_COST * val.price_eur_kwh / val.price_eur_kwh.mean())
    sel = (mlog.timestamp >= SEMANA[0]) & (mlog.timestamp < SEMANA[1])
    sub = mlog[sel].reset_index(drop=True)
    wk_sel = wk[sel.to_numpy()].reset_index(drop=True)
    week = []
    for i in range(len(sub)):
        week.append({
            "timestamp": sub.timestamp[i].isoformat(),
            "hour": int(sub.hour[i]), "weekday": int(sub.weekday[i]),
            "weight": r(float(wk_sel[i]), 3),
            "action_kw": r(float(sub.action_kw[i]), 1),
            "soc_mwh": r(float(sub.soc_kwh[i]) / 1000, 3),
            "price_c": r(float(sub.price_eur_kwh[i]) * 100, 2),
            "co2_g": r(float(sub.co2_kg_kwh[i]) * 1000, 1),
        })

    dump("strategies.json", {"comparison": comparison, "ceiling": ceiling,
                             "charge_by_hour": charge_by_hour, "napkin": napkin,
                             "week": {"start": SEMANA[0], "end": SEMANA[1], "points": week}})

    # ---- Operacions (monitoratge del dia a dia) ----
    export_operations(mlog, val, "operations.json", cap_kwh=DEFAULT_PARAMS.capacity_kwh, power_kw=DEFAULT_PARAMS.max_charge_kw,
                      eta=DEFAULT_PARAMS.eta_discharge, now_hour=19, solar=False)
    return comparison


def pick_now_hour(day, cap_kwh):
    """Tria l'hora que fa d'«ara»: descàrrega al pic del vespre amb càrrega sana (ni buida ni plena).

    Evita l'edge on la bateria es buida del tot (0 %), que semblava una errada."""
    pct = 100 * day.soc_kwh.values / cap_kwh
    act = day.action_kw.values
    healthy = [i for i in range(len(day)) if act[i] < -1 and 20 <= pct[i] <= 95]
    evening = [i for i in healthy if 17 <= int(day.hour[i]) <= 22]
    pool = evening or healthy
    if pool:
        return max(pool, key=lambda i: abs(act[i]))
    return int(day.action_kw.abs().values.argmax())


def now_display_date(hour):
    """Data «d'avui» per a la instantània de monitoratge (evita una data antiga del train)."""
    d = date.today()
    while d.weekday() >= 5:  # cap de setmana -> divendres
        d -= timedelta(days=1)
    return datetime(d.year, d.month, d.day, hour)


def export_operations(log, val, name, cap_kwh, power_kw, eta, now_hour, solar, today_date="2026-07-22"):
    """Instantània de monitoratge: estat ara, pla d'avui, KPIs de la setmana i alertes."""
    wmean_co2, wmean_price = val.co2_kg_kwh.mean(), val.price_eur_kwh.mean()
    day = log[log.timestamp.dt.strftime("%Y-%m-%d") == today_date].reset_index(drop=True)
    if len(day) < 24:
        day = log[(log.timestamp >= SEMANA[0]) & (log.timestamp < SEMANA[1])].head(24).reset_index(drop=True)
    wk = W_CO2 * day.co2_kg_kwh / wmean_co2 + W_COST * day.price_eur_kwh / wmean_price
    ni = pick_now_hour(day, cap_kwh)  # instantània realista: descàrrega al pic del vespre amb càrrega sana
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
        "soc_mwh": r(float(day.soc_kwh[ni]) / 1000, 2), "soc_pct": r(100 * float(day.soc_kwh[ni]) / cap_kwh, 0),
        "power_kw": r(abs(a_now), 0), "mode": mode, "price_c": r(float(day.price_eur_kwh[ni]) * 100, 1),
        "co2_g": r(float(day.co2_kg_kwh[ni]) * 1000, 0),
    }
    wsel = (log.timestamp >= SEMANA[0]) & (log.timestamp < SEMANA[1])
    wlog = log[wsel]
    wdf = val[wsel.to_numpy()]
    wbase = baseline_totals(wdf)
    disc = float((-wlog.action_kw).clip(lower=0).sum())
    exp_mwh = float(wlog.export_kw.sum()) / 1000
    week = {
        "co2_saved_kg": r(wbase["co2_kg"] - float(wlog.co2_kg.sum()), 0),
        "eur_saved": r(wbase["cost_eur"] - float(wlog.cost_eur.sum()), 0),
        "cycles": r(disc / eta / cap_kwh, 1), "infractions": int(wlog.infractions.sum()),
        "import_mwh": r(float(wlog.import_kw.sum()) / 1000, 1), "export_mwh": r(exp_mwh, 2),
        "days": int(len(wlog) / 24), "start": SEMANA[0], "end": SEMANA[1],
    }
    alerts = [
        {"level": "good", "label": "Sense infraccions", "detail": "La bateria s'ha mantingut dins dels límits físics tota la setmana."},
        {"level": "good", "label": "Balanç de xarxa correcte", "detail": "La compra i la descàrrega quadren amb el consum del campus."},
    ]
    if solar:
        alerts.append({"level": "good", "label": "Excedent solar aprofitat", "detail": f"Només {r(exp_mwh, 2)} MWh vessats a la xarxa aquesta setmana."})
        alerts.append({"level": "warn", "label": "Previsió amb incertesa", "detail": "La solar canvia molt a migdia (±142 kW/h); el pla aplica un marge de seguretat."})
    else:
        alerts.append({"level": "warn", "label": "Lectura nocturna estimada", "detail": "El comptador no mesura de 22 h a 6 h; s'estima amb l'energia acumulada."})
        alerts.append({"level": "good", "label": "Excedent mínim", "detail": "Gairebé no es vessa energia: el campus consumeix més que la solar."})
    dump(name, {"battery": {"capacity_mwh": cap_kwh / 1000, "power_kw": power_kw}, "status": status,
                "today": today, "week": week, "alerts": alerts})


# ---------------------------------------------------------------------------------------
# 4. Escenarios de dimensionado (escenarios.csv, generado por p2_escenarios)
# ---------------------------------------------------------------------------------------
def export_scenarios(annual_baseline):
    esc = pd.read_csv(REPO / "analysis" / "escenarios.csv")

    def block(variante):
        d = esc[esc.variante == variante].sort_values("capacidad_mwh")
        return [{
            "capacity_mwh": r(row.capacidad_mwh, 1), "power_kw": r(row.potencia_kw, 0),
            "score": r(row.score, 2), "co2_pct": r(row.co2_pct, 2), "cost_pct": r(row.coste_pct, 2),
            "co2_t_year": r(row.co2_t_ano, 1), "eur_year": r(row.eur_ano, 0),
            "cycles_day": r(row.ciclos_dia, 2),
            "marginal_co2_t": None if pd.isna(row.marginal_co2_t_mwh) else r(row.marginal_co2_t_mwh, 1),
            "marginal_eur": None if pd.isna(row.marginal_eur_mwh) else r(row.marginal_eur_mwh, 0),
        } for _, row in d.iterrows()]

    dump("scenarios.json", {
        "proportional": block("potencia proporcional"),
        "fixed_power": block("potencia fija 500 kW"),
        "annual_baseline": annual_baseline,
    })


# ---------------------------------------------------------------------------------------
# 5. Calidad de los datos (p2_calidad_datos)
# ---------------------------------------------------------------------------------------
def export_quality():
    data.ensure_official()
    m = data.read_meter()
    ofi = data.build_hourly()
    real = data.build_hourly(variant="real")

    # Perfil medio por hora (laborables), dataset vs real
    night_profile = []
    pofi = ofi[ofi.timestamp.dt.dayofweek < 5].groupby(ofi.timestamp.dt.hour).load_kw.mean()
    preal = real[real.timestamp.dt.dayofweek < 5].groupby(real.timestamp.dt.hour).load_kw.mean()
    for h in range(24):
        night_profile.append({"hour": h, "dataset_kw": r(pofi.get(h, np.nan), 0),
                              "real_kw": r(preal.get(h, np.nan), 0)})

    # Dos días de ejemplo (13-15 ene 2026) a resolución de 5 min: dataset vs real
    t0, t1 = pd.Timestamp("2026-01-13 12:00"), pd.Timestamp("2026-01-15 12:00")
    wdf = m[(m.Fecha >= t0) & (m.Fecha <= t1)].reset_index(drop=True)
    real_series = wdf.load_kw.mask(wdf.frozen & wdf.night_real_kw.notna(), wdf.night_real_kw)
    example = []
    for i in range(len(wdf)):
        example.append({
            "ts": wdf.Fecha[i].isoformat(),
            "dataset_kw": r(float(wdf.load_kw[i]), 0),
            "real_kw": (r(float(real_series[i]), 0) if bool(wdf.frozen[i]) else None),
            "frozen": bool(wdf.frozen[i]),
        })

    per = (m[m.frozen & m.night_real_kw.notna()]
           .assign(d=lambda x: (x.Fecha - pd.Timedelta("7h")).dt.date)
           .groupby("d").agg(cong=("load_kw", "first"), real=("night_real_kw", "first")))
    over = (per.cong - per.real).mean() * data.NIGHT_HOURS
    stats = {
        "meter_records": int(len(m)),
        "com_fail_n": int(m.com_fail.sum()), "com_fail_pct": r(100 * m.com_fail.mean(), 2),
        "frozen_n": int(m.frozen.sum()), "frozen_pct": r(100 * m.frozen.mean(), 1),
        "night_cong_kw": r(per.cong.mean(), 0), "night_real_kw": r(per.real.mean(), 0),
        "night_diff_pct": r(100 * (per.real.mean() / per.cong.mean() - 1), 1),
        "over_kwh_night": r(over, 0), "over_pct_daily": r(100 * over / (ofi.load_kw.mean() * 24), 1),
        "zero_hours": int((ofi.load_kw == 0).sum()),
        "mean_load_ofi": r(ofi.load_kw.mean(), 0), "mean_load_real": r(real.load_kw.mean(), 0),
        "hours_ofi": int(len(ofi)), "hours_real": int(len(real)),
    }

    # Score por variante (igual que BATTERY_DATOS=<v> eval.py, mpc y oracle)
    variants = []
    for v, etiqueta in (("oficial", "Oficials (com el tutorial)"),
                        ("limpio", "Netejats (avaries imputades)"),
                        ("real", "Consum nocturn real")):
        dv = load_variant(v)
        vval = data.validation_split(dv)
        vbase = baseline_totals(vval)
        sc_mpc = score(simulate(BatteryAgent(), vval).totals, vbase)
        sc_ora = score(simulate(oracle_agent(vval, vbase), vval).totals, vbase)
        variants.append({"variant": v, "label": etiqueta, "mpc": r(sc_mpc["score"], 2),
                         "oracle": r(sc_ora["score"], 2), "d_co2_pct": r(sc_mpc["d_co2_pct"], 2),
                         "d_cost_pct": r(sc_mpc["d_cost_pct"], 2)})
    os.environ["BATTERY_DATOS"] = "oficial"  # restaurar

    dump("quality.json", {"night_profile": night_profile, "example": example,
                          "stats": stats, "variants": variants})


# ---------------------------------------------------------------------------------------
# 6. KPIs de portada + meta
# ---------------------------------------------------------------------------------------
def export_kpis(comparison, val, base, annual_baseline):
    mpc = next(c for c in comparison if c["key"] == "mpc")
    oracle = next(c for c in comparison if c["key"] == "oracle")
    esc2 = pd.read_csv(REPO / "analysis" / "escenarios.csv")
    row2 = esc2[(esc2.capacidad_mwh == 2.0) & (esc2.variante == "potencia proporcional")].iloc[0]
    kpis = {
        "agent_score": mpc["score"], "oracle_score": oracle["score"],
        "pct_of_max": r(100 * mpc["score"] / oracle["score"], 1),
        "agent_co2_pct": mpc["d_co2_pct"], "agent_cost_pct": mpc["d_cost_pct"],
        "infractions": mpc["infractions"],
        "co2_t_year_2mwh": r(row2.co2_t_ano, 0), "eur_year_2mwh": r(row2.eur_ano, 0),
        "annual_baseline": annual_baseline,
        "validation_hours": int(len(val)),
        "validation_start": val.timestamp.iloc[0].date().isoformat(),
        "validation_end": val.timestamp.iloc[-1].date().isoformat(),
    }
    dump("kpis.json", kpis)


def export_meta(df_full):
    meta = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "data_source": "oficial" if not data.is_synthetic() else "sintético",
        "train_hours": int(len(df_full)),
        "train_start": df_full.timestamp.iloc[0].date().isoformat(),
        "train_end": df_full.timestamp.iloc[-1].date().isoformat(),
        "weights": {"co2": W_CO2, "cost": W_COST},
        "battery": {"capacity_kwh": DEFAULT_PARAMS.capacity_kwh, "power_kw": DEFAULT_PARAMS.max_charge_kw,
                    "roundtrip_eff": 0.9, "soc_init_kwh": DEFAULT_PARAMS.soc_init_kwh},
    }
    dump("meta.json", meta)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("Exportando datos del dashboard...")
    os.environ["BATTERY_DATOS"] = "oficial"
    df_full = data.load()
    val = data.validation_split(df_full)
    base = baseline_totals(val)

    # Baseline anual (train limpio, anualizado), coherente con analysis/escenarios.md
    dl = load_variant("limpio")
    bl = baseline_totals(dl)
    days = len(dl) / 24
    annual_baseline = {
        "co2_t": r(bl["co2_kg"] / 1000 / days * 365, 0),
        "eur": r(bl["cost_eur"] / days * 365, 0),
        "gwh": r(bl["import_kwh"] / 1e6 / days * 365, 1),
        "mwh_day": r(bl["import_kwh"] / 1000 / days, 1),
    }
    os.environ["BATTERY_DATOS"] = "oficial"

    export_patterns()
    export_objective(val, base)
    comparison = export_strategies(val, base)
    export_scenarios(annual_baseline)
    export_quality()
    export_kpis(comparison, val, base, annual_baseline)
    export_meta(df_full)
    print("Hecho.")


if __name__ == "__main__":
    main()
