"""¿Qué firma deja en la mitad pública un agente que llega con la batería llena a cada semana (o a cada media semana)?

La web puntúa el 50 % de cada semana del test. Si esa mitad fuera un tramo seguido, cargar la batería en la otra
mitad mueve el coste de la carga a horas que el público no ve: la nota pública sube y la privada baja lo mismo.
Aquí se mide en casa, con el calendario real del episodio, cuánto sube y cuánto baja, y se compara con el óptimo
que conoce todo el futuro. No se usa para diseñar el agente: es para saber leer el ranking.

    python scripts/p1_lab/hard_publico_llegar_lleno.py val      # también dev, 1-7
"""
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
REPO = Path(__file__).resolve().parents[2]
for extra in (str(REPO / "src"), str(REPO / "scripts"), str(REPO / "scripts" / "p1_lab")):
    if extra not in sys.path:
        sys.path.insert(0, extra)
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import p1_hard as B  # noqa: E402
from hard_rev_perdidas_salto import CalPolicy  # noqa: E402

win = sys.argv[1]
full = B.hard_table()
df = B.split_frame(full, win)
exclude = set(df.timestamp)
fit_df = full[~full.timestamp.isin(exclude)]
old_market = B.fit_market(exclude, fit_df, blend=False, weekend=False)
solar = B.fit_solar(fit_df)
ts = list(pd.DatetimeIndex(df.timestamp))
nxt = dict(zip(ts[:-1], ts[1:]))
n = len(df)
hw = np.arange(n) % 168
ETA = 0.9 ** 0.5


def v10():
    a = B.hard_agent(old_market, solar, use_scenarios=False)
    a.policy.__class__ = CalPolicy
    a.policy.nxt = nxt
    return a


class Lleno:
    """El agente de dentro, salvo en las últimas `k` horas del tramo que acaba en `end`: ahí carga todo lo que cabe."""

    def __init__(self, inner, end, k=5):
        self.inner, self.end, self.k, self.t = inner, end, k, 0

    def act(self, obs):
        a = float(self.inner.act(obs))
        phase = self.t % 168
        self.t += 1
        if self.end - self.k <= phase < self.end:
            room = (float(obs["cap_max_kwh"]) - float(obs["soc_kwh"])) / ETA
            return float(min(float(obs["power_max_kw"]), max(room - 1e-6, 0.0)))
        return a


def oracle(keep=None):
    """El óptimo con todo el futuro. Con `keep`, el óptimo de quien solo mira esas horas (el resto no le cuesta)."""
    d = df.copy()
    if keep is not None:
        d.loc[~keep, ["price_eur_kwh", "co2_kg_kwh"]] = 0.0
    base = B.baseline_totals(df)
    w = B.score_weights(base["co2_kg"] / len(df), base["cost_eur"] / len(df))
    return B.OracleAgent(d, *w, p=B.HARD_PARAMS)


VARS = {"v10": v10, "v10 + llega llena a cada semana": lambda: Lleno(v10(), 168),
        "v10 + llega llena a media semana": lambda: Lleno(v10(), 84),
        "óptimo (todo el futuro)": oracle,
        "óptimo de quien solo mira la 1.ª mitad": lambda: oracle(hw < 84),
        "óptimo de quien solo mira la 2.ª mitad": lambda: oracle(hw >= 84)}
base_imp = np.maximum(df.load_kw - df.pv_kw, 0).to_numpy(float)
co2, eur = df.co2_kg_kwh.to_numpy(float), df.price_eur_kwh.to_numpy(float)
MASKS = {"todo": np.ones(n, bool), "1.ª mitad de cada semana": hw < 84, "2.ª mitad de cada semana": hw >= 84}


def line(name, imp, infr):
    out = []
    for label, m in MASKS.items():
        dc = 100 * ((base_imp - imp) * co2)[m].sum() / (base_imp * co2)[m].sum()
        de = 100 * ((base_imp - imp) * eur)[m].sum() / (base_imp * eur)[m].sum()
        out.append(f"{label}: {0.7 * dc + 0.3 * de:6.2f} (CO2 {dc:5.2f} coste {de:5.2f})")
    print(f"{win:5s} {name:40s} infr {infr} | " + " | ".join(out), flush=True)


for name, mk in VARS.items():
    totals, log = B.simulate_hard(mk(), df)
    line(name, log.import_kw.to_numpy(float), totals["infractions"])
