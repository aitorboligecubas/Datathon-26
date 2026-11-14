"""Por qué el ahorro máximo es de ~6 %: tamaño, pérdidas y potencia de la batería. Owner: P2.

    python analysis/p2_techo.py

Todo con el oracle (LP con información perfecta = óptimo exacto del score) sobre la validación oficial,
cambiando una restricción física cada vez. Escribe analysis/figs/techo_*.png.
"""
import math

import numpy as np
import pandas as pd
from p2_estilo import AZUL, GRIS, TINTA, TINTA2, guardar, plt

from battery import data
from battery.baselines import OracleAgent
from battery.params import DEFAULT_PARAMS, W_CO2, W_COST
from battery.sim import baseline_totals, score, simulate

SIN_LIMITE = 1e7   # "sin límite" de potencia o de capacidad


def oracle(val: pd.DataFrame, p=DEFAULT_PARAMS):
    base = baseline_totals(val)
    n = len(val)
    agent = OracleAgent(val, W_CO2 / (base["co2_kg"] / n), W_COST / (base["cost_eur"] / n), p)
    res = simulate(agent, val, p)
    return score(res.totals, base), res.log, base


def main() -> None:
    val = data.validation_split(data.load())
    base = baseline_totals(val)
    dias = len(val) / 24
    P = DEFAULT_PARAMS
    sc, log, _ = oracle(val)

    # 1) La cuenta de la servilleta: energía movida x diferencia de peso.
    w = (W_CO2 * val.co2_kg_kwh / (base["co2_kg"] / len(val))
         + W_COST * val.price_eur_kwh / (base["cost_eur"] / len(val))).to_numpy()   # peso por kWh comprado
    carga = log.action_kw.clip(lower=0).to_numpy()
    desc = (-log.action_kw).clip(lower=0).to_numpy()
    consumo = log.load_kw.sum() - log.pv_kw.sum()
    w_norm = w / (w * (val.load_kw - val.pv_kw).clip(lower=0)).sum() * consumo   # 1 = hora media ponderada
    wc, wd = (w_norm * carga).sum() / carga.sum(), (w_norm * desc).sum() / desc.sum()
    print(f"validación: {len(val)} h ({dias:.0f} días); consumo neto {consumo / dias / 1000:.1f} MWh/día")
    print(f"batería: {P.capacity_kwh / 1000:.0f} MWh = {100 * P.capacity_kwh / (consumo / dias):.1f} % del consumo diario")
    print(f"oracle: score {sc['score']:.2f} (CO2 {sc['d_co2_pct']:.2f} %, coste {sc['d_cost_pct']:.2f} %)")
    print(f"energía cargada: {carga.sum() / dias:.0f} kWh/día ({100 * carga.sum() / consumo:.1f} % del consumo); "
          f"descargada: {desc.sum() / dias:.0f} kWh/día ({100 * desc.sum() / consumo:.1f} %)")
    print(f"ciclos completos al día: {desc.sum() / P.eta_discharge / P.capacity_kwh / dias:.2f}")
    print(f"peso medio al cargar: {wc:.2f}; al descargar: {wd:.2f} (1 = hora media)")
    aprox = 100 * (desc.sum() * wd - carga.sum() * wc) / consumo
    print(f"cuenta: {100 * desc.sum() / consumo:.1f} % x {wd:.2f} - {100 * carga.sum() / consumo:.1f} % x {wc:.2f} "
          f"= {aprox:.2f} puntos")
    horas_c = pd.Series(carga).groupby(val.timestamp.dt.hour).sum()
    horas_d = pd.Series(desc).groupby(val.timestamp.dt.hour).sum()
    print("carga por hora (% del total):", (100 * horas_c / horas_c.sum()).round(0).astype(int).to_dict())
    print("descarga por hora (% del total):", (100 * horas_d / horas_d.sum()).round(0).astype(int).to_dict())

    # 2) Quitar las restricciones de una en una.
    casos = [
        ("Batería real: 2 MWh, 500 kW, 10 % de pérdidas", P),
        ("Sin pérdidas (rendimiento del 100 %)", P._replace(eta_charge=1.0, eta_discharge=1.0)),
        ("Sin límite de potencia (se llena en 1 h)", P._replace(max_charge_kw=SIN_LIMITE, max_discharge_kw=SIN_LIMITE)),
        ("Sin pérdidas y sin límite de potencia", P._replace(eta_charge=1.0, eta_discharge=1.0,
                                                           max_charge_kw=SIN_LIMITE, max_discharge_kw=SIN_LIMITE)),
        ("Doble de capacidad y de potencia (4 MWh, 1.000 kW)", P._replace(capacity_kwh=4000.0, soc_init_kwh=2000.0,
                                                                         max_charge_kw=1000.0, max_discharge_kw=1000.0)),
    ]
    filas = []
    for nombre, p in casos:
        s, _, _ = oracle(val, p)
        filas.append((nombre, s["score"], s["d_co2_pct"], s["d_cost_pct"], s["infractions"]))
    # Flexibilidad total: todo el consumo de cada día se compra en su mejor hora (cota absurda, de referencia).
    d = val.assign(net=(val.load_kw - val.pv_kw).clip(lower=0), w=w, dia=val.timestamp.dt.normalize())
    flex = 100 * (1 - (d.groupby("dia").net.sum() * d.groupby("dia").w.min()).sum() / (d.net * d.w).sum())
    filas.append(("Flexibilidad total: todo el consumo del día en su mejor hora", flex, np.nan, np.nan, 0))
    t = pd.DataFrame(filas, columns=["caso", "score", "ΔCO2 %", "ΔCoste %", "infr."])
    print(t.round(2).to_string(index=False))

    # Figura: escalera de restricciones.
    orden = [0, 1, 2, 3, 4]
    fig, ax = plt.subplots(figsize=(11, 4.4))
    y = np.arange(len(orden))[::-1]
    vals = [t.score[i] for i in orden]
    colores = [AZUL] + [GRIS] * (len(orden) - 1)
    ax.barh(y, vals, color=colores, height=0.62)
    for yi, v, i in zip(y, vals, orden):
        ax.text(v + 0.12, yi, f"{v:.1f}".replace(".", ","), va="center", color=TINTA, fontsize=12,
                fontweight="bold" if i == 0 else "normal")
    ax.set_yticks(y, [t.caso[i] for i in orden])
    ax.set_xlabel("Score máximo posible (óptimo con información perfecta)")
    ax.set_xlim(0, max(vals) * 1.12)
    ax.grid(axis="y", visible=False)
    ax.set_title("El techo del 6 % lo pone el tamaño de la batería, no el algoritmo")
    guardar(fig, "techo_restricciones.png")

    # Figura: cuándo carga y cuándo descarga el óptimo.
    fig, ax = plt.subplots(figsize=(11, 4.2))
    h = np.arange(24)
    ax.bar(h, horas_c.reindex(h, fill_value=0) / dias, color=AZUL, width=0.75, label="Carga")
    ax.bar(h, -horas_d.reindex(h, fill_value=0) / dias, color="#eb6834", width=0.75, label="Descarga")
    ax.axhline(0, color=TINTA2, lw=1)
    ax.set_xticks(range(0, 24, 3))
    ax.set_xlabel("Hora del día")
    ax.set_ylabel("kWh por día (media)")
    ax.set_title("Dos ciclos al día: carga a mediodía y de madrugada, descarga al anochecer y al amanecer")
    ax.legend(loc="upper right", ncol=2)
    guardar(fig, "techo_carga_descarga.png")


if __name__ == "__main__":
    main()
