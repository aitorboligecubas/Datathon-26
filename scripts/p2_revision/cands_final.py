"""Candidatos: base = v10 (perfil sin interpolar, margen fijo); v12 = plan con incertidumbre; final = v14 de p1-optimizador."""
import p1_hard as b

_FULL = {}


def _old_market(exclude):
    if "full" not in _FULL:
        _FULL["full"] = b.hard_table()
    full = _FULL["full"]
    return b.fit_market(exclude, full[~full.timestamp.isin(exclude)], blend=False, weekend=False)


def v10(prior, solar, exclude):
    return b.hard_agent(_old_market(exclude), solar, use_scenarios=False)


def v12(prior, solar, exclude):
    return b.hard_agent(_old_market(exclude), solar, use_scenarios=True)


def final(prior, solar, exclude):
    return b.hard_agent(prior, solar, use_scenarios=True)


CANDS = {"base": v10, "v12": v12, "final": final}
