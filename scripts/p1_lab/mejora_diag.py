"""Diagnósticos y candidatos de la rama `mejora-score-hard` (modo difícil). NO se empaqueta.

Cada función es una fábrica para `scripts/p1_hard.py --agent ruta.py:func`:
    func(prior, solar_prior, exclude) -> agente con .act(obs)

    python scripts/p1_hard.py --split val --agent scripts/p1_lab/mejora_diag.py:perfect_all --only CANDIDATO
"""
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import p1_hard  # noqa: E402
from p1_hard import _TrueMarket, hard_agent, hard_table  # noqa: E402

_TABLE = None


def table():
    global _TABLE
    if _TABLE is None:
        _TABLE = hard_table()
    return _TABLE


class TrueNetload:
    """Previsor tramposo de consumo y solar: los valores reales de las fechas pedidas (techo de esa previsión)."""

    def __init__(self, df):
        self.load = dict(zip(df.timestamp, df.load_kw))
        self.pv = dict(zip(df.timestamp, df.pv_kw))

    def new_block(self):
        pass

    def update(self, obs, weather=None):
        pass

    def forecast(self, obs, times):
        load = np.array([self.load.get(t, np.nan) for t in times], dtype=float)
        pv = np.array([self.pv.get(t, np.nan) for t in times], dtype=float)
        for a in (load, pv):
            bad = ~np.isfinite(a)
            if bad.any():
                a[bad] = a[~bad][-1] if (~bad).any() else 0.0
        return load, pv

    def adjust_action(self, action_kw, obs, p):
        return action_kw


def _with(prior, solar_prior, market=False, netload=False, **cfg):
    a = hard_agent(prior, solar_prior, **cfg)
    df = table()
    if market:
        a.policy.market = _TrueMarket(df)
    if netload:
        a.policy.netload = TrueNetload(df)
        a.policy.cap_discharge = lambda action, obs: action
    return a


# --- diagnósticos (techos parciales)
def perfect_netload(prior, solar_prior, exclude):
    return _with(prior, solar_prior, netload=True)


def perfect_all(prior, solar_prior, exclude):
    return _with(prior, solar_prior, market=True, netload=True)


def perfect_all_h48(prior, solar_prior, exclude):
    return _with(prior, solar_prior, market=True, netload=True, horizon=48)


# --- candidatos de horizonte y valor terminal
def h36(prior, solar_prior, exclude):
    return hard_agent(prior, solar_prior, horizon=36)


def h48(prior, solar_prior, exclude):
    return hard_agent(prior, solar_prior, horizon=48)


def tq10(prior, solar_prior, exclude):
    return hard_agent(prior, solar_prior, terminal_quantile=0.10)


def tq40(prior, solar_prior, exclude):
    return hard_agent(prior, solar_prior, terminal_quantile=0.40)


def tq50(prior, solar_prior, exclude):
    return hard_agent(prior, solar_prior, terminal_quantile=0.50)


# --- desempate del LP (coste diminuto por kWh cargado, descargado o vertido)
def tb001(prior, solar_prior, exclude):
    return hard_agent(prior, solar_prior, tie_break=0.001)


def tb01(prior, solar_prior, exclude):
    return hard_agent(prior, solar_prior, tie_break=0.01)


def tb03(prior, solar_prior, exclude):
    return hard_agent(prior, solar_prior, tie_break=0.03)


def perfect_all_tb(prior, solar_prior, exclude):
    return _with(prior, solar_prior, market=True, netload=True, tie_break=0.001)


def perfect_all_h72(prior, solar_prior, exclude):
    return _with(prior, solar_prior, market=True, netload=True, horizon=72)


def perfect_market_h48(prior, solar_prior, exclude):
    return _with(prior, solar_prior, market=True, horizon=48)


def _true_weights(a):
    from battery.optimizer import score_weights
    from battery.sim import baseline_totals
    from p1_hard import split_frame
    import p1_hard
    df = split_frame(table(), "val")
    b = baseline_totals(df)
    a.policy.w_co2, a.policy.w_cost = score_weights(b["co2_kg"] / len(df), b["cost_eur"] / len(df))
    return a


def perfect_all_truew(prior, solar_prior, exclude):
    return _true_weights(_with(prior, solar_prior, market=True, netload=True))


def base_truew(prior, solar_prior, exclude):
    return _true_weights(hard_agent(prior, solar_prior))


def show_weights(prior, solar_prior, exclude):
    a = hard_agent(prior, solar_prior)
    w1 = (a.policy.w_co2, a.policy.w_cost)
    _true_weights(a)
    print("pesos agente", w1, "ratio", w1[0] / w1[1], "| pesos test", (a.policy.w_co2, a.policy.w_cost), "ratio", a.policy.w_co2 / a.policy.w_cost)
    print("solar_prior pesos", solar_prior["cand"].get("w_co2"), solar_prior["cand"].get("w_cost"))
    return hard_agent(prior, solar_prior)


class MixNetload:
    """Previsión real en unas antelaciones y verdad en otras. now_true: la hora actual exacta (sin margen);
    future_true: las horas siguientes exactas."""

    def __init__(self, real, df, now_true, future_true):
        self.real, self.true = real, TrueNetload(df)
        self.now_true, self.future_true = now_true, future_true

    def new_block(self):
        self.real.new_block()

    def update(self, obs, weather=None):
        self.real.update(obs, weather)

    def forecast(self, obs, times):
        lr, pr = self.real.forecast(obs, times)
        lt, pt = self.true.forecast(obs, times)
        load, pv = lr.copy(), pr.copy()
        if self.now_true:
            load[0], pv[0] = lt[0], pt[0]
        if self.future_true:
            load[1:], pv[1:] = lt[1:], pt[1:]
        return load, pv

    def adjust_action(self, action_kw, obs, p):
        return action_kw if self.now_true else self.real.adjust_action(action_kw, obs, p)


def _mix(prior, solar_prior, now_true, future_true):
    a = hard_agent(prior, solar_prior)
    a.policy.netload = MixNetload(a.policy.netload, table(), now_true, future_true)
    if now_true:
        a.policy.cap_discharge = lambda action, obs: action
    return a


def perfect_now(prior, solar_prior, exclude):
    return _mix(prior, solar_prior, True, False)


def perfect_future(prior, solar_prior, exclude):
    return _mix(prior, solar_prior, False, True)
