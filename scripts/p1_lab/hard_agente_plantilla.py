"""Plantilla de candidato de AGENTE COMPLETO para el banco del modo difícil. NO se empaqueta.

Owner: P1 (laboratorio). Copia este fichero, cambia lo que quieras dentro de la política y mídelo con:

    python scripts/p1_hard.py --split dev --agent scripts/p1_lab/MI_FICHERO.py:make --only "agente actual,CANDIDATO"

`make(prior, solar_prior, exclude)` recibe las tablas de mercado y de consumo/solar ajustadas SIN las horas
del split que se evalúa (las mismas que usa el agente actual) y devuelve un objeto con `.act(obs) -> float`.
Tal cual está, esta plantilla reproduce al agente actual.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for extra in (str(REPO / "src"), str(REPO / "scripts")):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import p1_hard as bench  # noqa: E402
from battery.hard import HardPolicy  # noqa: E402


class CandPolicy(HardPolicy):
    """Hereda de la política del modo difícil. Sobrescribe aquí plan_action, act_obs o lo que haga falta."""


def make(prior: dict, solar_prior: dict, exclude: set):
    agent = bench.hard_agent(prior, solar_prior)      # política actual con las tablas ajustadas sin el split
    agent.policy.__class__ = CandPolicy               # mismas tablas y estado, con los métodos del candidato
    return agent
