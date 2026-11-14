"""Candidato "compra": cuándo comprar la carga durante una semana sin datos de contador.

Parte de scripts/p1_lab/plantilla.py. Solo cambia el precio de reserva de la semana sin datos (la pieza
`no_data_view` de MPCPolicy). Todo lo demás es el agente actual: en una semana con consumo no cambia nada.

AVISO. Con el calendario real del test (la semana de noviembre va de lunes 24 a domingo 30) el agente
actual ya compra donde compra el óptimo, así que este candidato NO mejora ese caso: lo iguala. Lo que
aporta es que deja de depender de la suerte en las demás semanas. Ver results/p1_banco/compra_notas.md y
scripts/p1_lab/compra_banco_alineado.py (el banco estándar no conserva el día de la semana de los datos).

Qué hace v2 y por qué se cambia. v2 compara la hora actual con los valles de los 35 últimos días vistos,
que en el test son de otros meses. Si el mes es más caro que los anteriores, la reserva queda baja, el
agente no compra en toda la semana y compra el último día a lo que haya. Eso sale bien si el último día
es domingo (noviembre) y mal si es un miércoles.

Aquí la reserva sale de un modelo de los valles diarios, calibrado en el train:
    log(valle del día) = nivel de la semana + [fin de semana] + ruido,   ruido ~ N(0, SIGMA_VALLEY²)
    nivel de la semana ~ N(nivel de la semana vista antes, TAU_LEVEL²)   (se aprende con cada día)
y de la parada óptima con ese nivel incierto (`wait_factor`, 6 etapas como mucho): se compra hoy solo si
la hora cuesta menos que lo que se espera conseguir esperando. Tres detalles:
  - el sábado y el domingo el valle es un 18 % más barato (WEEKEND_SHIFT): un laborable tiene que ser
    muy bueno para no esperar al fin de semana;
  - las 24 h siguientes se conocen exactas: cuando ya se ve la hora de mañana en la que hoy está el
    mínimo, el valle de mañana se estima comparando la hora más barata visible de mañana con la de hoy;
  - lo que se compra vale lo que ahorre en la semana siguiente, y eso no se ve hasta el último día. Antes
    del último día se descuenta ese riesgo (`capped_price`); el último día decide el LP normal.

Parámetros (medidos en el train, sin mirar el resultado en el banco):
    SIGMA_VALLEY  = 0,17   desviación típica de log(valle) dentro de una semana (209 ventanas de 7 días)
    TAU_LEVEL     = 0,20   error típico del nivel de una semana predicho con las semanas vistas antes
    WEEKEND_SHIFT = -0,20  log(valle de sábado o domingo / valle de laborable), con efectos fijos de mes
    TAU_USE       = 0,34   desviación típica de log(valor de uso de un día del mes siguiente / de esta semana)
"""
import math
import sys
from collections import deque
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from battery.policy import FINAL_MONTH, VALLEY_HOURS, MPCPolicy, hours_to_month_end  # noqa: E402

SIGMA_VALLEY = 0.17    # dispersión (log) de los valles diarios dentro de una misma semana
TAU_LEVEL = 0.20       # incertidumbre (log) del nivel de la semana frente al de la semana vista antes
WEEKEND_SHIFT = -0.20  # log(valle de sábado o domingo / valle de un día laborable)
TAU_USE = 0.34         # incertidumbre (log) de lo que valdrá la carga en la semana siguiente
USE_HOURS = 13         # la carga que entra en la semana siguiente se gasta antes del primer valle (00-12 h)
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


def use_value_log(day_weights) -> float:
    """log de lo que vale, por kWh comprado, llegar a ese día con la batería llena: se gasta en las
    VALLEY_HOURS horas más caras antes del primer valle y se pierde un 10 % por el camino."""
    a = np.asarray(day_weights, dtype=float)[:USE_HOURS]
    a = np.sort(a[np.isfinite(a)])
    return math.log(0.9 * float(a[-VALLEY_HOURS:].mean())) if a.size else float("nan")


def is_weekend(day_ordinal: int) -> bool:
    """Sábado o domingo (el día 1 del calendario gregoriano proléptico es lunes)."""
    return (day_ordinal - 1) % 7 >= 5


def normal_cdf(x):
    """Función de distribución de la normal estándar (Abramowitz y Stegun 26.2.17, error < 1e-7)."""
    x = np.asarray(x, dtype=float)
    t = 1.0 / (1.0 + 0.2316419 * np.abs(x))
    poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
    tail = np.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi) * poly
    return np.where(x >= 0, 1.0 - tail, tail)


def level_variance(n_obs: int, sigma: float, tau: float) -> float:
    """Varianza del nivel de la semana tras ver n_obs valles (tau infinito = sin referencia previa)."""
    prec = n_obs / sigma ** 2 + (1.0 / tau ** 2 if math.isfinite(tau) and tau > 0 else 0.0)
    return 1.0 / prec if prec > 0 else float("inf")


def level_estimate(logs, prior_mean, sigma: float, tau: float) -> float:
    """Media a posteriori del nivel (log) con los valles de la semana y la referencia previa."""
    n = len(logs)
    if prior_mean is None or not math.isfinite(tau) or tau <= 0:
        return float(sum(logs) / n)
    p0 = 1.0 / tau ** 2
    return float((prior_mean * p0 + sum(logs) / sigma ** 2) / (p0 + n / sigma ** 2))


def capped_price(z, margin, tau_use: float):
    """E[min(exp(z), U)] con log U ~ N(margin, tau_use²): el último día solo se compra si compensa.

    `z` y `margin` son logaritmos relativos al nivel estimado; U es lo que valdrá la carga en la semana
    siguiente. Sin margen conocido devuelve exp(z).
    """
    z = np.asarray(z, dtype=float)
    if margin is None or not math.isfinite(margin):
        return np.exp(z)
    return (np.exp(z) * normal_cdf((margin - z) / tau_use)
            + math.exp(margin + 0.5 * tau_use ** 2) * normal_cdf((z - margin - tau_use ** 2) / tau_use))


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


class Candidate(MPCPolicy):
    SIGMA = SIGMA_VALLEY
    TAU = TAU_LEVEL
    USE_WEEKDAY = True         # el fin de semana el valle es más barato
    USE_PEEK = True            # usar las horas ya visibles de mañana
    PEEK_AFTER_VALLEY = True   # ... solo cuando ya se ve la hora de mañana en la que hoy está el mínimo
    USE_VALUE = True           # contar con que la carga puede valer poco en la semana siguiente

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.day_w = {}                              # día (ordinal) -> 24 pesos conocidos (NaN si no)
        self.cur_ord = None                          # día de la observación anterior
        self.block_days = []                         # (día, valle, log del valor de uso) de esta semana
        self.prev_days = deque(maxlen=PREV_DAYS)     # (día, valle) de la semana vista antes

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
                self.block_days.append((self.cur_ord, cheapest_mean(done), use_value_log(done)))
        if new_block:
            self.prev_days.extend((d, v) for d, v, _ in self.block_days)
            self.block_days, self.day_w = [], {}
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

    def day_shift(self, day_ordinal: int) -> float:
        return WEEKEND_SHIFT if (self.USE_WEEKDAY and is_weekend(day_ordinal)) else 0.0

    # ----------------------------------------------------------------------- precio de reserva
    def reserve_now(self, obs) -> float:
        """Peso por debajo del cual compensa comprar ahora en una semana sin datos (inf = no se sabe)."""
        ts = obs.timestamp
        day = ts.toordinal()
        days_after = int(ts.days_in_month - ts.day)        # días de la semana que quedan después de hoy
        today = self.day_w.get(day)
        if days_after < 1 or today is None or int(np.isfinite(today).sum()) < MIN_DAY_HOURS:
            return float("inf")
        v_today = cheapest_mean(today)
        # Valles de la semana, sin el efecto del fin de semana: el nivel "de día laborable".
        logs = [math.log(v) - self.day_shift(d) for d, v, _ in self.block_days]
        logs.append(math.log(v_today) - self.day_shift(day))
        prior, tau = None, float("inf")
        if len(self.prev_days) >= 4:
            prior = float(np.mean([math.log(v) - self.day_shift(d) for d, v in self.prev_days]))
            tau = self.TAU
        use_logs = [u for u in [x[2] for x in self.block_days] + [use_value_log(today)] if math.isfinite(u)]
        use_level = float(np.mean(use_logs)) if (self.USE_VALUE and use_logs) else None

        def later(logs_seen, first_day):
            """Lo que se espera pagar esperando a los días first_day..fin de la semana."""
            level = level_estimate(logs_seen, prior, self.SIGMA, tau)
            margin = None if use_level is None else use_level - level
            shifts = [self.day_shift(day + i) for i in range(first_day, days_after + 1)]
            return math.exp(level) * wait_factor(len(logs_seen), shifts, self.SIGMA, tau, margin)

        v_next = None
        hour = int(ts.hour)
        if self.USE_PEEK and hour >= MIN_PEEK_HOURS and (not self.PEEK_AFTER_VALLEY or hour > int(np.nanargmin(today))):
            tomorrow = self.day_w.get(day + 1)
            if tomorrow is not None:
                seen = np.isfinite(tomorrow[:hour]) & np.isfinite(today[:hour])
                if int(seen.sum()) >= MIN_PEEK_HOURS:
                    # Mismo trozo del día, hoy y mañana: su cociente estima el cociente de los valles. Si
                    # ya se ha pasado el mínimo de hoy, basta comparar la hora más barata de cada día.
                    k = 1 if self.PEEK_AFTER_VALLEY else VALLEY_HOURS
                    v_next = (v_today * cheapest_mean(tomorrow[:hour][seen], k)
                              / cheapest_mean(today[:hour][seen], k))
        if v_next is None or not math.isfinite(v_next) or v_next <= 0:
            return later(logs, 1)
        logs = logs + [math.log(v_next) - self.day_shift(day + 1)]
        if days_after == 1:
            # Mañana es el último día: allí se compra en su valle, si para entonces compensa.
            level = level_estimate(logs, prior, self.SIGMA, tau)
            margin = None if use_level is None else use_level - level
            return math.exp(level) * float(capped_price(math.log(v_next) - level, margin, TAU_USE))
        return min(v_next, later(logs, 2))

    def no_data_view(self, obs, H, load, pv, terminal):
        """Como en MPCPolicy, con el precio de reserva nuevo (y el de v2 si no se puede calcular)."""
        ts = obs.timestamp
        last_block = ts is not None and (ts.year, ts.month) >= FINAL_MONTH
        K = hours_to_month_end(ts) if ts is not None and not last_block else H
        load, pv = np.array(load, dtype=float), np.array(pv, dtype=float)
        load[:K] = 0.0
        pv[:K] = 0.0
        if last_block:
            terminal = 0.0   # es la última semana del test: no hay para qué guardar ni comprar
        elif K >= H and not self.episode_ends_soon(obs):
            reserve = float("inf")
            try:
                reserve = self.reserve_now(obs)
            except Exception:
                pass
            if math.isfinite(reserve) and reserve > 0:
                terminal = reserve / self.p.eta_charge
            elif K > H and len(self.valleys) >= 7:
                terminal = self.reserve_weight(int(math.ceil((K - H) / 24.0)) + 1) / self.p.eta_charge
        return load, pv, terminal

    # ------------------------------------------------------------------------------ paso completo
    def act_obs(self, obs) -> float:
        """Como MPCPolicy.act_obs, más la memoria de pesos por día (`note_hours`)."""
        try:
            new_block = self.track_block(obs)
        except Exception:
            new_block, self.no_data_block = False, False
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
        return self.cap_discharge(self.plan_action(obs), obs)


class _Agent:
    def __init__(self, cls=Candidate):
        self.policy = cls()

    def act(self, obs):
        return self.policy.act(obs)


def make_agent():
    return _Agent()


# ------------------------------------------------------------- variantes para medir cada pieza
def variant(base=Candidate, **attrs):
    cls = type("Variant", (base,), attrs)
    return lambda: _Agent(cls)


sin_dia_semana = variant(USE_WEEKDAY=False, PEEK_AFTER_VALLEY=False)   # lo que premia el banco estándar (y pierde con el calendario real)
peek_siempre = variant(PEEK_AFTER_VALLEY=False)                        # estimar el valle de mañana desde las 06 h
sin_peek = variant(USE_PEEK=False)                                     # sin mirar las horas de mañana
sin_valor_uso = variant(USE_VALUE=False)                               # sin contar con lo que valdrá la carga
