"""v12 con distintas fuerzas de mezcla, ajustadas de forma coherente (para mejora_grid.py)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mejora_cands as mc
import p1_hard as b
_C = {}


def blend(strength):
    def f(prior, solar_prior, exclude):
        key = (strength, len(exclude), min(exclude))
        if key not in _C:
            old = b.MARKET_BLEND
            b.MARKET_BLEND = strength
            full = b.hard_table()
            _C[key] = b.fit_market(exclude, full[~full.timestamp.isin(exclude)])
            b.MARKET_BLEND = old
        a = mc.hard_agent(_C[key], solar_prior)
        a.policy.netload.z_by_month = None
        return a
    return f


CANDS = {"base": mc.v10_old_market, "mezcla 1.0": blend(1.0), "mezcla 0.5": blend(0.5), "mezcla 0.7": blend(0.7)}
