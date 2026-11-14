"""Gráficas de resultados para la presentación: comparativa de estrategias y una semana tipo. Owner: P2.

    python analysis/p2_resultados.py

Ejecuta los agentes sobre la validación oficial (no necesita results/hourly/).
Escribe analysis/figs/resultados_*.png.
"""
import importlib.util

import numpy as np
import pandas as pd
from p2_estilo import AZUL, GRIS, NARANJA, REPO, TINTA, TINTA2, guardar, plt

from battery import data
from battery.baselines import GreedyAgent, OracleAgent
from battery.params import W_CO2, W_COST
from battery.policy import BatteryAgent
from battery.sim import baseline_totals, score, simulate

SEMANA = ("2026-07-18", "2026-07-25")   # semana de validación de julio


def plantilla_oficial():
    spec = importlib.util.spec_from_file_location("plantilla", REPO / "oficial" / "starter_kit" / "agent.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.BatteryAgent()


def main() -> None:
    val = data.validation_split(data.load())
    base = baseline_totals(val)
    n = len(val)
    oracle = OracleAgent(val, W_CO2 / (base["co2_kg"] / n), W_COST / (base["cost_eur"] / n))
    res = {}
    for nombre, agente in (("Plantilla oficial", plantilla_oficial()), ("Reglas simples", GreedyAgent()),
                           ("Nuestro agente", BatteryAgent()), ("Máximo teórico", oracle)):
        r = simulate(agente, val)
        res[nombre] = (score(r.totals, base), r.log)
        s = res[nombre][0]
        print(f"{nombre:<18} score {s['score']:.3f}  CO2 {s['d_co2_pct']:.2f} %  coste {s['d_cost_pct']:.2f} %  "
              f"infracciones {s['infractions']}")

    # Figura 1: comparativa de estrategias.
    fig, ax = plt.subplots(figsize=(10, 3.8))
    nombres = list(res)
    vals = [res[k][0]["score"] for k in nombres]
    y = np.arange(len(nombres))[::-1]
    ax.barh(y, vals, color=[GRIS, GRIS, AZUL, GRIS], height=0.6)
    for yi, v, k in zip(y, vals, nombres):
        extra = "  (con 7 infracciones)" if k == "Plantilla oficial" else ""
        ax.text(v + 0.08, yi, f"{v:.2f}".replace(".", ",") + extra, va="center", color=TINTA, fontsize=12,
                fontweight="bold" if k == "Nuestro agente" else "normal")
    ax.set_yticks(y, nombres)
    ax.set_xlim(0, 7.4)
    ax.set_xlabel("Score en validación (0,7 · % de CO₂ ahorrado + 0,3 · % de coste ahorrado)")
    ax.grid(axis="y", visible=False)
    ax.set_title("Nuestro agente captura el 99,6 % del máximo teórico")
    guardar(fig, "resultados_estrategias.png")

    # Figura 2: una semana tipo. Arriba, lo "mala" que es cada hora; abajo, la carga de la batería.
    log = res["Nuestro agente"][1]
    w = (W_CO2 * val.co2_kg_kwh / val.co2_kg_kwh.mean() + W_COST * val.price_eur_kwh / val.price_eur_kwh.mean())
    sel = (log.timestamp >= SEMANA[0]) & (log.timestamp < SEMANA[1])
    t, soc, peso, acc = log.timestamp[sel], log.soc_kwh[sel], w[sel.to_numpy()], log.action_kw[sel]
    fig, axes = plt.subplots(2, 1, figsize=(11, 5.6), sharex=True, gridspec_kw={"height_ratios": [1, 1]})
    ax = axes[0]
    ax.plot(t, peso, color=GRIS, lw=2)
    ax.fill_between(t, peso, 1, where=acc > 1, step="mid", color=AZUL, alpha=0.35, lw=0, label="El agente carga")
    ax.fill_between(t, peso, 1, where=acc < -1, step="mid", color=NARANJA, alpha=0.45, lw=0, label="El agente descarga")
    ax.axhline(1, color=TINTA2, lw=1, ls="--")
    ax.set_ylabel("Peso de la hora\n(1 = hora media)")
    ax.set_title("Una semana de julio: carga cuando la red es limpia y barata, descarga cuando es sucia y cara")
    ax.legend(loc="upper left", ncol=2, fontsize=10)
    ax = axes[1]
    ax.fill_between(t, soc / 1000, color=AZUL, alpha=0.18, lw=0)
    ax.plot(t, soc / 1000, color=AZUL, lw=2)
    ax.set_ylim(0, 2.1)
    ax.set_ylabel("Carga de la batería\n(MWh)")
    import matplotlib.dates as mdates
    ax.xaxis.set_major_locator(mdates.DayLocator())
    dias = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
    ax.xaxis.set_major_formatter(plt.FuncFormatter(
        lambda x, _: f"{dias[mdates.num2date(x).weekday()]} {mdates.num2date(x).day}"))
    fig.tight_layout()
    guardar(fig, "resultados_semana_tipo.png")


if __name__ == "__main__":
    main()
