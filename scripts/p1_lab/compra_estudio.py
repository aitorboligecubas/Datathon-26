"""Estudio del encargo "compra" con el train: de dónde salen los parámetros y qué pesa el día de la semana.
NO se empaqueta.

    python scripts/p1_lab/compra_estudio.py

1. Parámetros del candidato, medidos en los valles diarios del train (precio y CO2 de todos los meses,
   noviembre incluido): efecto del fin de semana, dispersión dentro de la semana, cambio de nivel entre
   semanas del test y valor de uso de la carga en la semana siguiente.
2. Simulación de la compra en cada ventana de 7 días del train (209), hora a hora y sin LP: con el consumo
   a 0, el LP de 24 h compra las horas de la ventana que cuestan menos que la reserva, las más baratas
   primero, hasta llenar; el último día se llena en sus horas más baratas. Se compara lo que paga cada
   regla con lo que pagaría quien conociera toda la semana ("exceso", en puntos de score de un episodio):
       v1          compra en el primer valle (lo que hacía el agente del primer envío)
       v2          reserva con los valles de los 35 últimos días vistos (el agente actual)
       candidato   scripts/p1_lab/cand_compra.py (usa su propio `reserve_now`)
       sin día     el candidato sin el efecto del fin de semana
   La historia es la que tendría el agente en el test: la última semana del train de cada mes anterior.
   Límite de esta simulación: obliga a llenar la batería. Lo que vale la carga en la semana siguiente solo
   lo miden el banco y los mini-episodios (ver results/p1_banco/compra_notas.md).
3. Lo mismo con el día de la semana puesto al azar, que es lo que hace scripts/p1_banco.py.
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "p1_lab"))

import cand_compra as C  # noqa: E402
from battery.data import TRAIN_DIR, ensure_official  # noqa: E402

W_CO2, W_COST = 0.7 / 93.19721939496067, 0.3 / 156.32105608412144
NEED = 2000.0 / math.sqrt(0.9)            # kWh de red para llenar la batería desde 0
POINTS = NEED * 100 / 2016                # kWh comprados x peso -> puntos de score de un episodio
TEST_STARTS = ["2025-09-24", "2025-10-25", "2025-11-24", "2025-12-25", "2026-01-25", "2026-02-22",
               "2026-03-25", "2026-04-24", "2026-05-25", "2026-06-24", "2026-07-25", "2026-08-25"]


def load_days() -> dict:
    """fecha -> 24 pesos (score por kWh comprado), solo días completos."""
    ensure_official()
    pr = pd.read_csv(TRAIN_DIR / "precio_pvpc.csv", parse_dates=["Fecha"]).set_index("Fecha")
    co = pd.read_csv(TRAIN_DIR / "co2_red.csv", parse_dates=["Fecha"]).set_index("Fecha")
    d = pd.DataFrame({"p": pr.precio_eur_per_kwh, "c": co.co2_kg_per_kwh}).dropna()
    w = W_CO2 * d.c + W_COST * d.p
    return {day: g.to_numpy() for day, g in w.groupby(w.index.normalize()) if len(g) == 24}


def windows(days: dict) -> list:
    keys = set(days)
    return [(d, np.concatenate([days[d + pd.Timedelta(days=i)] for i in range(7)]))
            for d in sorted(days) if all(d + pd.Timedelta(days=i) in keys for i in range(7))]


def parametros(days: dict, wins: list) -> None:
    t = pd.DataFrame({"date": sorted(days)})
    t["u"] = [math.log(C.cheapest_mean(days[d])) for d in t.date]
    t["use"] = [C.use_value_log(days[d]) for d in t.date]
    t["we"] = (t.date.dt.dayofweek >= 5).astype(float)
    t["month"] = t.date.dt.to_period("M")
    uc, wc = t.u - t.groupby("month").u.transform("mean"), t.we - t.groupby("month").we.transform("mean")
    delta = float((uc * wc).sum() / (wc ** 2).sum())
    print(f"1. Parámetros ({len(t)} días completos, {len(wins)} ventanas de 7 días)")
    print(f"   fin de semana: log(valle fin de semana / laborable) = {delta:+.3f} (factor {math.exp(delta):.2f});"
          f" en el candidato WEEKEND_SHIFT = {C.WEEKEND_SHIFT}")
    by = {str(m): float((uc[g.index] * wc[g.index]).sum() / (wc[g.index] ** 2).sum()) for m, g in t.groupby("month") if len(g) > 7}
    print("   por mes: " + "  ".join(f"{m[2:]}: {v:+.2f}" for m, v in by.items()))
    lv = {d: np.array([math.log(C.cheapest_mean(w[i * 24:(i + 1) * 24])) - delta * ((d.dayofweek + i) % 7 >= 5) for i in range(7)])
          for d, w in wins}
    sigma = math.sqrt(np.mean([x.var(ddof=1) for x in lv.values()]))
    print(f"   dispersión de log(valle) dentro de una semana: {sigma:.3f}; SIGMA_VALLEY = {C.SIGMA_VALLEY}")
    last = {}
    for d, _ in wins:
        last[d.to_period("M")] = d
    err, err5 = [], []
    for d, x in lv.items():
        prev = [lv[last[q]].mean() for q in sorted(last) if q < d.to_period("M")]
        if prev:
            err.append(x.mean() - prev[-1])
            err5.append(x.mean() - np.mean(prev[-5:]))
    print(f"   nivel de una semana frente al de la semana vista antes: error típico {np.sqrt(np.mean(np.square(err))):.3f}"
          f" (frente a la media de las 5 anteriores: {np.sqrt(np.mean(np.square(err5))):.3f}); TAU_LEVEL = {C.TAU_LEVEL}")
    xi = []
    for d, w in wins:
        now = np.mean([C.use_value_log(w[i * 24:(i + 1) * 24]) for i in range(7)])
        xi += list(t[t.month == d.to_period("M") + 1].use - now)
    print(f"   valor de uso de un día del mes siguiente frente al de la semana: desviación {np.std(xi):.3f}; TAU_USE = {C.TAU_USE}")


class Stamp:
    """Lo que `reserve_now` lee de la fecha: día real (para el día de la semana) y días que quedan."""

    def __init__(self, ordinal: int, days_after: int, hour: int):
        self.ordinal, self.hour, self.days_in_month, self.day = ordinal, hour, 31, 31 - days_after

    def toordinal(self) -> int:
        return self.ordinal


class Obs:
    def __init__(self, ts):
        self.timestamp = ts


def reserve_v2(valleys, days_left: int) -> float:
    x = np.asarray(valleys, dtype=float)
    c = float(x.mean())
    for _ in range(max(int(days_left) - 1, 0)):
        c = float(np.minimum(x, c).mean())
    return c


def buy_week(w, ord0: int, hist: list, rule: str) -> float:
    """Peso medio pagado por una carga entera en la semana `w` (168 pesos) con la regla dada."""
    pol = object.__new__(C.Candidate)
    pol.USE_WEEKDAY = rule == "candidato"
    pol.prev_days = hist[-C.PREV_DAYS:]
    pol.block_days, pol.day_w = [], {}
    valleys = [v for _, v in hist][-35:]
    need, cost = NEED, 0.0
    for t in range(1, 168):                      # la hora 0 se pierde: aún no se sabe que la semana viene a 0
        d, h, K = t // 24, t % 24, 168 - t
        if h == 0:
            day = w[(d - 1) * 24:d * 24]
            pol.block_days.append((ord0 + d - 1, C.cheapest_mean(day), C.use_value_log(day)))
            valleys = (valleys + [C.cheapest_mean(day)])[-35:]
        if need <= 1e-6:
            break
        win = w[t:min(t + 24, 168)]
        if K <= 24 or rule == "v1":
            thr = float("inf")                   # último día (o v1): se llena en las horas más baratas a la vista
        elif rule == "v2":
            thr = reserve_v2(valleys, int(math.ceil((K - 24) / 24.0)) + 1) if len(valleys) >= 7 else float("inf")
        else:
            pol.day_w = {ord0 + d: w[d * 24:(d + 1) * 24], ord0 + d + 1: w[(d + 1) * 24:(d + 2) * 24]}
            thr = pol.reserve_now(Obs(Stamp(ord0 + d, 6 - d, h)))
        rem = need
        for k in np.argsort(win, kind="stable"):
            if win[k] >= thr or rem <= 1e-9:
                break
            q = min(500.0, rem)
            if k == 0:
                cost += q * w[t]
                need -= q
                break
            rem -= q
    return cost / NEED


def hindsight(w) -> float:
    ws, rem, cost = np.sort(w[1:]), NEED, 0.0
    for x in ws:
        q = min(500.0, rem)
        cost, rem = cost + q * x, rem - q
        if rem <= 1e-9:
            break
    return cost / NEED


def compras(wins: list, random_weekday: bool = False) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    last = {}
    for d, w in wins:
        last[d.to_period("M")] = (d, w)
    rows = []
    for d, w in wins:
        hist = []
        for q in sorted(last):
            if q < d.to_period("M"):
                d0, w0 = last[q]
                hist += [(d0.toordinal() + i, C.cheapest_mean(w0[i * 24:(i + 1) * 24])) for i in range(7)]
        ord0 = d.toordinal() + (int(rng.integers(0, 7)) if random_weekday else 0)
        best = hindsight(w)
        row = {"inicio": d, "mes": str(d.to_period("M")), "dia": d.dayofweek}
        for rule in ("v1", "v2", "candidato", "sin día"):
            row[rule] = (buy_week(w, ord0, hist, rule) - best) * POINTS
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> int:
    pd.set_option("display.width", 200)
    days = load_days()
    wins = windows(days)
    parametros(days, wins)
    rules = ["v1", "v2", "candidato", "sin día"]
    t = compras(wins)
    print("\n2. Exceso sobre comprar sabiendo toda la semana, en puntos de score (día de la semana real)")
    g = t.groupby("dia")[rules].mean()
    g.index = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    g["ventanas"] = t.groupby("dia").size().to_numpy()
    print("   por día en que empieza la semana:")
    print(g.round(4).to_string())
    cal = []
    for s in TEST_STARTS:
        x = t[(t.mes == s[:7]) & (t.dia == pd.Timestamp(s).dayofweek)]
        cal.append({"semana del test": s, "empieza en": g.index[pd.Timestamp(s).dayofweek], "ventanas": len(x), **x[rules].mean().to_dict()})
    cal = pd.DataFrame(cal).set_index("semana del test")
    print("   cada mes, con las ventanas del train que empiezan el mismo día de la semana que su semana del test:")
    print(cal.round(4).to_string())
    print("   media:", cal[rules].mean().round(4).to_dict())
    print("   todas las ventanas:", t[rules].mean().round(4).to_dict())
    print("   diferencia con v2, ventana a ventana (positivo = mejor que v2), con su error típico:")
    groups = (("empiezan en lunes, de octubre a agosto", t[(t.dia == 0) & (t.mes != "2025-09")]),
              ("empiezan en lunes, noviembre", t[(t.dia == 0) & (t.mes == "2025-11")]),
              ("todas (solapadas)", t))
    for name, x in groups:
        parts = []
        for rule in ("candidato", "sin día"):
            d = x["v2"] - x[rule]
            parts.append(f"{rule} {d.mean():+.4f} ± {d.std(ddof=1) / math.sqrt(len(d)):.4f} (mejor en {int((d > 1e-5).sum())}, peor en {int((d < -1e-5).sum())})")
        print(f"      {name} ({len(x)}): " + "; ".join(parts))
    r = compras(wins, random_weekday=True)
    print("\n3. Con el día de la semana al azar (lo que ve el agente en scripts/p1_banco.py)")
    print("   todas las ventanas:", r[rules].mean().round(4).to_dict())
    print("   noviembre:", r[r.mes == "2025-11"][rules].mean().round(4).to_dict(),
          "| noviembre con el día real:", t[t.mes == "2025-11"][rules].mean().round(4).to_dict())
    return 0


if __name__ == "__main__":
    sys.exit(main())
