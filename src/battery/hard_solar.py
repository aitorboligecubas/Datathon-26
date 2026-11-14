"""Previsión del consumo y de la solar para el HARD MODE (solar x12: hay horas con excedente).

Owner: P1 (optimizador), con P2 (datos). Se empaqueta en el agent.py del modo difícil.

CONTRATO (no cambiar sin avisar):
    f = NetLoadForecaster(prior, base)          # prior: dict de models/hard_solar.json, o None
                                                # base: el Forecaster de P2 (perfil de consumo por hora de la semana)
    f.update(obs, weather)                      # una vez por hora, antes de forecast
    load_kw, pv_kw = f.forecast(obs, times)     # np.ndarray de la longitud de `times`, >= 0, [0] = hora actual
    a = f.adjust_action(action_kw, obs, p)      # último retoque de la acción de esta hora (p: BatteryParams)
        obs.load_prev_kw / obs.pv_prev_kw: consumo y solar (ya x12) de la hora ANTERIOR
        weather: {"irradiancia_wm2", "temp_ambient_c", "temp_panel_c", "vent_ms"} de la hora anterior
Tiene que tardar menos de ~2 ms por hora. Solo numpy, pandas y math.

Cómo prevé:
- Solar: "cielo despejado" del mes a esa hora (percentil 90 del train) por la claridad del día, que es
  solar medida / cielo despejado en la hora anterior. La claridad se va acercando a la media del mes
  cuanto más lejos se mira.
- Consumo: perfil por hora de la semana (el de P2) por el cociente consumo medido / perfil de la hora
  anterior, que también se apaga con el horizonte.
Y un retoque final de la acción (`adjust_action`), porque la previsión de la hora actual se equivoca
(unos 140 kW de día): descargar de más es tirar energía y cargar de menos es perder excedente gratis, así
que se descarga un poco por debajo de lo previsto y se carga un poco por encima. El plan de las horas
siguientes ya cuenta con ese margen (Z_PLAN), para repartir la energía sabiendo lo que de verdad se hará.
"""
import math
from typing import Optional

import numpy as np
import pandas as pd

from .obs import Obs

PV_FACTOR = 12.0            # la solar del modo difícil es 12 veces la del train
ONE_HOUR_BACK = pd.Timedelta(hours=1)
SOLAR_FILE = "hard_solar.json"
CLEAR_MIN_KW = 30.0         # por debajo de esto el "cielo despejado" no sirve para medir la claridad
PV_DAMP = 0.85              # cuánto se mantiene la claridad de una hora a la siguiente
LOAD_DAMP = 0.90            # ídem para el cociente consumo / perfil
Z_DISCHARGE = 1.0           # margen al descargar, en desviaciones típicas del error de la hora actual
Z_CHARGE = 1.0              # margen al cargar cuando puede haber excedente
Z_PLAN = 1.0                # el plan de las horas siguientes cuenta ya con ese mismo margen
DEFAULT_SD_KW = 150.0       # error típico del consumo neto de la hora actual si no hay tabla
# Días en que el campus funciona como un domingo: festivos nacionales, de Cataluña y de Barcelona, y el
# cierre de Navidad (del 24 de diciembre al 6 de enero). En el train, del 1 al 6 de enero el consumo medio
# es de 730-900 kW; el 7 de enero, 1.290.
CAMPUS_HOLIDAYS = ((2025, 9, 11), (2025, 9, 24), (2025, 10, 12), (2025, 11, 1), (2025, 12, 6), (2025, 12, 8),
                   (2025, 12, 24), (2025, 12, 25), (2025, 12, 26), (2025, 12, 27), (2025, 12, 28), (2025, 12, 29),
                   (2025, 12, 30), (2025, 12, 31), (2026, 1, 1), (2026, 1, 2), (2026, 1, 3), (2026, 1, 4),
                   (2026, 1, 5), (2026, 1, 6), (2026, 4, 3), (2026, 4, 6), (2026, 5, 1), (2026, 5, 25),
                   (2026, 6, 24), (2026, 8, 15))


def campus_hour_of_week(ts) -> int:
    """Hora de la semana (lunes 00 h = 0) con la que se busca el perfil de consumo: los festivos, como domingo."""
    if (ts.year, ts.month, ts.day) in CAMPUS_HOLIDAYS:
        return 6 * 24 + ts.hour
    return ts.dayofweek * 24 + ts.hour


class NetLoadForecaster:
    def __init__(self, prior: Optional[dict], base, z_discharge: float = Z_DISCHARGE, z_charge: float = Z_CHARGE):
        self.base = base
        self.z_discharge, self.z_charge = z_discharge, z_charge
        prior = prior or {}
        try:
            self.clear = np.asarray(prior["pv_clear"], dtype=float)       # [mes 0-11][hora 0-23], kW ya x12
            self.mean = np.asarray(prior["pv_mean"], dtype=float)
            self.sd = np.asarray(prior["net_sd"], dtype=float)            # [hora 0-23]
            self.ok = self.clear.shape == (12, 24) and self.mean.shape == (12, 24) and self.sd.shape == (24,)
        except Exception:
            self.ok = False
        try:    # sin tabla propia: la solar que verá el previsor de P2 es 12 veces la del train
            self.base.pv_prior = self.base.pv_prior * PV_FACTOR
        except Exception:
            pass
        self.weather = {}
        self.clearness = float("nan")     # solar medida / cielo despejado, de la última hora con sol
        self.load_ratio = 1.0             # consumo medido / perfil, de la hora anterior
        self.meter_down = False
        self.net_now = float("nan")       # previsión del consumo neto de la hora actual (para adjust_action)
        self.hour_now = 0
        self.pv_alive = False             # la última lectura de solar fue válida y mayor que cero
        self.pv_now = 0.0                 # solar prevista para la hora actual

    def new_block(self) -> None:
        """Empieza otra semana del test (hace un mes de la anterior): lo aprendido de las últimas horas no vale."""
        self.clearness = float("nan")
        self.load_ratio = 1.0
        self.meter_down = False

    def update(self, obs: Obs, weather: Optional[dict] = None) -> None:
        self.weather = weather or {}
        prev_how = (obs.hour_of_week - 1) % 168
        if obs.timestamp is not None:
            try:
                prev_how = campus_hour_of_week(obs.timestamp - ONE_HOUR_BACK)
            except Exception:
                pass
        expected = self.load_profile(prev_how)          # antes de que el perfil aprenda de esta lectura
        self.base.update(obs)
        load, pv, ts = obs.load_prev_kw, obs.pv_prev_kw, obs.timestamp
        self.meter_down = load == 0.0
        self.pv_alive = math.isfinite(pv) and pv > 1.0
        if math.isfinite(load) and load > 0 and expected > 0:
            self.load_ratio = min(max(load / expected, 0.3), 3.0)
        if self.ok and ts is not None and math.isfinite(pv):
            prev_hour = (obs.hour - 1) % 24
            month = ts.month if obs.hour > 0 else (ts.month - 1 if ts.day == 1 else ts.month)
            clear_prev = float(self.clear[(month - 1) % 12][prev_hour])
            if clear_prev >= CLEAR_MIN_KW:
                self.clearness = min(max(pv / clear_prev, 0.0), 1.5)

    def load_profile(self, how: int) -> float:
        try:
            v = float(self.base.load_how[how % 168])
            return v if math.isfinite(v) else float("nan")
        except Exception:
            return float("nan")

    def forecast(self, obs: Obs, times: list) -> tuple:
        H = max(1, len(times))
        if not self.ok or times[0] is None:
            load, pv = self.base.forecast(obs, H)
            self.net_now, self.hour_now = float(load[0] - pv[0]), obs.hour
            return np.maximum(load, 0.0), np.maximum(pv, 0.0)
        base_load, _ = self.base.forecast(obs, H)
        load, pv = np.empty(H), np.empty(H)
        for k, t in enumerate(times):
            m, h = t.month - 1, t.hour
            clear, mean = float(self.clear[m][h]), float(self.mean[m][h])
            typical = mean / clear if clear > 0 else 0.0
            c = self.clearness if math.isfinite(self.clearness) else typical
            c = typical + (c - typical) * PV_DAMP ** (k + 1)
            pv[k] = clear * c
            prof = self.load_profile(campus_hour_of_week(t))
            if math.isfinite(prof) and prof > 0:
                load[k] = prof * (1.0 + (self.load_ratio - 1.0) * LOAD_DAMP ** (k + 1))
            else:
                load[k] = base_load[k]
        if self.meter_down:          # contador caído (lectura 0 exacta): si sigue, descargar es tirar energía
            load[0] = 0.0
            if not self.pv_alive:    # ...y si la solar también marca 0, tampoco se cuenta con ella esta hora
                pv[0] = 0.0
        load, pv = np.maximum(load, 0.0), np.maximum(pv, 0.0)
        self.net_now, self.hour_now, self.pv_now = float(load[0] - pv[0]), times[0].hour, float(pv[0])
        # Al llegar cada hora se descargará algo menos y se cargará algo más de lo previsto (adjust_action).
        # Para que el plan reparta la energía contando con eso, las horas siguientes se planifican con un
        # consumo neto una desviación típica más bajo (se suma a la solar; solo mueve decisiones, no el score).
        for k in range(1, H):
            pv[k] += Z_PLAN * float(self.sd[times[k].hour])
        return load, pv

    def adjust_action(self, action_kw: float, obs: Obs, p) -> float:
        """Margen de seguridad con el consumo neto de ESTA hora, que solo se conoce aproximadamente."""
        if self.meter_down and not (self.pv_alive and self.pv_now > 1.0):
            return max(action_kw, 0.0)      # contador caído y sin solar: no se descarga ni hay excedente que guardar
        net = self.net_now
        if not math.isfinite(net):
            return action_kw
        sd = float(self.sd[self.hour_now % 24]) if self.ok else DEFAULT_SD_KW
        if action_kw < 0:
            # Descargar por encima del consumo neto real es verter: se descarga algo menos de lo previsto.
            return -min(-action_kw, max(net - self.z_discharge * sd, 0.0))
        surplus = -(net - self.z_charge * sd)       # excedente solar que puede llegar a haber esta hora
        if surplus > action_kw and net < sd:
            # Si puede sobrar solar, se carga al menos eso: lo que no se guarde se regala a la red.
            return min(surplus, p.max_charge_kw)
        return action_kw


# ------------------------------------------------------------------------------------------------------------
# Previsor con tablas ampliadas (versión 7). Si faltan sus tablas, el agente usa el NetLoadForecaster de arriba.
KAPPA_MAX = 1.5              # tope de la claridad
RATIO_MIN, RATIO_MAX = 0.3, 3.0     # topes del cociente consumo / perfil
FROZEN_HOURS = frozenset((23, 0, 1, 2, 3, 4, 5))   # horas con el contador congelado (100 % de las noches del train)
PV_LEADS = 16                # antelaciones con coeficiente propio: ningún día tiene más de 16 horas de sol
KAPPA_BINS = (0.25, 0.5, 0.75, 1.0)     # tramos de claridad prevista para el margen de la solar (iguales, sin afinar)
Q_LOW, Q_HIGH = 0.16, 0.84   # cuantiles del margen: equivalen a 1 desviación típica (el margen del agente actual)
MONTH_DAYS = 30.4            # días medios de un mes, para interpolar el cielo despejado
MIN_DAY_HOURS = 3            # horas de sol vistas hoy para que la media de hoy sirva de pista para mañana
VALUE_RANK = 6               # la séptima peor hora de las últimas 24 (una descarga cubre unas 6 h de consumo medio)
MIN_FIT_ROWS = 200           # filas mínimas para ajustar un coeficiente de la solar (si no, vale el día típico)
HOUR_NS = 3600 * 10 ** 9
HOLIDAY_SET = frozenset(CAMPUS_HOLIDAYS)
LAST_SUNDAY = {}             # (año, mes) -> día del último domingo (cambio de hora)


def last_sunday(year: int, month: int) -> int:
    key = (year, month)
    if key not in LAST_SUNDAY:
        LAST_SUNDAY[key] = 31 - (pd.Timestamp(year=year, month=month, day=31).dayofweek + 1) % 7
    return LAST_SUNDAY[key]


def summer_time(ts) -> bool:
    """True si la fecha (hora local) está en horario de verano: del último domingo de marzo al de octubre."""
    mo = ts.month
    if 3 < mo < 10:
        return True
    if mo < 3 or mo > 10:
        return False
    ls = last_sunday(ts.year, mo)
    if mo == 3:
        return ts.day > ls or (ts.day == ls and ts.hour >= 2)
    return ts.day < ls or (ts.day == ls and ts.hour < 3)


def campus_how(ts) -> int:
    """Hora de la semana (lunes 00 h = 0) del perfil de consumo: los festivos cuentan como domingo."""
    if (ts.year, ts.month, ts.day) in HOLIDAY_SET:
        return 144 + ts.hour
    return ts.dayofweek * 24 + ts.hour


def neighbour_month(month: int, day: float, centers) -> tuple:
    """Mes vecino (índice 0-11) y peso con el que entra su tabla, según lo lejos que cae el día del centro
    de los datos con los que se ajustó la tabla del mes."""
    c = centers[month - 1]
    if day >= c:
        other = month % 12
        w = (day - c) / (MONTH_DAYS - c + centers[other])
    else:
        other = (month - 2) % 12
        w = (c - day) / (c + MONTH_DAYS - centers[other])
    return other, min(max(w, 0.0), 1.0)


# Margen del previsor ampliado, en "desviaciones típicas" (1 = cuantiles 16 % y 84 % del error medido). Con 1,4
# gana a 1,0 en tres ventanas disjuntas del train (días 1-7: +0,002; días 8-14: +0,031; validación: +0,051) y
# el vertido al descargar baja a la mitad. Descargar de más es tirar la energía entera; descargar de menos solo
# la mueve a una hora algo peor, y el test (días 25-31) se parece menos al train que el train a sí mismo.
# v10 (rama mejora-score-hard-z10): se vuelve a 1,0. La v7 (1,0) sacó +0,04 sobre la v8 (1,4) en el ranking público,
# con los datos reales del test (sep-feb), y en el banco los meses de verano (la mitad privada) casi no notan el
# cambio (-0,004 de media en 4 ventanas). En el banco completo 1,4 gana por unas centésimas.
Z_SOLAR = 1.0
# Margen con el que el PLAN de las horas siguientes (no la acción de esta hora) cuenta con la solar. Se deja igual
# que el de la acción (1,4). Rama mejora-score-hard: 2,0 ganaba en validación (+0,031) pero en 9 ventanas solo
# +0,001 de media sobre la semilla y -0,027 en el episodio con el calendario del test: no se cambia.
Z_PLAN_SOLAR = Z_SOLAR


def scen_probs(alphas) -> tuple:
    """Para K cuantiles del consumo neto de niveles `alphas`: probabilidad de que el consumo neto supere cada tramo
    de descarga (tail, K valores) y de que haya que comprar en cada tramo de carga (head, K + 1 valores). Cada
    cuantil representa la masa que va de la mitad del hueco anterior a la mitad del siguiente."""
    a = [float(v) for v in alphas]
    K = len(a)
    mass = []
    for j in range(K):
        lo = 0.0 if j == 0 else 0.5 * (a[j - 1] + a[j])
        hi = 1.0 if j == K - 1 else 0.5 * (a[j] + a[j + 1])
        mass.append(hi - lo)
    tail = [sum(mass[i:]) for i in range(K)]                 # tramo i de descarga: de q[i-1] a q[i]
    head = [sum(mass[K - i:]) for i in range(K + 1)]         # tramo i de carga: de -q[K-i] a -q[K-i-1]
    return np.array(tail), np.array(head)


class SolarCand:
    """Previsor de consumo y solar con tablas ampliadas (mismo contrato que NetLoadForecaster). Qué añade:
    1. Consumo: una regresión por hora del día y antelación con el cociente consumo/perfil de la hora
       anterior, el de ayer a la hora que se prevé y el de ayer a la hora anterior.
    2. Noche: el contador se queda congelado de 23 a 5 h, así que desde las 23 h el consumo hasta las 6 h se
       conoce exacto (es la última lectura).
    3. Márgenes: cuantil 16 % del error del consumo (por hora) y cuantil 84 % del de la solar (por tramo de
       claridad prevista, proporcional al cielo despejado de la fecha), sumados en cuadratura.
    4. Tope de descarga: si ha actuado el tope "lo comprado la hora anterior", se llega hasta el consumo neto
       previsto menos el margen.
    5. Solar: la claridad prevista usa la última hora y la media del día, con un coeficiente por antelación;
       para mañana, la media de hoy.
    6. Cielo despejado en hora solar (sin el cambio de hora) e interpolado entre meses según el día: el test
       son los días 25-31 y el train los días 1-24, y la curva del test está a medio camino del mes siguiente.
    El ajuste de las tablas está en scripts/p1_lab/hard_solar_cand.py (fit_prior), que es donde se diseñó."""

    def __init__(self, prior: Optional[dict], base, z: float = Z_SOLAR, reg: bool = True, freeze: bool = True,
                 quant: bool = True, uncap: bool = True, pvreg: bool = True, shade_now: bool = True,
                 room: bool = False, value_z: bool = False):
        self.base = base
        self.z = z                    # márgenes en "desviaciones típicas" (1 = cuantiles 16 % y 84 %)
        self.z_plan = Z_PLAN_SOLAR    # margen de las horas siguientes en el plan
        self.reg, self.freeze, self.quant, self.uncap, self.pvreg, self.shade_now = reg, freeze, quant, uncap, pvreg, shade_now
        self.room = room              # margen de la solar de las horas siguientes con el error a esa antelación
        self.value_z = value_z        # margen al descargar según lo que vale esta hora frente a la alternativa
        try:
            self.w_co2, self.w_cost = float(prior["w_co2"]), float(prior["w_cost"])
        except Exception:
            self.w_co2, self.w_cost = 0.7 / 0.085, 0.3 / 0.138      # medias del train: solo importa la proporción
        prior = prior or {}
        try:
            self.clear = [[float(v) for v in row] for row in prior["pv_clear"]]      # [mes][hora solar], kW ya x12
            self.mean = [[float(v) for v in row] for row in prior["pv_mean"]]
            self.centers = [float(v) for v in prior["pv_day"]]                       # día medio de los datos de cada mes
            self.sky = bool(prior["sky"])                                            # hora solar e interpolación entre meses
            self.pv_a = [float(v) for v in prior["pv_a"]]                            # [antelación] última hora con sol
            self.pv_b = [float(v) for v in prior["pv_b"]]                            # [antelación] media del día
            self.pv_c = float(prior["pv_c"])                                         # de la media de un día al siguiente
            self.pv_up = [float(v) for v in prior["pv_up"]]                          # [tramo de claridad] cuantil 84 % / despejado
            self.pv_up_lead = prior.get("pv_up_lead")                                # [antelación][tramo] ídem a k horas vista
            self.pv_up_next = prior.get("pv_up_next")                                # [tramo] ídem para el día siguiente
            self.load_how = [float(v) for v in prior["load_how"]]                    # [168] perfil de consumo
            self.reg3 = prior["load_reg3"]                                           # [hora][antelación] -> 4 coeficientes
            self.reg1 = prior["load_reg1"]                                           # [hora][antelación] -> 2 coeficientes
            self.l_lo = [float(v) for v in prior["load_lo"]]                         # [hora] cuantil 16 % del error / perfil
            self.l_lo0 = [float(v) for v in prior["load_lo0"]]                       # ídem sin lectura anterior
            self.net_sd = [float(v) for v in prior.get("net_sd", [DEFAULT_SD_KW] * 24)]
            self.ok = (len(self.clear) == 12 and len(self.mean) == 12 and len(self.load_how) == 168
                       and len(self.reg3) == 24 and len(self.reg1) == 24 and len(self.pv_a) >= PV_LEADS
                       and len(self.pv_up) == len(KAPPA_BINS) + 1 and len(self.l_lo) == 24 and len(self.l_lo0) == 24)
        except Exception:
            self.ok = False
        self.weather = {}
        self.new_block()
        self.net_lo0 = float("nan")     # consumo neto de esta hora menos el margen (lo usa adjust_action)
        self.net_lo0_charge = float("nan")
        self.fresh = False              # True si forecast() ha dejado net_lo0 para esta hora
        # Plan con incertidumbre (v12): cuantiles del error del consumo neto de la hora actual, en unidades del margen.
        self.scen_ok = False            # hay tabla de cuantiles válida
        self.scen_used = False          # la acción de esta hora ha salido del plan con incertidumbre
        self.hold = False               # update() ya se ha hecho en esta hora (para no aprender dos veces de ella)
        self.scen_u = None
        self.scen_tail = None
        self.scen_head = None

    def new_block(self) -> None:
        """Empieza otra semana del test (hace un mes de la anterior): lo aprendido de las últimas horas no vale."""
        self.r_hist = []                # consumo / perfil - 1 de las últimas horas; [-1] = hora anterior
        self.w_hist = []                # peso (0,7 CO2 + 0,3 precio) de las últimas horas; [-1] = hora actual
        self.last_value = None          # fecha (ns) de la última observación, para saber si las horas son seguidas
        self.meter_down = False
        self.pv_alive = False           # la última lectura de solar fue válida y mayor que cero
        self.load_prev = float("nan")
        self.cur_day = None             # día al que pertenecen los acumulados de claridad
        self.day_sum, self.day_n = 0.0, 0
        self.last_dev = float("nan")    # desviación de la claridad en la última hora con sol de hoy
        self.last_any = float("nan")    # ídem, aunque sea de ayer (solo para la receta antigua)
        self.prev_day_mean = float("nan")

    def sky_at(self, ts) -> tuple:
        """Cielo despejado y solar media (kW) de una fecha: tabla del mes en hora solar, interpolada con el mes vecino."""
        mo = ts.month
        if not self.sky:
            return self.clear[mo - 1][ts.hour], self.mean[mo - 1][ts.hour]
        hs = (ts.hour - 1) % 24 if summer_time(ts) else ts.hour
        other, w = neighbour_month(mo, ts.day, self.centers)
        return ((1.0 - w) * self.clear[mo - 1][hs] + w * self.clear[other][hs],
                (1.0 - w) * self.mean[mo - 1][hs] + w * self.mean[other][hs])

    def profile(self, ts) -> float:
        try:
            v = self.load_how[campus_how(ts)]
            if math.isfinite(v) and v > 0:
                return v
            v = float(self.base.load_how[campus_how(ts)])
            return v if math.isfinite(v) and v > 0 else float("nan")
        except Exception:
            return float("nan")

    def set_scenarios(self, scen: Optional[dict]) -> None:
        """scen = {"alphas": [K niveles], "u": [K cuantiles del error del consumo neto / margen]} (hard_solar.json).
        Con ella, cada hora del plan lleva la distribución entera del consumo neto que se verá al llegar."""
        self.scen_ok, self.scen_used, self.hold = False, False, False
        try:
            alphas = [float(v) for v in scen["alphas"]]
            u = [float(v) for v in scen["u"]]
            good = (len(alphas) == len(u) and len(u) >= 3 and all(math.isfinite(v) for v in u)
                    and all(0.0 < v < 1.0 for v in alphas)
                    and all(alphas[i] < alphas[i + 1] and u[i] <= u[i + 1] for i in range(len(u) - 1)))
            if good and self.ok:
                self.scen_u = np.array(u)
                self.scen_tail, self.scen_head = scen_probs(alphas)
                self.scen_ok = True
        except Exception:
            self.scen_ok = False

    def scenarios(self, times: list) -> tuple:
        """Consumo y solar previstos (sin margen) y margen de cada hora del plan, con las tablas del previsor."""
        z, z_plan = self.z, self.z_plan
        try:
            self.z, self.z_plan = 0.0, 0.0
            load, pv = self.forecast_tables(times)
            self.z, self.z_plan = 1.0, 1.0
            pv1 = self.forecast_tables(times)[1]
        finally:
            self.z, self.z_plan = z, z_plan
            self.fresh = False          # net_lo0 ha quedado calculado con otro margen: que nadie lo use
        return load, pv, np.maximum(pv1 - pv, 0.0)

    def update(self, obs, weather: Optional[dict] = None) -> None:
        if self.hold:
            return                      # ya se ha aprendido de esta hora (el plan con incertidumbre llamó antes)
        self.weather = weather or {}
        self.fresh = False
        try:
            self.base.update(obs)       # el perfil de P2 sigue aprendiendo (lo usa el respaldo)
        except Exception:
            pass
        try:
            self.learn(obs)
        except Exception:
            self.new_block()

    def learn(self, obs) -> None:
        load, pv, ts = obs.load_prev_kw, obs.pv_prev_kw, obs.timestamp
        w_now = float("nan")
        try:
            w_now = self.w_co2 * float(obs.co2[0]) + self.w_cost * float(obs.price[0])
        except Exception:
            pass
        self.meter_down = load == 0.0
        self.pv_alive = math.isfinite(pv) and pv > 1.0
        self.load_prev = load if (math.isfinite(load) and load > 0) else float("nan")
        if not self.ok or ts is None:
            return
        value = ts.value
        seguido = self.last_value is not None and value - self.last_value == HOUR_NS
        if not seguido:                 # primera hora o salto de fechas: la lectura no es de la hora anterior
            keep = self.load_prev if self.last_value is None else float("nan")
            self.new_block()
            self.load_prev = keep
        self.last_value = value
        if math.isfinite(w_now):
            self.w_hist.append(w_now)
            if len(self.w_hist) > 60:
                del self.w_hist[:30]
        prev = ts - ONE_HOUR_BACK
        r = float("nan")
        if math.isfinite(self.load_prev):
            prof = self.profile(prev)
            if math.isfinite(prof):
                r = min(max(self.load_prev / prof, RATIO_MIN), RATIO_MAX) - 1.0
        self.r_hist.append(r)
        if len(self.r_hist) > 80:
            del self.r_hist[:40]
        day_prev, day_now = (prev.year, prev.month, prev.day), (ts.year, ts.month, ts.day)
        if self.cur_day is None:
            self.cur_day = day_prev
        if math.isfinite(pv) and day_prev == self.cur_day:
            clear, mean = self.sky_at(prev)
            if clear >= CLEAR_MIN_KW:
                dev = min(max(pv / clear, 0.0), KAPPA_MAX) - mean / clear
                self.day_sum += dev
                self.day_n += 1
                self.last_dev = self.last_any = dev
        if day_now != self.cur_day:     # cambia el día: la media de hoy pasa a ser "la de ayer"
            self.prev_day_mean = self.day_sum / self.day_n if self.day_n > 0 else float("nan")
            self.cur_day, self.day_sum, self.day_n, self.last_dev = day_now, 0.0, 0, float("nan")

    def forecast(self, obs, times: list) -> tuple:
        H = max(1, len(times))
        try:
            if self.ok and times and times[0] is not None:
                return self.forecast_tables(times)
        except Exception:
            pass
        load, pv = self.base.forecast(obs, H)
        load, pv = np.maximum(load, 0.0), np.maximum(pv, 0.0)
        self.net_lo0, self.fresh = float(load[0] - pv[0]) - self.z * DEFAULT_SD_KW, True
        self.net_lo0_charge = self.net_lo0
        return load, pv

    def forecast_tables(self, times: list) -> tuple:
        H = len(times)
        now = times[0]
        v0 = now.value
        hist = self.r_hist
        n = len(hist)
        r1 = hist[-1] if n >= 1 else float("nan")
        ry1 = hist[-25] if n >= 25 else float("nan")
        have_r1 = math.isfinite(r1)
        frozen = self.load_prev if (self.freeze and now.hour in FROZEN_HOURS) else float("nan")
        in_night = math.isfinite(frozen)
        day0 = now.day
        day_mean = self.day_sum / self.day_n if self.day_n > 0 else float("nan")
        load, pv, margin = np.empty(H), np.empty(H), np.empty(H)
        pv_margin0 = 0.0                 # la parte del margen de esta hora que viene de la solar
        for k, t in enumerate(times):
            h = t.hour
            seguido = t.value - v0 == k * HOUR_NS
            prof = self.profile(t)
            if not math.isfinite(prof):
                prof = self.load_prev if math.isfinite(self.load_prev) else 0.0
            # ---- consumo
            lo_rel = self.l_lo[h]
            if in_night and seguido and h in FROZEN_HOURS:
                load_k = frozen                         # contador congelado: es la última lectura
            else:
                in_night = False
                dev = 0.0
                if seguido and k < 24 and have_r1:
                    if self.reg:
                        ry = hist[k - 24] if n >= 24 - k else float("nan")
                        if math.isfinite(ry) and math.isfinite(ry1):
                            c = self.reg3[h][k]
                            dev = c[0] * r1 + c[1] * ry + c[2] * ry1 + c[3]
                        else:
                            c = self.reg1[h][k]
                            dev = c[0] * r1 + c[1]
                    else:
                        dev = r1 * 0.9 ** (k + 1)
                elif k == 0:
                    lo_rel = self.l_lo0[h]              # sin lectura anterior: solo el perfil, margen más ancho
                load_k = prof * (1.0 + dev)
            # ---- solar
            clear, mean = self.sky_at(t)
            kappa = 0.0
            if clear > 0:
                dev = 0.0
                if seguido:
                    if self.pvreg:
                        if t.day == day0:
                            if self.day_n > 0:
                                if k < PV_LEADS:
                                    dev = self.pv_a[k] * self.last_dev + self.pv_b[k] * day_mean
                            elif math.isfinite(self.prev_day_mean):
                                dev = self.pv_c * self.prev_day_mean
                        elif self.day_n >= MIN_DAY_HOURS:
                            dev = self.pv_c * day_mean
                        elif self.day_n == 0 and math.isfinite(self.prev_day_mean):
                            dev = self.pv_c * self.pv_c * self.prev_day_mean
                    elif math.isfinite(self.last_any):
                        dev = self.last_any * 0.85 ** (k + 1)
                kappa = min(max(mean / clear + dev, 0.0), KAPPA_MAX)
                pv_k = clear * kappa
            else:
                pv_k = max(mean, 0.0)
            # ---- margen del consumo neto de esa hora cuando llegue (cuantiles del error de la hora actual)
            if self.quant:
                b = 0
                while b < len(KAPPA_BINS) and kappa >= KAPPA_BINS[b]:
                    b += 1
                up = self.pv_up[b]
                if self.room and k >= 1 and seguido and self.pv_up_lead is not None:
                    up = self.pv_up_lead[k][b] if (t.day == day0 and k < PV_LEADS) else self.pv_up_next[b]
                m_load, m_pv = lo_rel * prof, up * clear
                margin[k] = math.sqrt(m_load * m_load + m_pv * m_pv)
                if k == 0:
                    pv_margin0 = m_pv
            else:
                margin[k] = self.net_sd[h]
            load[k], pv[k] = load_k, pv_k
        if self.meter_down:              # contador caído (lectura 0 exacta): si sigue, descargar es tirar energía
            load[0] = 0.0
            if self.pv_alive:            # ...pero si la solar sigue viva, lo que produzca es excedente que guardar
                margin[0] = pv_margin0
            else:
                pv[0], margin[0] = 0.0, 0.0
        load, pv = np.maximum(load, 0.0), np.maximum(pv, 0.0)
        z_now = self.discharge_z()
        self.net_lo0 = float(load[0] - pv[0]) - z_now * float(margin[0])           # tope de la descarga
        self.net_lo0_charge = float(load[0] - pv[0]) - self.z * float(margin[0])    # excedente que puede haber
        self.fresh = True
        # El plan cuenta ya con el margen en todas las horas (se suma a la solar; solo mueve decisiones).
        shade = self.z_plan * margin
        shade[0] = z_now * float(margin[0]) if self.shade_now else 0.0
        return load, pv + shade

    def discharge_z(self) -> float:
        """Margen al descargar, en desviaciones típicas. Regla del vendedor de periódicos: si lo que no se
        descarga ahora acabará usándose en una hora de peso mu, conviene descargar hasta el cuantil 1 - mu/w
        del consumo neto, es decir, z = F^-1(mu / w). mu = peso de la séptima peor hora de las últimas 24:
        una descarga completa cubre unas 6 horas de consumo medio."""
        hist = self.w_hist
        if not self.value_z or len(hist) < 12:
            return self.z
        w_now = hist[-1]
        ranked = sorted(hist[-24:], reverse=True)
        mu = ranked[min(VALUE_RANK, len(ranked) - 1)]
        if not (w_now > 0 and mu > 0):
            return self.z
        ratio = min(max(mu / w_now, 0.5), 0.977)        # z entre 0 y 2
        return 4.91 * (ratio ** 0.14 - (1.0 - ratio) ** 0.14)   # inversa de la normal (aproximación de Tukey)

    def adjust_action(self, action_kw: float, obs, p) -> float:
        """Margen de seguridad con el consumo neto de ESTA hora, que solo se conoce aproximadamente."""
        if self.scen_used:
            # La acción ya cuenta con la incertidumbre. Único seguro: con el contador caído no se descarga.
            return max(action_kw, 0.0) if self.meter_down else action_kw
        if self.meter_down and not self.pv_alive:
            return max(action_kw, 0.0)      # contador caído y sin solar: no se descarga ni hay excedente que guardar
        if not self.fresh or not math.isfinite(self.net_lo0):
            return action_kw
        limit = max(self.net_lo0, 0.0)
        if action_kw < 0:
            d = -action_kw
            if self.uncap and limit > d:
                # ¿Ha actuado el tope de la política (descarga = consumo neto de la hora anterior)? Entonces el
                # plan quería más: se llega hasta el consumo neto previsto menos el margen.
                net_prev = obs.load_prev_kw - obs.pv_prev_kw
                if math.isfinite(net_prev) and net_prev > 0 and abs(d - net_prev) <= 1e-6:
                    d = limit
            return -min(d, limit)           # descargar por encima del consumo neto real es verter
        surplus = -self.net_lo0_charge      # excedente solar que puede llegar a haber esta hora
        if surplus > action_kw:
            return min(surplus, p.max_charge_kw)    # lo que no se guarde se regala a la red
        return action_kw


def make_netload(prior: Optional[dict], base, **cfg):
    """El previsor de consumo y solar del agente: el de tablas ampliadas (`cand` en hard_solar.json) si están y
    son válidas; si no, el sencillo. La solar que ve el previsor de respaldo de P2 se pasa a x12 una sola vez."""
    try:
        tables = (prior or {}).get("cand")
        if tables:
            cand = SolarCand(tables, base)
            if cand.ok:
                try:
                    base.pv_prior = base.pv_prior * PV_FACTOR
                except Exception:
                    pass
                cand.set_scenarios((prior or {}).get("scen"))      # sin tabla: plan con el margen fijo
                return cand
    except Exception:
        pass
    return NetLoadForecaster(prior, base, **cfg)
