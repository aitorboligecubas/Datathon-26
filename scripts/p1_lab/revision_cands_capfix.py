"""Candidatos de la revisión de la capa de DECISIÓN (mejora_privado.py). base = v10. NO se empaqueta."""
import sys
import types
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "scripts"))
from p1_hard import hard_agent  # noqa: E402
from battery.hard import LAST_MONTHS  # noqa: E402


def base(prior, solar_prior, exclude):
    return hard_agent(prior, solar_prior)


def capfix(prior, solar_prior, exclude):
    """Con la previsión de esta hora disponible, el tope de 'lo comprado la hora anterior' no se aplica: manda el
    margen de adjust_action (consumo neto previsto). Así no se descarga MÁS que el plan cuando el tope actúa y uncap
    lo levanta hasta el límite previsto (caso tope < plan < límite)."""
    a = hard_agent(prior, solar_prior)
    pol = a.policy
    orig = pol.cap_discharge

    def cap(self, action, obs):
        if getattr(self.netload, "fresh", False) and getattr(self.netload, "uncap", False):
            return action
        return orig(action, obs)
    pol.cap_discharge = types.MethodType(cap, pol)
    return a


def end48(prior, solar_prior, exclude):
    """En el último mes del test, horizonte de 48 h: el plan ve el final del test un día antes."""
    a = hard_agent(prior, solar_prior)
    pol = a.policy
    orig = pol.plan_action

    def plan_action(self, obs):
        ts = obs.timestamp
        self.horizon = 48 if ts is not None and (ts.year, ts.month) in LAST_MONTHS else 24
        return orig(obs)
    pol.plan_action = types.MethodType(plan_action, pol)
    return a


CANDS = {"base": base, "capfix": capfix}
