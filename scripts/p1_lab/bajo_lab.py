"""Laboratorio del encargo "consumo bajo" (semanas normales con poco consumo). NO se empaqueta.

Owner: P1. Piezas de diagnóstico que usan bajo_diag.py y bajo_pruebas.py:

    LabPolicy        MPCPolicy con interruptores para medir cuánto vale cada información que el agente
                     no tiene (consumo real de las próximas 24 h, R real del episodio, lectura de la
                     primera hora de cada semana, tope de descarga con el consumo real de la hora).
    hourly_weights   lo que cuesta, en puntos de score del episodio, cada kWh comprado en cada hora.
    tail_cost        coste del óptimo desde una hora y una carga dadas ("el óptimo a partir de aquí").
    regret_by_week   reparto exacto de la distancia al óptimo entre las 12 semanas.

Los agentes "informados" hacen trampa a propósito (leen el episodio): solo sirven para medir techos.
"""
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from battery.optimizer import plan, score_weights  # noqa: E402
from battery.policy import MPCPolicy  # noqa: E402
from battery.sim import baseline_totals  # noqa: E402

WEEK = 168


def episode_weights(df) -> tuple:
    """Pesos del LP con las referencias reales del episodio (los que usa el óptimo)."""
    b = baseline_totals(df)
    return score_weights(b["co2_kg"] / len(df), b["cost_eur"] / len(df))


def hourly_weights(df) -> np.ndarray:
    """Puntos de score que cuesta cada kWh comprado en cada hora: score = 100 - sum(w_t * compra_t)."""
    b = baseline_totals(df)
    return 100.0 * (0.7 * df.co2_kg_kwh.to_numpy() / b["co2_kg"] + 0.3 * df.price_eur_kwh.to_numpy() / b["cost_eur"])


def tail_cost(df, w, t0: int, soc0: float, wc: float, wk: float, horizon: int = 0) -> float:
    """Coste (puntos de score) del óptimo desde la hora t0 con la carga soc0 (hasta el final, o `horizon` h)."""
    if t0 >= len(df):
        return 0.0
    t1 = len(df) if not horizon else min(len(df), t0 + horizon)
    d = df.iloc[t0:t1]
    net = d.load_kw.to_numpy() - d.pv_kw.to_numpy()
    a = plan(soc0, d.load_kw.to_numpy(), d.pv_kw.to_numpy(), d.price_eur_kwh.to_numpy(),
             d.co2_kg_kwh.to_numpy(), wc, wk, 0.0)
    return float((np.maximum(net + a, 0.0) * w[t0:t1]).sum())


def regret_by_week(log, df) -> np.ndarray:
    """Distancia al óptimo generada en cada semana: lo pagado en la semana más el óptimo desde la carga
    con la que se sale, menos el óptimo desde la carga con la que se entró. Suma la distancia total."""
    wc, wk = episode_weights(df)
    w = hourly_weights(df)
    imp, soc = log.import_kw.to_numpy(), log.soc_kwh.to_numpy()
    n_weeks = len(df) // WEEK
    v = [tail_cost(df, w, 0, 1000.0, wc, wk)]
    for i in range(1, n_weeks + 1):
        v.append(tail_cost(df, w, i * WEEK, soc[i * WEEK - 1], wc, wk))
    paid = (imp * w).reshape(n_weeks, WEEK).sum(1)
    return np.array([paid[i] + v[i + 1] - v[i] for i in range(n_weeks)])


def regret_by_hour(log, df, t0: int, t1: int, horizon: int = 240) -> np.ndarray:
    """Distancia al óptimo generada en cada hora de [t0, t1): aproximada con un óptimo de `horizon` horas."""
    wc, wk = episode_weights(df)
    w = hourly_weights(df)
    imp, soc = log.import_kw.to_numpy(), log.soc_kwh.to_numpy()
    out = []
    end = min(len(df), t1 + horizon)
    for t in range(t0, t1):
        s0 = soc[t - 1] if t > 0 else 1000.0
        v0 = tail_cost(df, w, t, s0, wc, wk, end - t)
        v1 = tail_cost(df, w, t + 1, soc[t], wc, wk, end - t - 1)
        out.append(imp[t] * w[t] + v1 - v0)
    return np.array(out)


class PerfectForecaster:
    """Previsión perfecta: lee el consumo y la solar reales del episodio. Solo para medir techos."""

    def __init__(self, df, policy):
        self.load = df.load_kw.to_numpy(float)
        self.pv = df.pv_kw.to_numpy(float)
        self.policy = policy

    def update(self, obs) -> None:
        return None

    def forecast(self, obs, h: int) -> tuple:
        t = self.policy.t
        load, pv = self.load[t:t + h], self.pv[t:t + h]
        if len(load) < h:
            pad = h - len(load)
            load = np.concatenate([load, np.full(pad, load[-1] if len(load) else 0.0)])
            pv = np.concatenate([pv, np.full(pad, pv[-1] if len(pv) else 0.0)])
        return load.copy(), pv.copy()


class LabPolicy(MPCPolicy):
    """MPCPolicy con interruptores de información (para descomponer la distancia al óptimo).

    df            el episodio (solo lo usan los interruptores "informados")
    perfect_fc    None | 'all' (consumo real de las 24 h) | 'now' (solo el de la hora actual)
    cap           'prev' (como v2: última lectura) | 'none' | 'true' (consumo real de la hora)
    true_w        usar los pesos reales del episodio en vez de los del train
    first         'nan' (como v2) | 'true' (en la primera hora de cada semana se conoce el consumo de esa hora)
    """

    def __init__(self, df=None, perfect_fc=None, cap="prev", true_w=False, first="nan", **kw):
        super().__init__(**kw)
        self.df = df
        self.perfect_fc = perfect_fc
        self.cap_mode = cap
        self.first = first
        if df is not None:
            self.true_load = df.load_kw.to_numpy(float)
            self.true_pv = df.pv_kw.to_numpy(float)
        if true_w:
            self.w_co2, self.w_cost = episode_weights(df)
        if perfect_fc == "all":
            self.forecaster = PerfectForecaster(df, self)
        elif perfect_fc == "now":
            inner = self.forecaster
            pol = self

            class NowForecaster:
                def update(self, obs):
                    inner.update(obs)

                def forecast(self, obs, h):
                    load, pv = inner.forecast(obs, h)
                    load[0], pv[0] = pol.true_load[pol.t], pol.true_pv[pol.t]
                    return load, pv

            self.forecaster = NowForecaster()

    def cap_discharge(self, action_kw: float, obs) -> float:
        if self.cap_mode == "none":
            return action_kw
        if self.cap_mode == "true":
            net = self.true_load[self.t] - self.true_pv[self.t]
            return -min(-action_kw, max(net, 0.0)) if action_kw < 0 else action_kw
        return super().cap_discharge(action_kw, obs)

    def act_obs(self, obs) -> float:
        try:
            new_block = self.track_block(obs)
        except Exception:
            new_block, self.no_data_block = False, False
        if new_block:
            if self.first == "true":
                obs = obs._replace(load_prev_kw=float(self.true_load[self.t]), pv_prev_kw=float(self.true_pv[self.t]))
            else:
                obs = obs._replace(load_prev_kw=float("nan"), pv_prev_kw=float("nan"))
        try:
            self.note_weight(obs)
        except Exception:
            pass
        return self.cap_discharge(self.plan_action(obs), obs)


class Wrap:
    """Envoltorio con la interfaz oficial act(obs)."""

    def __init__(self, policy):
        self.policy = policy

    def act(self, obs):
        return self.policy.act(obs)
