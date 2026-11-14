"""Candidato "compra": cuándo comprar la carga durante una semana sin datos de contador.

Parte de scripts/p1_lab/plantilla.py. Cambia tres piezas de MPCPolicy y deja todo lo demás igual:

1. Precio de reserva de la semana sin datos (`reserve_now`, usado en `no_data_view`).
   v2 compara la hora actual con los valles de los 35 últimos días vistos, que en el test son de otros
   meses: si el nivel del mes ha subido, la reserva queda demasiado baja, el agente espera toda la semana
   y acaba comprando el último día a lo que haya. Aquí el nivel se aprende con la propia semana:
       log(valle del día) = nivel de la semana + ruido,   ruido ~ N(0, SIGMA_VALLEY²)
       nivel de la semana ~ N(nivel de la semana anterior, TAU_LEVEL²)
   y la reserva es la de la parada óptima con ese nivel incierto: se compra hoy solo si la hora cuesta
   menos que lo que se espera conseguir esperando (programación dinámica de 6 etapas, `wait_factor`).
   Además se usa lo que ya se ve de mañana (las 24 h siguientes se conocen exactas): el valle de mañana se
   estima comparando las horas ya visibles de mañana con las mismas horas de hoy, y nunca se compra hoy
   más caro que eso.
2. Sin plazo de más: v2 contaba como una oportunidad más el primer valle de la semana siguiente. No lo es:
   llegar vacío a la semana siguiente cuesta un ciclo entero. El último día se compra en su valle.
3. Primera hora de cada semana del test: la lectura "de la hora anterior" es de otro mes, así que no hay
   ninguna prueba de que haya consumo. En esa hora no se descarga (si la semana viene sin datos, sería
   tirar 500 kWh). Es la misma regla del tope de descarga, aplicada cuando no hay lectura válida.

Parámetros (del train, sin mirar el resultado en el banco; ver results/p1_banco/compra_notas.md):
    SIGMA_VALLEY = 0,17   desviación típica de log(valle) dentro de una semana (209 ventanas de 7 días)
    TAU_LEVEL    = 0,20   error típico del nivel de una semana si se predice con la semana vista antes
"""
import math
import sys
from collections import deque
from pathlib import Path

import numpy as np
from scipy.special import ndtr

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from battery.optimizer import plan  # noqa: E402
from battery.policy import FINAL_MONTH, VALLEY_HOURS, MPCPolicy, greedy_action, hours_to_month_end  # noqa: E402
from battery.safety import clip_action  # noqa: E402

SIGMA_VALLEY = 0.17    # dispersión (log) de los valles diarios dentro de una misma semana
TAU_LEVEL = 0.20       # incertidumbre (log) del nivel de la semana frente al de la semana vista antes
TAU_USE = 0.34         # incertidumbre (log) de lo que valdrá la carga en la semana siguiente
USE_HOURS = 13         # la carga que entra en la semana siguiente se gasta antes del primer valle (00-12 h)
WEEKEND_SHIFT = -0.20  # log(valle de sábado o domingo / valle de un día laborable); solo si USE_WEEKDAY
P_NO_DATA = 1.0 / 12.0   # en el train, 1 de los 12 meses no tiene contador: a priori, 1 semana de cada 12
PREV_DAYS = 7          # días de la semana anterior que dan la referencia de nivel
MIN_DAY_HOURS = 20     # horas conocidas de un día para dar por bueno su valle
MIN_PEEK_HOURS = 6     # horas visibles de mañana para estimar su valle
GRID_Z = np.linspace(-5.0, 5.0, 201)             # nodos de integración de la normal estándar
GRID_P = np.exp(-0.5 * GRID_Z ** 2) / np.exp(-0.5 * GRID_Z ** 2).sum()


def cheapest_mean(values, k: int = VALLEY_HOURS) -> float:
    """Media de las k horas más baratas (el "valle"). NaN si no hay ninguna hora válida."""
    a = np.asarray(values, dtype=float)
    a = np.sort(a[np.isfinite(a)])
    return float(a[:k].mean()) if a.size else float("nan")


def plan_cost(soc_kwh: float, actions, net, weights, terminal: float, p) -> float:
    """Valor del objetivo del LP para un plan dado: compras ponderadas menos el valor de la carga final."""
    a = np.asarray(actions, dtype=float)
    soc_end = soc_kwh + float(np.where(a > 0, a * p.eta_charge, a / p.eta_discharge).sum())
    return float((weights * np.maximum(net + a, 0.0)).sum() - terminal * soc_end)


def use_value_log(day_weights) -> float:
    """log de lo que vale, por kWh comprado, llegar a ese día con la batería llena: se gasta en las
    VALLEY_HOURS horas más caras antes del primer valle y se pierde un 10 % por el camino."""
    a = np.asarray(day_weights, dtype=float)[:USE_HOURS]
    a = np.sort(a[np.isfinite(a)])
    return math.log(0.9 * float(a[-VALLEY_HOURS:].mean())) if a.size else float("nan")


def level_variance(n_obs: int, sigma: float, tau: float) -> float:
    """Varianza del nivel de la semana tras ver n_obs valles (tau infinito = sin referencia previa)."""
    prec = n_obs / sigma ** 2 + (1.0 / tau ** 2 if math.isfinite(tau) and tau > 0 else 0.0)
    return 1.0 / prec if prec > 0 else float("inf")


def capped_price(z, margin: float, tau_use: float):
    """E[min(exp(z), U)] con log U ~ N(margin, tau_use²): el último día solo se compra si compensa."""
    if margin is None or not math.isfinite(margin):
        return np.exp(z)
    return (np.exp(z) * ndtr((margin - z) / tau_use)
            + math.exp(margin + 0.5 * tau_use ** 2) * ndtr((z - margin - tau_use ** 2) / tau_use))


def wait_factor(n_obs: int, shifts, sigma: float, tau: float, margin=None, tau_use: float = TAU_USE) -> float:
    """Coste esperado de seguir esperando, relativo a exp(nivel estimado), con n_obs valles ya vistos.

    `shifts`: desplazamiento (log) de cada día que queda, en orden. Parada óptima con nivel desconocido:
    a_k = E[min(valle de mañana, a_(k+1) con el nivel actualizado)]. El último día se compra en su valle,
    salvo que la carga valga menos que eso en la semana siguiente (`margin` = log(valor de uso / nivel)).
    """
    a_next = None
    for j in range(len(shifts) - 1, -1, -1):
        var = level_variance(n_obs + j, sigma, tau)
        if not math.isfinite(var):
            return float("inf")
        z = GRID_Z * math.sqrt(sigma ** 2 + var)       # valle de mañana menos el nivel estimado
        if a_next is None:
            price = capped_price(z + shifts[j], margin, tau_use)
        else:
            gain = var / (var + sigma ** 2)            # cuánto mueve ese valle el nivel estimado
            price = np.minimum(np.exp(z + shifts[j]), np.exp(gain * z) * a_next)
        a_next = float((price * GRID_P).sum())
    return a_next if a_next is not None else float("inf")


def level_estimate(logs, prior_mean, sigma: float, tau: float) -> float:
    """Media a posteriori del nivel (log) con los valles de la semana y la referencia previa."""
    n = len(logs)
    if prior_mean is None or not math.isfinite(tau) or tau <= 0:
        return float(sum(logs) / n)
    p0 = 1.0 / tau ** 2
    return float((prior_mean * p0 + sum(logs) / sigma ** 2) / (p0 + n / sigma ** 2))


class Candidate(MPCPolicy):
    SIGMA = SIGMA_VALLEY
    TAU = TAU_LEVEL
    USE_WEEKDAY = False        # el banco no conserva el día de la semana de los datos: ver las notas
    USE_PEEK = True            # usar las horas ya visibles de mañana
    FIRST_HOUR = "v2"          # "v2" (como antes) | "no_discharge" | "wait" (no hacer nada)
    NEW_RESERVE = True
    USE_VALUE = True           # contar con que la carga puede valer poco en la semana siguiente
    P_ZERO = P_NO_DATA

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.day_w = {}                              # día (ordinal) -> 24 pesos conocidos (NaN si no)
        self.cur_ord = None                          # día de la observación anterior
        self.block_vals = []                         # valles de los días completos de esta semana
        self.block_use = []                          # log del valor de uso de esos mismos días
        self.prev_vals = deque(maxlen=PREV_DAYS)     # valles de la semana vista antes
        self.first_hour = False

    # ------------------------------------------------------------------ memoria de pesos por día
    def note_hours(self, obs, new_block: bool) -> None:
        """Guarda los pesos de las horas conocidas (hasta fin de mes) y cierra los días completos."""
        ts = obs.timestamp
        if ts is None:
            return
        today = ts.toordinal()
        if self.cur_ord is not None and today != self.cur_ord:
            done = self.day_w.get(self.cur_ord)
            if done is not None and int(np.isfinite(done).sum()) >= MIN_DAY_HOURS:
                self.block_vals.append(cheapest_mean(done))
                self.block_use.append(use_value_log(done))
        if new_block:
            self.prev_vals.extend(self.block_vals)
            self.block_vals, self.block_use, self.day_w = [], [], {}
        self.cur_ord = today
        w = self.w_co2 * obs.co2 + self.w_cost * obs.price
        n = min(len(w), hours_to_month_end(ts))      # lo que pasa de fin de mes ya es otra semana del test
        for k in range(n):
            day, hour = today + (ts.hour + k) // 24, (ts.hour + k) % 24
            row = self.day_w.get(day)
            if row is None:
                row = self.day_w[day] = np.full(24, np.nan)
            row[hour] = w[k]
        for day in [d for d in self.day_w if d < today - 1]:
            del self.day_w[day]

    def day_shift(self, ts, days_ahead: int) -> float:
        if not self.USE_WEEKDAY:
            return 0.0
        return WEEKEND_SHIFT if (ts.dayofweek + days_ahead) % 7 >= 5 else 0.0

    # ----------------------------------------------------------------------- precio de reserva
    def reserve_now(self, obs) -> float:
        """Peso por debajo del cual compensa comprar ahora en una semana sin datos (inf = no se sabe)."""
        ts = obs.timestamp
        days_after = int(ts.days_in_month - ts.day)        # días de la semana que quedan después de hoy
        today = self.day_w.get(ts.toordinal())
        if days_after < 1 or today is None or int(np.isfinite(today).sum()) < MIN_DAY_HOURS:
            return float("inf")
        v_today = cheapest_mean(today)
        logs = [math.log(v) for v in self.block_vals] + [math.log(v_today) - self.day_shift(ts, 0)]
        # Los valles de días anteriores de la semana se guardaron sin corregir: se corrigen aquí.
        if self.USE_WEEKDAY:
            nb = len(self.block_vals)
            logs = [math.log(v) - self.day_shift(ts, i - nb) for i, v in enumerate(self.block_vals)] + logs[-1:]
        prior = None
        tau = float("inf")
        if len(self.prev_vals) >= 4:
            prior, tau = float(np.mean(np.log(np.asarray(self.prev_vals, dtype=float)))), self.TAU
        v_next = None
        if self.USE_PEEK and ts.hour >= MIN_PEEK_HOURS:
            tomorrow = self.day_w.get(ts.toordinal() + 1)
            if tomorrow is not None:
                seen = np.isfinite(tomorrow[:ts.hour]) & np.isfinite(today[:ts.hour])
                if int(seen.sum()) >= MIN_PEEK_HOURS:
                    # Mismo trozo del día, hoy y mañana: su cociente estima el cociente de los valles.
                    v_next = v_today * cheapest_mean(tomorrow[:ts.hour][seen]) / cheapest_mean(today[:ts.hour][seen])
        use_logs = [u for u in self.block_use + [use_value_log(today)] if math.isfinite(u)]
        use_level = float(np.mean(use_logs)) if (self.USE_VALUE and use_logs) else None

        def expected(logs, shifts):
            level = level_estimate(logs, prior, self.SIGMA, tau)
            margin = None if use_level is None else use_level - level
            return level, margin, math.exp(level) * wait_factor(len(logs), shifts, self.SIGMA, tau, margin)

        if v_next is None or not math.isfinite(v_next) or v_next <= 0:
            return expected(logs, [self.day_shift(ts, i) for i in range(1, days_after + 1)])[2]
        logs = logs + [math.log(v_next) - self.day_shift(ts, 1)]
        if days_after == 1:
            # Mañana es el último día: allí se compra en su valle, si para entonces compensa.
            level = level_estimate(logs, prior, self.SIGMA, tau)
            margin = None if use_level is None else use_level - level
            return math.exp(level) * float(capped_price(math.log(v_next) - level, margin, TAU_USE))
        return min(v_next, expected(logs, [self.day_shift(ts, i) for i in range(2, days_after + 1)])[2])

    def no_data_view(self, obs, H, load, pv, terminal):
        if not self.NEW_RESERVE:
            return super().no_data_view(obs, H, load, pv, terminal)
        ts = obs.timestamp
        last_block = ts is not None and (ts.year, ts.month) >= FINAL_MONTH
        K = hours_to_month_end(ts) if ts is not None and not last_block else H
        load, pv = np.array(load, dtype=float), np.array(pv, dtype=float)
        load[:K] = 0.0
        pv[:K] = 0.0
        if last_block:
            terminal = 0.0
        elif K >= H and not self.episode_ends_soon(obs):
            reserve = float("inf")
            try:
                reserve = self.reserve_now(obs)
            except Exception:
                pass
            if math.isfinite(reserve) and reserve > 0:
                terminal = reserve / self.p.eta_charge
            elif K > H and len(self.valleys) >= 7:
                # Sin datos del día para la regla nueva: la reserva de v2.
                terminal = self.reserve_weight(int(math.ceil((K - H) / 24.0)) + 1) / self.p.eta_charge
        return load, pv, terminal

    # ------------------------------------------------------------ primera hora de una semana nueva
    def first_hour_bet(self, obs, H: int, load, pv, terminal: float, actions, a0: float) -> float:
        """¿Compensa actuar ya en la primera hora de una semana, sin saber si viene con datos?

        Si la semana es normal, actuar ya vale `gain` (lo que mejora el plan frente a esperar una hora).
        Si viene sin datos, descargar es tirar la energía y cargar es comprar antes de tiempo (`loss`).
        Se actúa solo si la ganancia esperada supera a la pérdida esperada, con P_NO_DATA de prior.
        """
        if H < 2 or abs(a0) < 1e-6:
            return a0
        w = self.w_co2 * obs.co2[:H] + self.w_cost * obs.price[:H]
        net = np.asarray(load, dtype=float) - np.asarray(pv, dtype=float)
        later = plan(obs.soc_kwh, load[1:], pv[1:], obs.price[1:H], obs.co2[1:H],
                     self.w_co2, self.w_cost, terminal, self.p)
        wait = w[0] * max(float(net[0]), 0.0) + plan_cost(obs.soc_kwh, later, net[1:], w[1:], terminal, self.p)
        gain = wait - plan_cost(obs.soc_kwh, actions, net, w, terminal, self.p)
        valley = cheapest_mean(w)                # a cuánto se compra en una semana sin datos
        if a0 > 0:
            loss = a0 * max(float(w[0]) - valley, 0.0)
        else:
            loss = -a0 * valley / (self.p.eta_charge * self.p.eta_discharge)
        return a0 if (1.0 - self.P_ZERO) * gain >= self.P_ZERO * loss else 0.0

    def plan_action(self, obs) -> float:
        """Como MPCPolicy.plan_action, más la apuesta de la primera hora de cada semana."""
        if not (self.first_hour and self.FIRST_HOUR == "ev"):
            return super().plan_action(obs)
        self.forecaster.update(obs)
        H = max(1, min(self.horizon, len(obs.price)))
        load, pv = self.forecaster.forecast(obs, H)
        if self.elapsed_s > self.time_budget_s:
            self.n_fallbacks += 1
            return greedy_action(obs, load[0], pv[0], self.p)
        try:
            terminal = self.terminal_value(obs, H)
            actions = plan(obs.soc_kwh, load, pv, obs.price[:H], obs.co2[:H],
                           self.w_co2, self.w_cost, terminal, self.p)
            a0 = clip_action(actions[0], obs.soc_kwh, self.p)
            try:
                return self.first_hour_bet(obs, H, load, pv, terminal, actions, a0)
            except Exception:
                return a0
        except Exception:
            self.n_fallbacks += 1
            return greedy_action(obs, load[0], pv[0], self.p)

    # ------------------------------------------------------------------------------ paso completo
    def act_obs(self, obs) -> float:
        try:
            new_block = self.track_block(obs)
        except Exception:
            new_block, self.no_data_block = False, False
        raw = obs
        if new_block:
            obs = obs._replace(load_prev_kw=float("nan"), pv_prev_kw=float("nan"))
        try:
            self.note_weight(obs)
        except Exception:
            pass
        try:
            self.note_hours(obs, new_block)
        except Exception:
            pass
        self.first_hour = bool(new_block and self.t > 0)
        action = self.cap_discharge(self.plan_action(obs), obs)
        if new_block and self.t > 0:
            # Primera hora de una semana nueva del test: no hay lectura válida del contador.
            if self.FIRST_HOUR == "wait":
                return 0.0
            if self.FIRST_HOUR == "no_discharge":
                return max(action, 0.0)
        elif new_block and self.FIRST_HOUR != "v2":
            # Primera hora del episodio: el entorno da el consumo de esa misma hora, así que el tope vale.
            action = self.cap_discharge(action, raw)
        return action


class _Agent:
    def __init__(self, cls=Candidate):
        self.policy = cls()

    def act(self, obs):
        return self.policy.act(obs)


def make_agent():
    return _Agent()


# ------------------------------------------------------------- variantes para medir cada pieza
def _variant(**attrs):
    cls = type("Variant", (Candidate,), attrs)
    return lambda: _Agent(cls)


solo_reserva = _variant()                                                 # el precio de reserva nuevo (lo mismo que make_agent)
sin_uso = _variant(USE_VALUE=False)                                       # ... sin el valor de uso de la semana siguiente
sin_peek = _variant(USE_PEEK=False)                                       # ... sin mirar las horas de mañana
con_dia_semana = _variant(USE_WEEKDAY=True)                               # ... con el efecto de fin de semana
solo_hora1 = _variant(NEW_RESERVE=False, FIRST_HOUR="no_discharge")       # v2 + no descargar en la primera hora
solo_hora1_wait = _variant(NEW_RESERVE=False, FIRST_HOUR="wait")          # v2 + no hacer nada en la primera hora
hora1 = _variant(FIRST_HOUR="no_discharge")                               # reserva nueva + no descargar en la primera hora
solo_apuesta = _variant(NEW_RESERVE=False, FIRST_HOUR="ev")               # v2 + apuesta de la primera hora (prior 1/12)
solo_apuesta_p6 = _variant(NEW_RESERVE=False, FIRST_HOUR="ev", P_ZERO=1.0 / 6.0)
solo_apuesta_p24 = _variant(NEW_RESERVE=False, FIRST_HOUR="ev", P_ZERO=1.0 / 24.0)
