"""Revisión "logica" (HARD MODE). NO se empaqueta. Candidato de medida, no toca src/ ni models/.

Sospecha: la regresión del previsor de precio y CO2 (models/hard_market.json, "cand") se ajusta con
crossfit = False (scripts/p1_lab/hard_market_cand.py, DEFAULT_CFG): la desviación z = log(real / perfil) de cada
hora del train se mide contra un perfil que INCLUYE esa misma hora. En el test (días 25-31) el perfil sale de
otros días (1-24): la z del test lleva además el desnivel de la semana, que dentro de la muestra no existe.
El propio laboratorio ya trae la variante `crossfit` (cada bloque de 7 días contra el perfil del resto del mes,
"igual que una semana del test"). Aquí se mide con el perfil de la v14 (interpolado y fines de semana suavizados).

    python scripts/p1_hard.py --split dev --only "agente actual,CANDIDATO" --agent scripts/p1_lab/hard_rev_logica_crossfit.py:make
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for extra in (str(REPO / "src"), str(REPO / "scripts"), str(REPO / "scripts" / "p1_lab")):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import p1_hard as bench  # noqa: E402
from hard_market_cand import fit_cand  # noqa: E402


def make(prior: dict, solar_prior: dict, exclude: set):
    prior2 = dict(prior)
    prior2["cand"] = fit_cand(exclude or None, {"blend": True, "weekend": True, "crossfit": True})
    return bench.hard_agent(prior2, solar_prior)
