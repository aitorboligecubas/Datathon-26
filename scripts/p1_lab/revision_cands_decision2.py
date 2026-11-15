"""Candidatos (2) de la revisión de la capa de DECISIÓN: transiciones entre semanas. base = v10. NO se empaqueta."""
import sys
import types
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "scripts"))
from p1_hard import hard_agent  # noqa: E402
from battery.hard import LAST_MONTHS  # noqa: E402


def base(prior, solar_prior, exclude):
    return hard_agent(prior, solar_prior)


def cutweek(prior, solar_prior, exclude):
    """El plan no cruza a la semana del mes siguiente (que solo conoce por el perfil): se corta al acabar el mes y lo
    que quede en la batería vale el cuantil 25 % del peso del horizonte (como al final de cualquier horizonte)."""
    a = hard_agent(prior, solar_prior)
    pol = a.policy
    orig_times, orig_plan = pol.horizon_times, pol.plan_action

    def horizon_times(self, obs):
        times = orig_times(obs)
        for i in range(1, len(times)):
            if times[i].month != times[i - 1].month:
                times = times[:i]
                self.horizon = len(times)   # no es el final del test: se mantiene el valor terminal
                break
        return times

    def plan_action(self, obs):
        self.horizon = 24
        return orig_plan(obs)
    pol.horizon_times = types.MethodType(horizon_times, pol)
    pol.plan_action = types.MethodType(plan_action, pol)
    return a


def cross36(prior, solar_prior, exclude):
    """Cuando el plan de 24 h cruza a la semana siguiente, horizonte de 36 h: ve medio día más de la semana nueva."""
    a = hard_agent(prior, solar_prior)
    pol = a.policy
    orig_times, orig_plan = pol.horizon_times, pol.plan_action

    def plan_action(self, obs):
        self.horizon = 24
        ts = obs.timestamp
        if ts is not None and (ts.year, ts.month) not in LAST_MONTHS:
            t = orig_times(obs)
            if any(t[i].month != t[i - 1].month for i in range(1, len(t))):
                self.horizon = 36
        return orig_plan(obs)
    pol.plan_action = types.MethodType(plan_action, pol)
    return a


CANDS = {"base": base, "cutweek": cutweek, "cross36": cross36}
