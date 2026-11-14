"""Patrones de la red: cuándo es sucia, cuándo es cara y si coinciden. Owner: P2.

    python analysis/p2_patrones.py

Usa todo el train de precio y CO2 (también noviembre, que sí está en esos ficheros) y, para el coste
del conflicto, el oracle (LP con información perfecta) sobre la validación oficial.
Escribe analysis/figs/patrones_*.png e imprime las cifras de analysis/patrones.md.
"""
import numpy as np
import pandas as pd
from p2_estilo import AZUL, GRIS, MESES, NARANJA, TINTA, TINTA2, guardar, plt

from battery import data
from battery.baselines import OracleAgent
from battery.optimizer import score_weights
from battery.params import W_CO2, W_COST
from battery.sim import baseline_totals, score, simulate

ORDEN_MESES = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8]   # el curso: de septiembre a agosto


def red() -> pd.DataFrame:
    data.ensure_official()
    p = pd.read_csv(data.TRAIN_DIR / "precio_pvpc.csv", parse_dates=["Fecha"]).set_index("Fecha")
    c = pd.read_csv(data.TRAIN_DIR / "co2_red.csv", parse_dates=["Fecha"]).set_index("Fecha")
    df = pd.DataFrame({"precio": p["precio_eur_per_kwh"], "co2": c["co2_kg_per_kwh"],
                       "pct_emisiones": c["porcentaje_con_emisiones"]}).dropna()
    df["hora"], df["mes"], df["dia"] = df.index.hour, df.index.month, df.index.normalize()
    df["peso"] = W_CO2 * df.co2 / df.co2.mean() + W_COST * df.precio / df.precio.mean()
    return df


def fig_por_hora(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), sharex=True)
    for ax, col, color, titulo, unidad, k in (
            (axes[0], "co2", AZUL, "CO₂ de la red por hora del día", "g CO₂/kWh", 1000),
            (axes[1], "precio", NARANJA, "Precio PVPC por hora del día", "céntimos/kWh", 100)):
        g = df.groupby("hora")[col]
        med, q1, q3 = g.mean() * k, g.quantile(0.25) * k, g.quantile(0.75) * k
        ax.fill_between(med.index, q1, q3, color=color, alpha=0.18, lw=0)
        ax.plot(med.index, med, color=color, lw=2.5)
        hmin, hmax = med.idxmin(), med.idxmax()
        for h, txt, dy in ((hmin, "mínimo", -1), (hmax, "máximo", 1)):
            ax.scatter([h], [med[h]], color=color, s=60, zorder=3, edgecolor="#fcfcfb", linewidth=2)
            ax.annotate(f"{txt}: {med[h]:.0f} a las {h} h", (h, med[h]), xytext=(0, 14 * dy),
                        textcoords="offset points", ha="center", va="center", fontsize=11, color=TINTA)
        ax.set_title(titulo)
        ax.set_ylabel(unidad)
        ax.set_xlabel("Hora del día")
        ax.set_xticks(range(0, 24, 3))
        ax.set_ylim(0, q3.max() * 1.15)
    fig.text(0.01, -0.03, "Línea: media del año. Banda: la mitad central de los días (percentiles 25–75).",
             color=TINTA2, fontsize=10)
    fig.tight_layout()
    guardar(fig, "patrones_por_hora.png")


def fig_mapas(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    for ax, col, cmap, titulo, k, fmt in (
            (axes[0], "co2", "Blues", "CO₂ de la red (g/kWh): mes × hora", 1000, "{:.0f}"),
            (axes[1], "precio", "Oranges", "Precio PVPC (cént./kWh): mes × hora", 100, "{:.0f}")):
        t = (df.pivot_table(index="mes", columns="hora", values=col, aggfunc="mean") * k).reindex(ORDEN_MESES)
        im = ax.imshow(t.values, aspect="auto", cmap=cmap)
        ax.set_yticks(range(12), [MESES[m - 1] for m in ORDEN_MESES])
        ax.set_xticks(range(0, 24, 3))
        ax.set_xlabel("Hora del día")
        ax.set_title(titulo)
        ax.grid(False)
        cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
        cb.outline.set_visible(False)
    fig.tight_layout()
    guardar(fig, "patrones_mes_hora.png")


def fig_conflicto(df: pd.DataFrame) -> None:
    """Para cada día: ¿la hora más limpia es también barata? ¿la más sucia es cara?"""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    g = df.groupby("hora")
    co2n, pn = g.co2.mean() / df.co2.mean(), g.precio.mean() / df.precio.mean()
    ax = axes[0]
    ax.plot(co2n.index, co2n, color=AZUL, lw=2.5)
    ax.plot(pn.index, pn, color=NARANJA, lw=2.5)
    ax.text(23.3, co2n.iloc[-1] + 0.03, "CO₂", color=TINTA, va="center")
    ax.text(23.3, pn.iloc[-1] - 0.03, "Precio", color=TINTA, va="center")
    ax.axhline(1, color=GRIS, lw=1, ls="--")
    ax.set_xlim(0, 26)
    ax.set_xticks(range(0, 24, 3))
    ax.set_xlabel("Hora del día")
    ax.set_ylabel("Respecto a la media del año (1 = media)")
    ax.set_title("De día van juntos; de madrugada, no")
    ax = axes[1]
    corr = df.groupby("mes").apply(lambda d: d.co2.corr(d.precio)).reindex(ORDEN_MESES)
    ax.bar(range(12), corr.values, color=AZUL, width=0.7)
    ax.set_xticks(range(12), [MESES[m - 1] for m in ORDEN_MESES])
    ax.axhline(0, color=TINTA2, lw=1)
    ax.set_ylabel("Correlación horaria CO₂–precio")
    ax.set_ylim(0, 1)
    ax.set_title("Van juntos todos los meses, pero no del todo")
    fig.tight_layout()
    guardar(fig, "patrones_conflicto.png")


def coste_del_conflicto() -> pd.DataFrame:
    """Oracle con distintos pesos: solo CO2, solo coste y el 70/30 del score."""
    val = data.validation_split(data.load())
    base = baseline_totals(val)
    n = len(val)
    rows = []
    for nombre, a, b in (("solo CO₂ (100/0)", 1.0, 0.0), ("score (70/30)", W_CO2, W_COST),
                         ("mitad y mitad (50/50)", 0.5, 0.5), ("solo coste (0/100)", 0.0, 1.0)):
        w_co2, w_cost = a / (base["co2_kg"] / n), b / (base["cost_eur"] / n)
        res = simulate(OracleAgent(val, w_co2, w_cost), val)
        sc = score(res.totals, base)
        rows.append({"objetivo": nombre, "ΔCO2 %": sc["d_co2_pct"], "ΔCoste %": sc["d_cost_pct"],
                     "score": sc["score"], "infracciones": sc["infractions"]})
    return pd.DataFrame(rows)


def main() -> None:
    df = red()
    print(f"{len(df)} h de precio y CO2 ({df.index.min():%d/%m/%Y} – {df.index.max():%d/%m/%Y})")
    print(f"CO2: media {1000 * df.co2.mean():.0f} g/kWh (de {1000 * df.co2.min():.0f} a {1000 * df.co2.max():.0f}); "
          f"precio: media {100 * df.precio.mean():.1f} cént./kWh (de {100 * df.precio.min():.1f} a {100 * df.precio.max():.1f})")
    h = df.groupby("hora")[["co2", "precio", "peso"]].mean()
    print("por hora (g/kWh, cént./kWh, peso):")
    print((h * [1000, 100, 1]).round(2).T.to_string())
    for col in ("co2", "precio", "peso"):
        print(f"  {col}: mejor hora {h[col].idxmin()} h, peor hora {h[col].idxmax()} h, "
              f"peor/mejor = {h[col].max() / h[col].min():.2f}")
    mm = df.groupby("mes")[["co2", "precio"]].mean().reindex(ORDEN_MESES)
    print("por mes (g/kWh, cént./kWh):")
    print((mm * [1000, 100]).round(1).T.to_string())
    print(f"correlación horaria CO2–precio: {df.co2.corr(df.precio):.2f}")
    dia = df.groupby("dia").filter(lambda d: len(d) == 24)
    por_dia = dia.groupby("dia")
    print(f"correlación dentro del día (mediana de {por_dia.ngroups} días): "
          f"{por_dia.apply(lambda d: d.co2.corr(d.precio)).median():.2f}")
    limpia = por_dia.apply(lambda d: d.co2.idxmin().hour)
    barata = por_dia.apply(lambda d: d.precio.idxmin().hour)
    sucia = por_dia.apply(lambda d: d.co2.idxmax().hour)
    cara = por_dia.apply(lambda d: d.precio.idxmax().hour)
    print(f"hora más limpia del día: moda {limpia.mode()[0]} h; más barata: {barata.mode()[0]} h; "
          f"más sucia: {sucia.mode()[0]} h; más cara: {cara.mode()[0]} h")
    # ¿Las 6 horas más limpias del día están entre las 12 más baratas? ¿Y las 6 más sucias entre las 12 más caras?
    def solape(d, limpias=True):
        a = d.co2.nsmallest(6).index if limpias else d.co2.nlargest(6).index
        b = d.precio.nsmallest(12).index if limpias else d.precio.nlargest(12).index
        return len(a.intersection(b)) / 6
    print(f"de las 6 h más limpias de cada día, están en la mitad barata: {100 * por_dia.apply(solape).mean():.0f} %")
    print(f"de las 6 h más sucias de cada día, están en la mitad cara:   "
          f"{100 * por_dia.apply(lambda d: solape(d, False)).mean():.0f} %")
    rango = por_dia.peso.max() / por_dia.peso.min()
    print(f"peso máx/mín dentro del día: mediana {rango.median():.2f}; "
          f"días en los que no llega a 1,11: {100 * (rango < 1 / 0.9).mean():.1f} %")
    print("\nCoste del conflicto (oracle en validación oficial):")
    print(coste_del_conflicto().round(2).to_string(index=False))
    fig_por_hora(df)
    fig_mapas(df)
    fig_conflicto(df)


if __name__ == "__main__":
    main()
