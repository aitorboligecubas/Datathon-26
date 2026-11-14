"""Experimento (encargo de transiciones): ¿cuándo comprar la carga durante una semana a 0?

Estudio sin simulador, solo con precio y CO2 del train (todos los meses, noviembre incluido). Para cada
ventana de 7 días seguidos de un mes y una historia como la del test (semanas de los meses anteriores),
cada regla decide qué día compra una batería entera (2.000 kWh a red: 2.108 kWh) al valle de ese día
(media de las 4 horas más baratas). Se mide el coste en puntos de score y los días que pasa vacía.
NO se empaqueta.

    python scripts/p1_lab/trans_exp_compra.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from battery.data import TRAIN_DIR, ensure_official  # noqa: E402

W_CO2, W_COST = 0.7 / 93.19721939496067, 0.3 / 156.32105608412144
CONV = 2108.2 * 100 / 2016          # kWh de una carga entera x peso -> puntos de score de un episodio


def daily_valleys():
    ensure_official()
    pr = pd.read_csv(TRAIN_DIR / "precio_pvpc.csv", parse_dates=["Fecha"]).set_index("Fecha")
    co = pd.read_csv(TRAIN_DIR / "co2_red.csv", parse_dates=["Fecha"]).set_index("Fecha")
    d = pd.DataFrame({"p": pr.precio_eur_per_kwh, "c": co.co2_kg_per_kwh}).dropna()
    d["w"] = W_CO2 * d.c + W_COST * d.p
    v = d.groupby(d.index.floor("D")).w.apply(lambda x: np.sort(x.values)[:4].mean() if len(x) >= 24 else np.nan).dropna()
    return v


def iid_reserve(x, k):
    """Coste esperado con k días por delante (sin ver ninguno) si los valles fueran iid como x."""
    x = np.asarray(x, dtype=float)
    c = float(x.mean())
    for _ in range(max(int(k) - 1, 0)):
        c = float(np.minimum(x, c).mean())
    return c


def rule_day1(hist, week, dow):
    return 0


def rule_last(hist, week, dow):
    return 6


def rule_oracle(hist, week, dow):
    return int(np.argmin(week))


def make_best_of(n):
    def rule(hist, week, dow):
        # compra el día n-ésimo como muy tarde; antes, si el valle de hoy es el mejor visto y... (no causal del todo:
        # elegir el mejor de n exige verlos; aquí se aproxima con "esperar a ver n y comprar el último si es el mínimo")
        return int(np.argmin(week[:n]))
    return rule


def make_v2(pool_days=35, patient=1):
    def rule(hist, week, dow):
        for d in range(7):
            x = np.concatenate([hist, week[:d]])[-pool_days:]
            if len(x) < 7 or d == 6:
                return d
            if week[d] <= iid_reserve(x, 6 - d + patient):
                return d
        return 6
    return rule


def make_relative(shrink=0.0, sigma=None, patient=0):
    """Reserva relativa al nivel de la semana: nivel = media de los valles vistos esta semana (con `shrink`
    días equivalentes de la historia), y dispersión dentro de la semana tomada de la historia (cada valle
    dividido por la media de su semana)."""
    def rule(hist, week, dow):
        if len(hist) >= 7:
            blocks = [hist[i:i + 7] for i in range(0, len(hist) - 6, 7)]
            rel = np.concatenate([b / b.mean() for b in blocks])
        else:
            rel = None
        for d in range(6):
            seen = week[:d + 1]
            if rel is None and sigma is None:
                return d
            level = (seen.sum() + shrink * (hist.mean() if len(hist) else seen.mean())) / (len(seen) + shrink)
            r = rel if sigma is None else np.exp(sigma * np.array([-1.5, -0.75, 0, 0.75, 1.5]))
            if week[d] <= level * iid_reserve(r, 6 - d + patient):
                return d
        return 6
    return rule


def make_secretary(skip):
    def rule(hist, week, dow):
        for d in range(skip, 6):
            if week[d] <= week[:d].min():
                return d
        return 6
    return rule


def make_dow(pool_days=35):
    """Como v2 pero quitando el efecto del día de la semana (fin de semana más barato) con un factor fijo."""
    f = np.array([1.09, 1.05, 1.05, 1.04, 1.05, 0.85, 0.87])

    def rule(hist, week, dow, hist_dow=None):
        raise NotImplementedError
    return rule


def main():
    v = daily_valleys()
    months = sorted({str(p) for p in v.index.to_period("M")})
    by_m = {m: v[v.index.to_period("M") == m] for m in months}
    order = [m for m in months if len(by_m[m]) >= 7]
    rng = np.random.default_rng(0)
    rules = {"día 1 (como v1)": rule_day1, "último día": rule_last,
             "v2: reserva iid, 35 días": make_v2(35, 1), "v2 sin día de más": make_v2(35, 0),
             "reserva iid, 14 días": make_v2(14, 0), "reserva iid, 7 días": make_v2(7, 0),
             "relativa (nivel = semana)": make_relative(0.0), "relativa, shrink 1": make_relative(1.0),
             "relativa, shrink 2": make_relative(2.0), "relativa, shrink 4": make_relative(4.0),
             "secretaria, salta 1": make_secretary(1), "secretaria, salta 2": make_secretary(2),
             "mejor de 2 (no causal)": make_best_of(2), "mejor de 3 (no causal)": make_best_of(3),
             "óptimo (mínimo de 7)": rule_oracle}
    res = {k: [] for k in rules}
    wait = {k: [] for k in rules}
    for mi, m in enumerate(order):
        vm = by_m[m].to_numpy()
        prev = order[max(0, mi - 5):mi]
        for s in range(len(vm) - 6):
            week = vm[s:s + 7]
            dow = by_m[m].index[s].dayofweek
            for rep in range(4):
                hist = []
                for pm in prev:
                    x = by_m[pm].to_numpy()
                    a = int(rng.integers(0, len(x) - 6))
                    hist.append(x[a:a + 7])
                hist = np.concatenate(hist) if hist else np.array([])
                for name, rule in rules.items():
                    d = rule(hist, week, dow)
                    res[name].append(CONV * week[d])
                    wait[name].append(d)
    n = len(res["día 1 (como v1)"])
    base = np.array(res["día 1 (como v1)"])
    best = np.array(res["óptimo (mínimo de 7)"])
    print(f"{n} casos (ventana x historia). Coste de la carga en puntos de score; 'ahorro' = frente a comprar el día 1")
    print(f"{'regla':<28} {'coste':>7} {'ahorro':>7} {'% del posible':>13} {'peor caso':>9} {'días vacía':>10} {'% compra día 1':>14}")
    for name in rules:
        c = np.array(res[name])
        w = np.array(wait[name])
        print(f"{name:<28} {c.mean():>7.4f} {(base - c).mean():>7.4f} {100 * (base - c).mean() / (base - best).mean():>12.0f}% "
              f"{(c - base).max():>9.4f} {w.mean():>10.2f} {100 * (w == 0).mean():>13.0f}%")


if __name__ == "__main__":
    main()
