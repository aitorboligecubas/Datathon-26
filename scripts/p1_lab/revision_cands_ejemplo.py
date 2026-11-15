"""Ejemplo de candidatos para mejora_privado.py: base = v10; v9-margen en verano."""
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "scripts"))
from p1_hard import hard_agent


def base(prior, solar_prior, exclude):      # v10 tal cual
    return hard_agent(prior, solar_prior)


def margen14(prior, solar_prior, exclude):  # margen 1,4 todo el año (v9)
    a = hard_agent(prior, solar_prior)
    a.policy.netload.z = a.policy.netload.z_plan = 1.4
    return a


CANDS = {"base": base, "margen 1,4": margen14}
