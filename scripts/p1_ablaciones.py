"""Desglose de piezas (ablaciones) y robustez del agente. NO se empaqueta.

Owner: P1 (optimización y robustez).

    python scripts/p1_ablaciones.py            # todo (unos 2-3 min)
    python scripts/p1_ablaciones.py --quick    # menos semillas de ruido

Responde con números a tres preguntas, sobre la validación con datos oficiales:
1. ¿Cuántas décimas aporta cada pieza del agente? (quitando una cada vez)
2. ¿Qué pasa si el servidor evalúa cada semana por separado (carga reiniciada al 50 %)?
3. ¿Cuánto se degrada si las previsiones de precio y CO2 llevan ruido?
4. ¿Se sostiene fuera de la validación (train e histórico completo, episodios > 2.016 h)?
Escribe las tablas en results/p1_ablaciones.md (para la presentación).
"""
import argparse
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from battery.baselines import GreedyAgent, OracleAgent  # noqa: E402
from battery.data import is_synthetic, load, train_split, validation_split  # noqa: E402
from battery.optimizer import score_weights  # noqa: E402
from battery.policy import BatteryAgent, MPCPolicy  # noqa: E402
from battery.sim import baseline_totals, score, simulate  # noqa: E402

OUT = REPO / "results" / "p1_ablaciones.md"


# ----------------------------------------------------------------- variantes del agente
class _Wrap:
    """Agente con una MPCPolicy modificada."""

    def __init__(self, policy):
        self.policy = policy

    def act(self, obs):
        return self.policy.act(obs)


class NoTerminalValue(MPCPolicy):
    """Sin valor de la carga al final del horizonte (el LP cree que lo que sobra no vale nada)."""

    def terminal_value(self, obs, H):
        return 0.0


class NoEndEmptying(MPCPolicy):
    """No detecta el final del episodio: nunca vacía la batería a propósito."""

    def episode_ends_soon(self, obs):
        return False


class NoDischargeCap(MPCPolicy):
    """Sin el tope de descarga por la última lectura del contador."""

    def cap_discharge(self, action_kw, obs):
        return action_kw


class PerfectForecaster:
    """Conoce el consumo y la solar reales (hace trampa: mide lo que cuesta nuestra previsión)."""

    def __init__(self, df):
        self.load = df["load_kw"].to_numpy(float)
        self.pv = df["pv_kw"].to_numpy(float)
        self.t = -1

    def update(self, obs):
        self.t += 1

    def forecast(self, obs, h):
        return self.load[self.t:self.t + h], self.pv[self.t:self.t + h]


class FlatForecaster:
    """Previsión tonta: consumo constante de 1.000 kW y solar 0."""

    def update(self, obs):
        pass

    def forecast(self, obs, h):
        return np.full(h, 1000.0), np.zeros(h)


def make(kind, df):
    if kind == "greedy":
        return GreedyAgent()
    if kind == "mpc":
        return BatteryAgent()
    if kind == "sin_valor_final":
        return _Wrap(NoTerminalValue())
    if kind == "sin_vaciar":
        return _Wrap(NoEndEmptying())
    if kind == "sin_tope":
        return _Wrap(NoDischargeCap())
    if kind == "prevision_perfecta":
        pol = NoDischargeCap()   # con el consumo real no hace falta el tope
        pol.forecaster = PerfectForecaster(df)
        return _Wrap(pol)
    if kind == "prevision_plana":
        pol = MPCPolicy()
        pol.forecaster = FlatForecaster()
        return _Wrap(pol)
    if kind == "oracle":
        base = baseline_totals(df)
        return OracleAgent(df, *score_weights(base["co2_kg"] / len(df), base["cost_eur"] / len(df)))
    raise ValueError(kind)


# ----------------------------------------------------------------------- evaluaciones
def run(kind, df, fc_noise=0.0, seed=0):
    res = simulate(make(kind, df), df, fc_noise=fc_noise, seed=seed)
    return score(res.totals, baseline_totals(df))


def weeks(df):
    """Las semanas de validación (bloques seguidos de 168 h, uno por mes)."""
    month = df["timestamp"].dt.to_period("M")
    return [g.reset_index(drop=True) for _, g in df.groupby(month)]


def run_weekly(kind, df):
    """Cada semana por separado: agente nuevo, carga al 50 % y previsión recortada al final."""
    tot = {"co2_kg": 0.0, "cost_eur": 0.0, "infractions": 0}
    base = {"co2_kg": 0.0, "cost_eur": 0.0}
    for wk in weeks(df):
        res = simulate(make(kind, wk), wk)
        b = baseline_totals(wk)
        for k in tot:
            tot[k] += res.totals[k]
        for k in base:
            base[k] += b[k]
    return score(tot, base)


def fmt(x):
    return f"{x:.2f}".replace(".", ",")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    if is_synthetic():
        sys.exit("Hacen falta los datos oficiales: python scripts/preparar_oficial.py")
    df = validation_split(load())
    lines = ["# P1 · Desglose de piezas y robustez", "",
             f"Validación con datos oficiales: {len(df)} h ({len(weeks(df))} semanas, una por mes). "
             "Generado por `python scripts/p1_ablaciones.py`.", ""]

    # 1. Ablaciones
    ref = run("mpc", df)
    orc = run("oracle", df)
    rows = [
        ("Reglas simples (greedy)", "greedy", "Sin planificar: lo que aporta el LP"),
        ("**Agente completo (MPC)**", "mpc", ""),
        ("MPC sin valor de la carga al final del horizonte", "sin_valor_final", "El plan de 24 h vacía la batería cada día"),
        ("MPC sin vaciar al final del episodio", "sin_vaciar", "La carga final se queda sin usar"),
        ("MPC sin tope de descarga (última lectura del contador)", "sin_tope", "Avería del contador: 14 h marcando 0"),
        ("MPC con previsión plana (1.000 kW, sin solar)", "prevision_plana", "Lo que aporta nuestra previsión"),
        ("MPC con consumo y solar reales (trampa)", "prevision_perfecta", "Lo que ganaríamos con previsión perfecta"),
        ("Óptimo con todo el futuro (oracle)", "oracle", "Techo teórico"),
    ]
    lines += ["## 1. ¿Cuánto aporta cada pieza?", "",
              "| Variante | Score | ΔCO₂ % | ΔCoste % | Infr. | Diferencia con el agente | Qué mide |",
              "|---|---|---|---|---|---|---|"]
    print(f"{'variante':<58}{'score':>7}{'dif':>7}{'infr':>5}")
    for label, kind, what in rows:
        sc = ref if kind == "mpc" else orc if kind == "oracle" else run(kind, df)
        d = sc["score_raw"] - ref["score_raw"]
        dtxt = "—" if kind == "mpc" else ("+" if d >= 0 else "−") + fmt(abs(d))
        lines.append(f"| {label} | {fmt(sc['score'])} | {fmt(sc['d_co2_pct'])} | {fmt(sc['d_cost_pct'])} | "
                     f"{sc['infractions']} | {dtxt} | {what} |")
        print(f"{label:<58}{sc['score']:>7.2f}{d:>+7.2f}{sc['infractions']:>5d}")

    # 2. Por semanas
    lines += ["", "## 2. ¿Y si el servidor evalúa cada semana por separado?", "",
              "Cada semana con un agente nuevo, la carga reiniciada al 50 % y la previsión recortada al final "
              "de la semana (el agente vacía la batería al final de cada una).", "",
              "| Agente | Seguido (nuestra validación) | Por semanas | Infr. por semanas |", "|---|---|---|---|"]
    print("\npor semanas:")
    for label, kind in [("MPC", "mpc"), ("Oracle", "oracle")]:
        w = run_weekly(kind, df)
        cont = ref if kind == "mpc" else orc
        lines.append(f"| {label} | {fmt(cont['score'])} | {fmt(w['score'])} | {w['infractions']} |")
        print(f"  {label:<8} seguido {cont['score']:.2f}   por semanas {w['score']:.2f}   infr {w['infractions']}")

    # 3. Ruido
    seeds = [0, 1] if args.quick else [0, 1, 2, 3, 4]
    lines += ["", "## 3. ¿Y si las previsiones de precio y CO₂ fallan?", "",
              f"Ruido multiplicativo que crece con la antelación (hasta el porcentaje indicado a 24 h). "
              f"Media de {len(seeds)} semillas.", "",
              "| Ruido | Score medio | Peor semilla | Infracciones (total) |", "|---|---|---|---|",
              f"| 0 % (oficial) | {fmt(ref['score'])} | {fmt(ref['score'])} | {ref['infractions']} |"]
    print("\nruido en precio/CO2:")
    for noise in (0.05, 0.10, 0.20):
        scs = [run("mpc", df, fc_noise=noise, seed=s) for s in seeds]
        vals = [s["score"] for s in scs]
        inf = sum(s["infractions"] for s in scs)
        lines.append(f"| {int(noise * 100)} % | {fmt(np.mean(vals))} | {fmt(min(vals))} | {inf} |")
        print(f"  {int(noise * 100):>3d} %  media {np.mean(vals):.2f}  peor {min(vals):.2f}  infr {inf}")

    lines += ["", "## 4. ¿Se sostiene fuera de la validación?", "",
              "El agente no tiene parámetros ajustados sobre la validación, así que el train también sirve de prueba. "
              "Episodios largos (> 2.016 h) incluidos: el agente no depende de la duración del test.", "",
              "| Datos | Horas | MPC | Oracle | % del techo | Infr. | Tiempo |", "|---|---|---|---|---|---|---|"]
    print("\nfuera de muestra:")
    full = load()
    for name, d in (("Validación", df), ("Train (3 primeras semanas de cada mes)", train_split(full)),
                    ("Todo el histórico seguido", full)):
        b = baseline_totals(d)
        r = simulate(make("mpc", d), d)
        m = score(r.totals, b)
        o = score(simulate(make("oracle", d), d).totals, b)
        pct = 100 * m["score_raw"] / o["score_raw"]
        lines.append(f"| {name} | {len(d)} | {fmt(m['score'])} | {fmt(o['score'])} | {fmt(pct)} % | "
                     f"{m['infractions']} | {fmt(r.totals['runtime_s'])} s |")
        print(f"  {name:<40}{len(d):>5} h  mpc {m['score']:.2f}  oracle {o['score']:.2f}  {pct:.1f} %  infr {m['infractions']}")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nTablas en {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
