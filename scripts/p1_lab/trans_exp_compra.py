"""Experimento (encargo de transiciones): ¿cuándo comprar la carga durante una semana a 0?

Estudio sin simulador, solo con precio y CO2 del train (todos los meses, noviembre incluido). Para cada
ventana de 7 días seguidos de un mes y una historia como la del test (una semana al azar de cada uno de
los 5 meses anteriores), cada regla decide qué día compra una batería entera (2.000 kWh; 2.108 kWh de
red) al valle de ese día (media de las 4 horas más baratas). Si no compra en toda la semana, compra en el
primer valle de la semana siguiente. Se mide el ahorro frente a comprar siempre el primer día (en puntos
de score de un episodio), el peor caso y cuántos días pasa la batería vacía, que es lo que se paga si el
consumo vuelve a media semana. NO se empaqueta.

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
    """Coste esperado con k días por delante (sin ver ninguno) si los valles fueran iid como x.
    Es MPCPolicy.reserve_weight."""
    x = np.asarray(x, dtype=float)
    c = float(x.mean())
    for _ in range(max(int(k) - 1, 0)):
        c = float(np.minimum(x, c).mean())
    return c


def rule_day1(hist, week, dow):
    return 0


def rule_oracle(hist, week, dow):
    return int(np.argmin(week))


def patience(cal, mode):
    """cal = valles que quedan por ver, contando el primero de la semana siguiente."""
    if mode == "half":
        return max(1, int(np.ceil(cal / 2)))
    if mode == "one":
        return 1
    return cal


def make_reserve(pool, mode, level_prior=None, weekend=None):
    """Regla de reserva del agente. `pool`: días de historia; `mode`: paciencia; `level_prior`: si no es
    None, la reserva se reescala al nivel de esta semana (la historia cuenta como ese número de días);
    `weekend`: si no es None, factor fin de semana / laborable para descontar el día de la semana."""
    def rule(hist, week, dows, hist_dows=None, next_dow=None):
        for d in range(7):
            x = np.concatenate([hist, week[:d]])[-pool:]
            if len(x) < 7:
                return d
            k = patience(7 - d, mode)
            if weekend is None:
                thr = iid_reserve(x, k)
            else:
                f = lambda dw: weekend if dw >= 5 else 1.0     # noqa: E731
                xd = np.concatenate([hist_dows, dows[:d]])[-pool:]
                xn = x / np.array([f(j) for j in xd])
                fut = ([f(j) for j in dows[d + 1:]] + [f(next_dow)])[:k]
                c = None
                for fj in fut[::-1]:
                    c = float((xn * fj).mean()) if c is None else float(np.minimum(xn * fj, c).mean())
                thr = c
            if level_prior is not None and d:
                thr *= (level_prior * x.mean() + week[:d].sum()) / ((level_prior + d) * x.mean())
            if week[d] <= thr:
                return d
        return 7
    return rule


def main():
    v = daily_valleys()
    per = v.index.to_period("M").astype(str)
    months = sorted(set(per))
    by_m = {m: v[per == m] for m in months}
    order = [m for m in months if len(by_m[m]) >= 7]
    lv = np.log(v)
    within = lv.groupby(per).transform(lambda x: x - x.mean()).std()
    print(f"valles diarios del train: {len(v)} días; desviación del logaritmo: total {lv.std():.3f}, "
          f"dentro del mes {within:.3f}, entre meses {np.sqrt(lv.std() ** 2 - within ** 2):.3f}")
    we = v.index.dayofweek >= 5
    print(f"valle medio de fin de semana / laborable: {v[we].mean() / v[~we].mean():.3f}")

    rules = {
        "día 1 (lo que hace v1)": rule_day1,
        "v2: 35 días, paciencia total": make_reserve(35, "full"),
        "14 días, paciencia total": make_reserve(14, "full"),
        "CANDIDATO: 7 días, total": make_reserve(7, "full"),
        "7 días, media paciencia (D)": make_reserve(7, "half"),
        "7 días, un día de paciencia": make_reserve(7, "one"),
        "35 días, media paciencia": make_reserve(35, "half"),
        "7 días, total + nivel semana": make_reserve(7, "full", level_prior=1.0),
        "7 días, media + nivel semana": make_reserve(7, "half", level_prior=1.0),
        "7 días, total + fin de semana": "weekend",
        "óptimo (mínimo de 7)": rule_oracle,
    }
    res = {k: [] for k in rules}
    wait = {k: [] for k in rules}
    for seed in (21, 22, 23):
        rng = np.random.default_rng(seed)
        for mi, m in enumerate(order):
            xm = by_m[m]
            vm, dm = xm.to_numpy(), xm.index.dayofweek.to_numpy()
            prev = order[max(0, mi - 5):mi]
            nxt = order[mi + 1] if mi + 1 < len(order) else None
            others = pd.concat([by_m[o] for o in order if o != m])
            wo = others.index.dayofweek >= 5
            fwe = float(others[wo].mean() / others[~wo].mean())   # factor estimado sin el mes evaluado
            for s in range(len(vm) - 6):
                week, dows = vm[s:s + 7], dm[s:s + 7]
                for _ in range(4):
                    hist, hd = [], []
                    for pm in prev:
                        x = by_m[pm]
                        a = int(rng.integers(0, len(x) - 6))
                        hist.append(x.to_numpy()[a:a + 7])
                        hd.append(x.index.dayofweek.to_numpy()[a:a + 7])
                    hist = np.concatenate(hist) if hist else np.array([])
                    hd = np.concatenate(hd) if hd else np.array([], dtype=int)
                    if nxt is not None:
                        xn = by_m[nxt]
                        a = int(rng.integers(0, len(xn) - 6))
                        nxt_first, nxt_dow = xn.to_numpy()[a], int(xn.index.dayofweek[a])
                    else:
                        nxt_first, nxt_dow = week.mean(), int((dows[-1] + 1) % 7)
                    ext = np.concatenate([week, [nxt_first]])
                    for name, rule in rules.items():
                        if rule == "weekend":
                            d = make_reserve(7, "full", weekend=fwe)(hist, week, dows, hd, nxt_dow)
                        else:
                            d = rule(hist, week, dows)
                        res[name].append(CONV * ext[d])
                        wait[name].append(d)
    base = np.array(res["día 1 (lo que hace v1)"])
    best = np.array(res["óptimo (mínimo de 7)"])
    print(f"\n{len(base)} casos (ventana x historia). Una carga entera cuesta {base.mean():.4f} puntos comprando el día 1.")
    print(f"{'regla':<30} {'ahorro':>7} {'% del posible':>13} {'peor caso':>9} {'días vacía':>10} {'vacía >= 4 d':>12} {'no compra':>9}")
    for name in rules:
        c, w = np.array(res[name]), np.array(wait[name])
        print(f"{name:<30} {(base - c).mean():>7.4f} {100 * (base - c).mean() / (base - best).mean():>12.0f}% "
              f"{(c - base).max():>9.4f} {w.mean():>10.2f} {100 * (w >= 4).mean():>11.0f}% {100 * (w >= 7).mean():>8.0f}%")


if __name__ == "__main__":
    main()
