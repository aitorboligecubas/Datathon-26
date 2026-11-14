"""Pregunta de negocio para UPC Sostenible: ¿qué ahorraría una batería de 1, 2, 4 u 8 MWh? Owner: P2.

    python analysis/p2_escenarios.py

Óptimo con información perfecta (baselines.OracleAgent) para cada tamaño, sobre TODO el train
(variante "limpio": 258 días completos de 11 meses; falta noviembre) y anualizado a 365 días.
Nuestro agente real captura el 99,6 % de ese óptimo. Escribe analysis/figs/escenarios_*.png
y analysis/escenarios.csv.
"""
import numpy as np
import pandas as pd
from p2_estilo import AZUL, GRIS, NARANJA, REPO, TINTA, TINTA2, guardar, plt

from battery import data
from battery.baselines import OracleAgent
from battery.params import DEFAULT_PARAMS, W_CO2, W_COST
from battery.sim import baseline_totals, score, simulate

TAMANOS_MWH = [0.5, 1, 2, 4, 8, 16]
HORAS_A_PLENA_POTENCIA = 4.0          # la batería del reto: 2.000 kWh / 500 kW
COSTES_EUR_KWH = [200, 300, 400]      # SUPUESTO de coste instalado, a contrastar con UPC Sostenible


def escenario(df: pd.DataFrame, mwh: float, kw: float) -> dict:
    p = DEFAULT_PARAMS._replace(capacity_kwh=1000.0 * mwh, soc_init_kwh=500.0 * mwh,
                                max_charge_kw=kw, max_discharge_kw=kw)
    base = baseline_totals(df)
    n = len(df)
    res = simulate(OracleAgent(df, W_CO2 / (base["co2_kg"] / n), W_COST / (base["cost_eur"] / n), p), df, p)
    sc = score(res.totals, base)
    anual = 365.0 / (n / 24.0)
    desc = (-res.log.action_kw).clip(lower=0).sum()
    return {
        "capacidad_mwh": mwh, "potencia_kw": kw, "score": sc["score"],
        "co2_pct": sc["d_co2_pct"], "coste_pct": sc["d_cost_pct"], "infracciones": sc["infractions"],
        "co2_t_ano": (base["co2_kg"] - res.totals["co2_kg"]) * anual / 1000.0,
        "eur_ano": (base["cost_eur"] - res.totals["cost_eur"]) * anual,
        "ciclos_dia": desc / p.eta_discharge / p.capacity_kwh / (n / 24.0),
        "vertido_kwh": res.totals["export_kwh"],
    }


def main() -> None:
    df = data.build_hourly(variant="limpio")
    base = baseline_totals(df)
    dias = len(df) / 24
    anual = 365 / dias
    print(f"{len(df)} h ({dias:.0f} días). Campus sin batería, anualizado: "
          f"{base['import_kwh'] * anual / 1e6:.2f} GWh, {base['co2_kg'] * anual / 1000:.0f} t CO2, "
          f"{base['cost_eur'] * anual / 1e6:.2f} M€")
    prop = pd.DataFrame([escenario(df, m, 1000.0 * m / HORAS_A_PLENA_POTENCIA) for m in TAMANOS_MWH])
    fija = pd.DataFrame([escenario(df, m, 500.0) for m in TAMANOS_MWH])
    for nombre, t in (("potencia proporcional (4 h a plena potencia)", prop), ("potencia fija de 500 kW", fija)):
        t["co2_t_por_mwh"] = t.co2_t_ano / t.capacidad_mwh
        t["eur_por_mwh"] = t.eur_ano / t.capacidad_mwh
        t["marginal_eur_mwh"] = t.eur_ano.diff() / t.capacidad_mwh.diff()
        t["marginal_co2_t_mwh"] = t.co2_t_ano.diff() / t.capacidad_mwh.diff()
        print(f"\n{nombre}:")
        print(t.round(2).to_string(index=False))
    prop.assign(variante="potencia proporcional").to_csv(REPO / "analysis" / "escenarios.csv", index=False)
    fija.assign(variante="potencia fija 500 kW").to_csv(REPO / "analysis" / "escenarios.csv", index=False,
                                                        mode="a", header=False)
    print("\nRetorno simple de la inversión (años), solo con el ahorro en la factura [SUPUESTO de coste]:")
    for c in COSTES_EUR_KWH:
        print(f"  {c} €/kWh:", {m: round(c * 1000 * m / e, 1) for m, e in zip(prop.capacidad_mwh, prop.eur_ano)})

    # Figura 1: ahorro anual según el tamaño (dos paneles, una medida en cada uno).
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    for ax, col, color, titulo, unidad, k in (
            (axes[0], "co2_t_ano", AZUL, "CO₂ evitado al año", "toneladas de CO₂ al año", 1),
            (axes[1], "eur_ano", NARANJA, "Ahorro en la factura al año", "miles de € al año", 1e-3)):
        ax.plot(prop.capacidad_mwh, prop[col] * k, color=color, lw=2.5, marker="o", ms=8,
                markeredgecolor="#fcfcfb", markeredgewidth=2)
        ax.plot(fija.capacidad_mwh, fija[col] * k, color=GRIS, lw=2, ls="--")
        ax.text(16.3, prop[col].iloc[-1] * k, "potencia\nproporcional", va="center", color=TINTA2, fontsize=10)
        ax.text(16.3, fija[col].iloc[-1] * k, "potencia fija\nde 500 kW", va="center", color=TINTA2, fontsize=10)
        for m in (1, 2, 4, 8):
            v = prop.loc[prop.capacidad_mwh == m, col].iloc[0] * k
            ax.annotate(f"{v:.0f}", (m, v), xytext=(0, 10), textcoords="offset points", ha="center",
                        color=TINTA, fontsize=11, fontweight="bold" if m == 2 else "normal")
        ax.set_xticks([1, 2, 4, 8, 16])
        ax.set_xlim(0, 20.5)
        ax.set_ylim(0, None)
        ax.set_xlabel("Capacidad de la batería (MWh)")
        ax.set_ylabel(unidad)
        ax.set_title(titulo)
    fig.tight_layout()
    guardar(fig, "escenarios_ahorro.png")

    # Figura 2: lo que aporta cada MWh adicional.
    tramos = [f"{a:g} → {b:g}".replace(".", ",") for a, b in zip(prop.capacidad_mwh[:-1], prop.capacidad_mwh[1:])]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    v = prop.marginal_co2_t_mwh.iloc[1:].to_numpy()
    ax.bar(range(len(v)), v, color=AZUL, width=0.65)
    for i, x in enumerate(v):
        ax.text(i, x + 0.3, f"{x:.1f}".replace(".", ","), ha="center", color=TINTA, fontsize=12)
    ax.set_xticks(range(len(v)), tramos)
    ax.set_xlabel("Ampliación de la batería (MWh)")
    ax.set_ylabel("t de CO₂ evitadas al año por cada MWh añadido")
    ax.grid(axis="x", visible=False)
    ax.set_ylim(0, 25)
    ax.set_title("Hasta 4 MWh cada MWh rinde lo mismo; a partir de ahí, cada vez menos")
    guardar(fig, "escenarios_marginal.png")


if __name__ == "__main__":
    main()
