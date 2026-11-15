"""Comprobación tras la revisión de la decisión: base = src (v10 + tope de descarga con la previsión), "v10" = el
tope de siempre. NO se empaqueta."""
import sys
import types
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "scripts"))
from p1_hard import hard_agent  # noqa: E402
from battery.policy import MPCPolicy  # noqa: E402


def base(prior, solar_prior, exclude):
    return hard_agent(prior, solar_prior)


def v10(prior, solar_prior, exclude):
    a = hard_agent(prior, solar_prior)
    a.policy.cap_discharge = types.MethodType(MPCPolicy.cap_discharge, a.policy)
    return a


CANDS = {"base": base, "v10": v10}
