"""Calidad de los datos oficiales: qué falla, cuánto y si cambia el score. Owner: P2.

    python analysis/p2_calidad_datos.py

Escribe analysis/figs/calidad_*.png e imprime las cifras de analysis/calidad_datos.md.
"""
import numpy as np
import pandas as pd
from p2_estilo import AZUL, GRIS, NARANJA, TINTA2, guardar, plt

from battery import data


def main() -> None:
    data.ensure_official()
    m = data.read_meter()
    ofi = data.build_hourly()
    real = data.build_hourly(variant="real")

    n = len(m)
    print(f"registros de 5 min del contador: {n}")
    print(f"  fallo de comunicación (potencia = 0): {m.com_fail.sum()} ({100 * m.com_fail.mean():.2f} %)")
    print(f"  contador congelado (noche):           {m.frozen.sum()} ({100 * m.frozen.mean():.1f} %)")
    nights = m[m.frozen & m.night_real_kw.notna()].groupby("night_real_kw", sort=False).first()
    blocks = m[m.frozen & m.night_real_kw.notna()].assign(d=lambda x: (x.Fecha - pd.Timedelta("7h")).dt.date)
    per = blocks.groupby("d").agg(cong=("load_kw", "first"), real=("night_real_kw", "first"))
    print(f"  noches con energía real: {len(per)}; consumo congelado {per.cong.mean():.0f} kW, "
          f"real {per.real.mean():.0f} kW ({100 * (per.real.mean() / per.cong.mean() - 1):+.1f} %)")
    over = (per.cong - per.real).mean() * data.NIGHT_HOURS
    print(f"  sobrestimación media: {over:.0f} kWh por noche "
          f"({100 * over / (ofi.load_kw.mean() * 24):.1f} % del consumo diario)")
    print(f"tabla horaria oficial: {len(ofi)} h; consumo 0 en {(ofi.load_kw == 0).sum()} h; "
          f"limpia/real: {len(real)} h (+{len(real) - len(ofi)})")
    print(f"consumo medio: oficial {ofi.load_kw.mean():.0f} kW, real {real.load_kw.mean():.0f} kW")

    # Figura 1: dos días de ejemplo, lo que dice el dataset y lo que pasó de verdad.
    t0, t1 = pd.Timestamp("2026-01-13 12:00"), pd.Timestamp("2026-01-15 12:00")
    w = m[(m.Fecha >= t0) & (m.Fecha <= t1)]
    fig, ax = plt.subplots(figsize=(11, 4.6))
    for _, g in w[w.frozen].groupby((~w.frozen).cumsum()):
        ax.axvspan(g.Fecha.iloc[0], g.Fecha.iloc[-1], color="#f0efec", lw=0)
    ax.plot(w.Fecha, w.load_kw, color=GRIS, lw=2, label="Lo que dice el dataset (potencia del contador)")
    r = w.load_kw.mask(w.frozen & w.night_real_kw.notna(), w.night_real_kw)
    ax.plot(w.Fecha, r.where(w.frozen), color=AZUL, lw=2.5, label="Consumo real (energía acumulada del contador)")
    ax.set_ylim(600, 1800)
    ax.set_ylabel("Consumo del campus (kW)")
    ax.set_title("De 22:10 a 06:00 el contador no se lee: el dataset repite el último valor")
    ax.text(pd.Timestamp("2026-01-14 02:05"), 1085, "sin lectura", ha="center", color=TINTA2, fontsize=11)
    ax.legend(loc="upper left", fontsize=11)
    import matplotlib.dates as mdates
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %Hh"))
    guardar(fig, "calidad_contador_congelado.png")

    # Figura 2: perfil medio del día, dataset frente a real (días laborables).
    fig, ax = plt.subplots(figsize=(11, 4.6))
    for df, color, label in ((ofi, GRIS, "Dataset oficial"), (real, AZUL, "Consumo real reconstruido")):
        d = df[df.timestamp.dt.dayofweek < 5]
        prof = d.groupby(d.timestamp.dt.hour).load_kw.mean()
        ax.plot(prof.index, prof.values, color=color, label=label, lw=2.5)
        ax.text(23.2, prof.iloc[-1], label, color=TINTA2, va="center", fontsize=11)
    ax.set_xlim(0, 28)
    ax.set_xticks(range(0, 24, 3))
    ax.set_xlabel("Hora del día")
    ax.set_ylabel("Consumo medio en laborables (kW)")
    ax.set_title("El consumo nocturno real es un 19 % menor que el del dataset")
    guardar(fig, "calidad_perfil_noche.png")


if __name__ == "__main__":
    main()
