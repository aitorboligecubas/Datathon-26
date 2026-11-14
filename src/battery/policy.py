"""Política principal y `BatteryAgent` (la clase que carga el evaluador).

Owner: P1 (optimizador).

MPC (control predictivo) con LP en horizonte deslizante. Cada hora:
1. Traduce la observación oficial a `Obs` (adapter).
2. Actualiza la previsión con la demanda y la solar de la hora anterior (forecaster).
3. Resuelve el LP de las próximas H = 24 horas con precio y CO2 previstos (optimizer).
4. Aplica solo la primera hora, recortada a los límites físicos (safety).

Robustez: si algo falla o nos acercamos al límite de tiempo, pasa a la regla
greedy. El agente nunca lanza una excepción ni devuelve una acción inválida.

Semanas sin datos de contador. El test son 12 semanas sueltas (la última de cada mes) puestas una
detrás de otra, así que entre una y la siguiente hay un salto de fechas. Si el contador marca 0 desde
la primera hora de una semana (en el train, noviembre no tiene datos de contador), el agente la
trata como "semana sin datos": no hay consumo que cubrir hasta que acabe el mes, así que no descarga
y compra la energía para la semana siguiente en una hora barata, con un precio de reserva (ver
`MPCPolicy.reserve_weight`). Una avería que empieza a media semana se sigue tratando como corta.

Este fichero se empaqueta en dist/agent.py junto con params, obs, adapter,
safety, forecaster y optimizer (scripts/build_submission.py). Solo imports permitidos.
"""
import json
import math
from collections import deque
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

BLOCK_GAP_H = 6        # un salto de fechas mayor que esto es un cambio de semana del test
LONG_OUTAGE_H = 24     # más de un día a 0 ya no es una avería corta: es un hueco de datos
VALLEY_DAYS = 35       # días recientes con los que se estima cuánto cuesta cargar en un día cualquiera
VALLEY_HOURS = 4       # llenar la batería son unas 4 horas a 500 kW
FINAL_MONTH = (2026, 8)  # el test acaba el 31/08/2026 (ENUNCIAT): después no hay semana siguiente
REFS_FILE = "objective_refs.json"
# Media horaria de CO2 (kg) y coste (€) sin batería en el train oficial. Es el último recurso si no
# se puede leer models/objective_refs.json ni su copia incrustada: aun así, los pesos serían los buenos.
DEFAULT_REFS = {"co2_ref_kg_per_h": 93.197, "cost_ref_eur_per_h": 156.321}
# El empaquetador (scripts/build_submission.py) copia aquí el contenido de models/*.json, para que
# agent.py decida igual aunque el servidor no encuentre los ficheros auxiliares del ZIP.
EMBEDDED_MODELS = {}


def find_models_dir() -> Optional[Path]:
    """Carpeta con los artefactos: junto a agent.py en el ZIP, o models/ en el repo."""
    try:
        here = Path(__file__).resolve().parent
    except Exception:
        here = Path(".")
    for cand in (here, here.parent.parent / "models", Path(".")):
        try:
            if (cand / REFS_FILE).exists() or (cand / FORECASTER_FILE).exists():
                return cand
        except Exception:
            continue
    return None


def load_json(models_dir: Optional[Path], name: str) -> Optional[dict]:
    """Lee un artefacto JSON. Si no está o no se puede leer, usa la copia incrustada (o None)."""
    if models_dir is not None:
        try:
            if (models_dir / name).exists():
                with open(models_dir / name) as fh:
                    return json.load(fh)
        except Exception:
            pass
    return EMBEDDED_MODELS.get(name)


def hours_to_month_end(ts) -> int:
    """Horas que quedan de mes, contando la actual. Cada semana del test acaba con su mes."""
    return int((ts.days_in_month - ts.day) * 24 + (24 - ts.hour))


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
        try:
            self.forecaster = Forecaster(load_json(models_dir, FORECASTER_FILE))
        except Exception:
            self.forecaster = Forecaster(None)   # sin perfil inicial: lo aprende sobre la marcha
        refs = load_json(models_dir, REFS_FILE) or DEFAULT_REFS
        try:
            self.w_co2, self.w_cost = score_weights(float(refs["co2_ref_kg_per_h"]),
                                                    float(refs["cost_ref_eur_per_h"]))
        except Exception:
            self.w_co2, self.w_cost = score_weights(DEFAULT_REFS["co2_ref_kg_per_h"],
                                                    DEFAULT_REFS["cost_ref_eur_per_h"])
        self.t = 0
        self.elapsed_s = 0.0
        self.n_fallbacks = 0
        # Seguimiento de bloques (semanas del test) y de semanas sin datos de contador.
        self.prev_ts = None          # fecha de la observación anterior
        self.block_hours = 0         # horas desde el inicio del bloque de fechas seguidas
        self.zero_hours = 0          # horas seguidas con el contador a 0
        self.no_data_block = False   # el contador está a 0 desde el inicio del bloque (o más de un día)
        self.valleys = deque(maxlen=VALLEY_DAYS)   # coste de las 4 horas más baratas de cada día reciente
        self.day_key = None
        self.day_weights = []

    def episode_ends_soon(self, obs: Obs) -> bool:
        """environment.py recorta la previsión al final de los datos: si llega con menos de
        24 valores, el episodio acaba dentro del horizonte. Es la única señal que usamos: no
        contamos pasos, porque no sabemos cuánto dura el test (~1.700 h según las slides, 2.016
        según el enunciado) y un contador dejaría al agente parado si el episodio fuese más largo."""
        return len(obs.price) < self.horizon

    def terminal_value(self, obs: Obs, H: int) -> float:
        """Valor de cada kWh que quede en la batería al final del horizonte."""
        if self.episode_ends_soon(obs):
            return 0.0  # la carga final no puntúa (environment.py): mejor gastarla
        marginal = self.w_co2 * obs.co2[:H] + self.w_cost * obs.price[:H]
        return float(np.quantile(marginal, self.terminal_quantile)) * self.p.eta_discharge

    def cap_discharge(self, action_kw: float, obs: Obs) -> float:
        """No descargar más de lo que el campus compró a la red en la hora anterior.

        Descargar por encima del consumo es energía tirada (el vertido no se paga ni ahorra CO2).
        Normalmente el campus consume > 500 kW y este tope no actúa. Solo actúa cuando el contador
        marca un consumo anómalo (en el train hay una avería de 14 h con lectura 0): ahí la mejor
        previsión de la hora actual es la última lectura. Sin parámetros que ajustar.
        """
        net_prev = obs.load_prev_kw - obs.pv_prev_kw
        if action_kw < 0 and math.isfinite(net_prev):
            return -min(-action_kw, max(net_prev, 0.0))
        return action_kw

    def track_block(self, obs: Obs) -> bool:
        """Actualiza el seguimiento de bloques. Devuelve True en la primera hora de un bloque nuevo."""
        ts = obs.timestamp
        new_block = False
        if ts is not None:
            prev, self.prev_ts = self.prev_ts, ts
            if prev is None:
                new_block = True
            else:
                gap_h = abs((ts - prev).total_seconds()) / 3600.0
                new_block = gap_h > BLOCK_GAP_H
        if new_block:
            self.block_hours, self.zero_hours, self.no_data_block = 0, 0, False
            return True
        self.block_hours += 1
        if obs.load_prev_kw == 0.0:
            self.zero_hours += 1
            if self.block_hours == 1 or self.zero_hours >= LONG_OUTAGE_H:
                self.no_data_block = True
        else:
            self.zero_hours, self.no_data_block = 0, False
        return False

    def note_weight(self, obs: Obs) -> None:
        """Guarda el coste de las horas más baratas de cada día (para el precio de reserva)."""
        w = self.w_co2 * obs.co2[0] + self.w_cost * obs.price[0]
        key = (obs.timestamp.year, obs.timestamp.month, obs.timestamp.day) if obs.timestamp is not None else None
        if key != self.day_key:
            if len(self.day_weights) >= 20:
                self.valleys.append(sum(sorted(self.day_weights)[:VALLEY_HOURS]) / VALLEY_HOURS)
            self.day_key, self.day_weights = key, []
        if math.isfinite(w):
            self.day_weights.append(float(w))

    def reserve_weight(self, days_left: int) -> float:
        """Precio de reserva para cargar durante una semana sin datos, con `days_left` días por delante.

        Es un problema de parada óptima: hay que comprar una carga antes de que acabe la semana y
        cada día trae su hora barata. El coste esperado de esperar es c_1 = media de los valles
        recientes (el último día se compra a lo que haya) y c_k = media de min(valle, c_(k-1)).
        Se compra hoy solo si la hora cuesta menos que lo que se espera conseguir esperando.
        """
        x = np.asarray(self.valleys, dtype=float)
        c = float(x.mean())
        for _ in range(max(int(days_left) - 1, 0)):
            c = float(np.minimum(x, c).mean())
        return c

    def act_obs(self, obs: Obs) -> float:
        """Acción interna en kW (+ carga), ya recortada a los límites."""
        try:
            new_block = self.track_block(obs)
        except Exception:      # fechas en un formato inesperado: seguimos sin seguimiento de semanas
            new_block, self.no_data_block = False, False
        if new_block:
            # Primera hora de una semana nueva: la "hora anterior" que da el entorno es de la semana
            # pasada (otro mes), así que no sirve ni como previsión ni como tope de descarga.
            obs = obs._replace(load_prev_kw=float("nan"), pv_prev_kw=float("nan"))
        try:
            self.note_weight(obs)
        except Exception:
            pass
        return self.cap_discharge(self.plan_action(obs), obs)

    def no_data_view(self, obs: Obs, H: int, load, pv, terminal: float) -> tuple:
        """Previsión y valor de la carga durante una semana sin datos de contador.

        No habrá consumo hasta que acabe el mes (o en todo el horizonte, si no sabemos la fecha);
        lo que venga después se prevé como una semana normal.
        """
        ts = obs.timestamp
        last_block = ts is not None and (ts.year, ts.month) >= FINAL_MONTH
        K = hours_to_month_end(ts) if ts is not None and not last_block else H
        load, pv = np.array(load, dtype=float), np.array(pv, dtype=float)
        load[:K] = 0.0
        pv[:K] = 0.0
        if last_block:
            terminal = 0.0   # es la última semana del test: no hay para qué guardar ni comprar
        elif K >= H and not self.episode_ends_soon(obs) and len(self.valleys) >= 7:
            # El consumo no vuelve dentro del horizonte: lo que quede en la batería vale lo que costaría
            # cargarlo más adelante. Así solo se carga en horas más baratas que eso.
            days_left = int(math.ceil((K - H) / 24.0)) + 1
            terminal = self.reserve_weight(days_left) / self.p.eta_charge
        return load, pv, terminal

    def plan_action(self, obs: Obs) -> float:
        """Primera hora del plan óptimo de 24 h (o la regla de respaldo si el LP no está disponible)."""
        self.forecaster.update(obs)
        H = max(1, min(self.horizon, len(obs.price)))
        load, pv = self.forecaster.forecast(obs, H)
        if self.elapsed_s > self.time_budget_s:
            self.n_fallbacks += 1
            return greedy_action(obs, load[0], pv[0], self.p)
        try:
            terminal = self.terminal_value(obs, H)
            if self.no_data_block:
                try:
                    load, pv, terminal = self.no_data_view(obs, H, load, pv, terminal)
                except Exception:
                    pass   # si algo falla aquí, vale el plan normal: el tope de descarga sigue protegiendo
            actions = plan(obs.soc_kwh, load, pv, obs.price[:H], obs.co2[:H],
                           self.w_co2, self.w_cost, terminal, self.p)
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
