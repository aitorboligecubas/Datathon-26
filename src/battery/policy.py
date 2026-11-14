"""Política principal y `BatteryAgent` (la clase que carga el evaluador).

Owner: P1 (optimizador).

MPC (control predictivo) con LP en horizonte deslizante. Cada hora:
1. Traduce la observación oficial a `Obs` (adapter).
2. Actualiza la previsión con la demanda y la solar de la hora anterior (forecaster).
3. Resuelve el LP de las próximas H = 24 horas con precio y CO2 previstos (optimizer).
4. Aplica solo la primera hora, recortada a los límites físicos (safety).

Robustez: si algo falla o nos acercamos al límite de tiempo, pasa a la regla
greedy. El agente nunca lanza una excepción ni devuelve una acción inválida.

Este fichero se empaqueta en dist/agent.py junto con params, obs, adapter,
safety, forecaster y optimizer (scripts/build_submission.py). Solo imports permitidos.
"""
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

from .adapter import from_official
from .forecaster import FORECASTER_FILE, Forecaster
from .obs import Obs
from .optimizer import plan, score_weights
from .params import DEFAULT_PARAMS, N_STEPS, TIME_BUDGET_S, BatteryParams
from .safety import clip_action

REFS_FILE = "objective_refs.json"
# Media horaria de CO2 (kg) y coste (€) sin batería. Se sobrescriben con
# models/objective_refs.json, que genera scripts/train_forecaster.py con los datos reales.
DEFAULT_REFS = {"co2_ref_kg_per_h": 60.0, "cost_ref_eur_per_h": 50.0}


def find_models_dir() -> Optional[Path]:
    """Carpeta con los artefactos: junto a agent.py en el ZIP, o models/ en el repo."""
    try:
        here = Path(__file__).resolve().parent
    except NameError:
        here = Path(".").resolve()
    for cand in (here, here.parent.parent / "models", Path(".").resolve()):
        if (cand / REFS_FILE).exists() or (cand / FORECASTER_FILE).exists():
            return cand
    return None


def load_json(models_dir: Optional[Path], name: str) -> Optional[dict]:
    if models_dir is None or not (models_dir / name).exists():
        return None
    with open(models_dir / name) as fh:
        return json.load(fh)


def greedy_action(obs: Obs, load_kw: float, pv_kw: float,
                  p: BatteryParams = DEFAULT_PARAMS, co2_quantile: float = 0.66) -> float:
    """Regla de respaldo: excedente solar -> cargar; CO2 alto -> cubrir la demanda."""
    net = load_kw - pv_kw
    if not math.isfinite(net):
        return 0.0
    if net < 0 or obs.co2[0] >= np.quantile(obs.co2, co2_quantile):
        return clip_action(-net, obs.soc_kwh, p)
    return 0.0


class MPCPolicy:
    def __init__(self, p: BatteryParams = DEFAULT_PARAMS, models_dir: Optional[Path] = None,
                 horizon: int = 24, terminal_quantile: float = 0.25,
                 n_steps: int = N_STEPS, time_budget_s: float = TIME_BUDGET_S):
        self.p = p
        self.horizon = horizon
        self.terminal_quantile = terminal_quantile
        self.n_steps = n_steps
        self.time_budget_s = time_budget_s
        if models_dir is None:
            models_dir = find_models_dir()
        self.forecaster = Forecaster(load_json(models_dir, FORECASTER_FILE))
        refs = load_json(models_dir, REFS_FILE) or DEFAULT_REFS
        self.w_co2, self.w_cost = score_weights(refs["co2_ref_kg_per_h"], refs["cost_ref_eur_per_h"])
        self.t = 0
        self.elapsed_s = 0.0
        self.n_fallbacks = 0

    def episode_ends_soon(self, obs: Obs) -> bool:
        """environment.py recorta la previsión al final de los datos: si llega con menos de
        24 valores, el episodio acaba dentro del horizonte. (El test tiene ~1.700 h, no 2.016.)"""
        return len(obs.price) < self.horizon or self.n_steps - self.t <= self.horizon

    def terminal_value(self, obs: Obs, H: int) -> float:
        """Valor de cada kWh que quede en la batería al final del horizonte."""
        if self.episode_ends_soon(obs):
            return 0.0  # la carga final no puntúa (environment.py): mejor gastarla
        marginal = self.w_co2 * obs.co2[:H] + self.w_cost * obs.price[:H]
        return float(np.quantile(marginal, self.terminal_quantile)) * self.p.eta_discharge

    def act_obs(self, obs: Obs) -> float:
        """Acción interna en kW (+ carga), ya recortada a los límites."""
        self.forecaster.update(obs)
        H = max(1, min(self.horizon, len(obs.price), self.n_steps - self.t))
        load, pv = self.forecaster.forecast(obs, H)
        if self.elapsed_s > self.time_budget_s:
            self.n_fallbacks += 1
            return greedy_action(obs, load[0], pv[0], self.p)
        try:
            actions = plan(obs.soc_kwh, load, pv, obs.price[:H], obs.co2[:H],
                           self.w_co2, self.w_cost, self.terminal_value(obs, H), self.p)
            return clip_action(actions[0], obs.soc_kwh, self.p)
        except Exception:
            self.n_fallbacks += 1
            return greedy_action(obs, load[0], pv[0], self.p)

    def act(self, raw_obs) -> float:
        t0 = datetime.now()
        try:
            a = self.act_obs(from_official(raw_obs))
            if not math.isfinite(a):
                a = 0.0
        except Exception:
            self.n_fallbacks += 1
            a = 0.0
        self.t += 1
        self.elapsed_s += (datetime.now() - t0).total_seconds()
        return float(a)


class BatteryAgent:
    """Punto de entrada que llama el evaluador (firma de oficial/starter_kit/agent.py)."""

    def __init__(self):
        self.policy = MPCPolicy()

    def act(self, obs) -> float:
        """Devuelve la potencia en kW: > 0 carga, < 0 descarga."""
        return self.policy.act(obs)
