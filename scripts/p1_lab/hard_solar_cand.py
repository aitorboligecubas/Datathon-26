"""Candidato del encargo "solar" (HARD MODE): previsión de consumo y solar, y márgenes con su incertidumbre.

Owner: P1 (laboratorio). Contrato de battery.hard_solar.NetLoadForecaster:
    f = make(exclude, base)                     # fábrica para el banco (ajusta sin las horas de `exclude`)
    f.update(obs, weather)                      # una vez por hora, antes de forecast
    load_kw, pv_kw = f.forecast(obs, times)     # arrays de la longitud de `times`, >= 0, [0] = hora actual
    a = f.adjust_action(action_kw, obs, p)      # último retoque de la acción de esta hora
    to_prior(exclude=None) -> dict              # todo lo ajustado, listo para guardar en models/ (JSON)

Qué cambia respecto al agente actual (cada pieza se puede apagar para medirla):
1. CONSUMO (`reg`). Una regresión por hora del día y antelación sobre tres pistas: el cociente consumo/perfil
   de la hora anterior, el de ayer a la hora que se prevé y el de ayer a la hora anterior. Baja el error de la
   hora actual un 15 % y el de 3 horas vista un 25 % (fuera de muestra).
2. NOCHE (`freeze`). El contador se queda congelado de 23 a 5 h: desde las 23 h el consumo hasta las 6 h se
   conoce exacto (es la última lectura). Margen cero en esas horas.
3. MÁRGENES (`quant`). El margen ya no es una desviación típica fija por hora del día. Es el cuantil 16 % del
   error medido del consumo (por hora) y el cuantil 84 % del de la solar (por tramo de claridad prevista,
   proporcional al cielo despejado de la fecha), sumados en cuadratura. En diciembre es pequeño; en junio, mayor.
4. TOPE (`uncap`). La política recorta la descarga al consumo neto de la hora ANTERIOR. Cuando la solar cae
   (tarde) o el consumo sube (6-8 h), ese tope deja energía sin usar. Si el tope ha actuado, se descarga
   hasta el consumo neto previsto menos el margen. Con el contador caído no se toca.
5. SOLAR (`pvreg`). La claridad prevista usa la última hora y la media del día, con un coeficiente por
   antelación ajustado; para mañana, la media de hoy.
6. CIELO DESPEJADO (`sky`, se decide al ajustar). La tabla va en hora solar (sin el cambio de hora) y se
   interpola entre meses según el día. El test son los días 25-31 y el train los días 1-24: la curva del
   test está a medio camino del mes siguiente, y en octubre y marzo el cambio de hora la mueve una hora.

Solo numpy, pandas y math. La parte de "ajuste" (abajo) no se empaqueta.
"""
import math
from typing import Optional

import numpy as np
import pandas as pd

CLEAR_MIN = 30.0             # kW; por debajo, el "cielo despejado" no sirve para medir la claridad (como hard_solar)
KAPPA_MAX = 1.5              # tope de la claridad (como hard_solar)
RATIO_MIN, RATIO_MAX = 0.3, 3.0     # topes del cociente consumo / perfil (como hard_solar)
FROZEN_HOURS = frozenset((23, 0, 1, 2, 3, 4, 5))   # horas con el contador congelado (100 % de las noches del train)
PV_LEADS = 16                # antelaciones con coeficiente propio: ningún día tiene más de 16 horas de sol
KAPPA_BINS = (0.25, 0.5, 0.75, 1.0)     # tramos de claridad prevista para el margen de la solar (iguales, sin afinar)
Q_LOW, Q_HIGH = 0.16, 0.84   # cuantiles del margen: equivalen a 1 desviación típica (el margen del agente actual)
MONTH_DAYS = 30.4            # días medios de un mes, para interpolar el cielo despejado
MIN_DAY_HOURS = 3            # horas de sol vistas hoy para que la media de hoy sirva de pista para mañana
DEFAULT_SD = 150.0           # kW; margen si no hay tablas (como hard_solar)
VALUE_RANK = 6               # la séptima peor hora de las últimas 24 (una descarga cubre unas 6 h de consumo medio)
MIN_FIT_ROWS = 200           # filas mínimas para ajustar un coeficiente de la solar (si no, vale el día típico)
HOUR_NS = 3600 * 10 ** 9
ONE_HOUR_CAND = pd.Timedelta(hours=1)
HOLIDAYS_CAND = frozenset((
    (2025, 9, 11), (2025, 9, 24), (2025, 10, 12), (2025, 11, 1), (2025, 12, 6), (2025, 12, 8),
    (2025, 12, 24), (2025, 12, 25), (2025, 12, 26), (2025, 12, 27), (2025, 12, 28), (2025, 12, 29),
    (2025, 12, 30), (2025, 12, 31), (2026, 1, 1), (2026, 1, 2), (2026, 1, 3), (2026, 1, 4),
    (2026, 1, 5), (2026, 1, 6), (2026, 4, 3), (2026, 4, 6), (2026, 5, 1), (2026, 5, 25),
    (2026, 6, 24), (2026, 8, 15)))     # los mismos días que battery.hard_solar.CAMPUS_HOLIDAYS
LAST_SUNDAY = {}             # (año, mes) -> día del último domingo (cambio de hora)


# ------------------------------------------------------------------------------------ inferencia
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
    if (ts.year, ts.month, ts.day) in HOLIDAYS_CAND:
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


class SolarCand:
    def __init__(self, prior: Optional[dict], base, z: float = 1.0, reg: bool = True, freeze: bool = True,
                 quant: bool = True, uncap: bool = True, pvreg: bool = True, shade_now: bool = True,
                 room: bool = False, pv_factor: float = 1.0, value_z: bool = False):
        self.base = base
        self.z = z                    # márgenes en "desviaciones típicas" (1 = cuantiles 16 % y 84 %)
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
            self.net_sd = [float(v) for v in prior.get("net_sd", [DEFAULT_SD] * 24)]
            self.ok = (len(self.clear) == 12 and len(self.mean) == 12 and len(self.load_how) == 168
                       and len(self.reg3) == 24 and len(self.reg1) == 24 and len(self.pv_a) >= PV_LEADS
                       and len(self.pv_up) == len(KAPPA_BINS) + 1 and len(self.l_lo) == 24 and len(self.l_lo0) == 24)
        except Exception:
            self.ok = False
        if pv_factor != 1.0:
            try:    # al integrarlo (pv_factor = 12): la solar que ve el previsor de respaldo de P2 también es x12.
                self.base.pv_prior = self.base.pv_prior * pv_factor     # En el banco ya lo hace el previsor actual.
            except Exception:
                pass
        self.weather = {}
        self.new_block()
        self.net_lo0 = float("nan")     # consumo neto de esta hora menos el margen (lo usa adjust_action)
        self.net_lo0_charge = float("nan")
        self.fresh = False              # True si forecast() ha dejado net_lo0 para esta hora

    def new_block(self) -> None:
        """Empieza otra semana del test (hace un mes de la anterior): lo aprendido de las últimas horas no vale."""
        self.r_hist = []                # consumo / perfil - 1 de las últimas horas; [-1] = hora anterior
        self.w_hist = []                # peso (0,7 CO2 + 0,3 precio) de las últimas horas; [-1] = hora actual
        self.last_value = None          # fecha (ns) de la última observación, para saber si las horas son seguidas
        self.meter_down = False
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

    def update(self, obs, weather: Optional[dict] = None) -> None:
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
        prev = ts - ONE_HOUR_CAND
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
            if clear >= CLEAR_MIN:
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
        self.net_lo0, self.fresh = float(load[0] - pv[0]) - self.z * DEFAULT_SD, True
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
            else:
                margin[k] = self.net_sd[h]
            load[k], pv[k] = load_k, pv_k
        if self.meter_down:              # contador caído (lectura 0 exacta): si sigue, descargar es tirar energía
            load[0], pv[0], margin[0] = 0.0, 0.0, 0.0
        load, pv = np.maximum(load, 0.0), np.maximum(pv, 0.0)
        z_now = self.discharge_z()
        self.net_lo0 = float(load[0] - pv[0]) - z_now * float(margin[0])           # tope de la descarga
        self.net_lo0_charge = float(load[0] - pv[0]) - self.z * float(margin[0])    # excedente que puede haber
        self.fresh = True
        # El plan cuenta ya con el margen en todas las horas (se suma a la solar; solo mueve decisiones).
        shade = self.z * margin
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
        if self.meter_down:
            return max(action_kw, 0.0)      # contador caído: no se descarga, y no hay excedente que guardar
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


# ------------------------------------------------------------------------------------ ajuste (no se empaqueta)
def lead(a: np.ndarray, k: int) -> np.ndarray:
    """a[t + k] (NaN si no existe). k puede ser negativo (pasado)."""
    out = np.full(len(a), np.nan)
    if k == 0:
        out[:] = a
    elif k > 0:
        out[:len(a) - k] = a[k:]
    else:
        out[-k:] = a[:k]
    return out


def sky_lookup(clear, mean, centers, idx, sky: bool) -> tuple:
    """Cielo despejado y media de cada hora de `idx`, con la misma receta que SolarCand.sky_at."""
    cl, mn = np.zeros(len(idx)), np.zeros(len(idx))
    for i, ts in enumerate(idx):
        mo = ts.month
        if not sky:
            cl[i], mn[i] = clear[mo - 1][ts.hour], mean[mo - 1][ts.hour]
            continue
        hs = (ts.hour - 1) % 24 if summer_time(ts) else ts.hour
        other, w = neighbour_month(mo, ts.day, centers)
        cl[i] = (1.0 - w) * clear[mo - 1][hs] + w * clear[other][hs]
        mn[i] = (1.0 - w) * mean[mo - 1][hs] + w * mean[other][hs]
    return cl, mn


def fit_prior(table: pd.DataFrame, sky: bool = True) -> dict:
    """Ajusta todas las tablas con las horas de `table` (columnas timestamp, load_kw y pv_kw ya x12)."""
    t = table.sort_values("timestamp")
    idx = pd.date_range(t.timestamp.min().normalize(), t.timestamp.max(), freq="h")
    T = t.set_index("timestamp").reindex(idx)                 # los huecos (otras semanas, horas excluidas) quedan en NaN
    pv = T.pv_kw.to_numpy(float)
    load = T.load_kw.where(T.load_kw > 0).to_numpy(float)     # un 0 exacto es el contador caído
    hour, month, day = idx.hour.to_numpy(), idx.month.to_numpy(), idx.day.to_numpy()
    # ---- cielo despejado (percentil 90) y media por mes y hora solar
    hs = np.array([(ts.hour - 1) % 24 if (sky and summer_time(ts)) else ts.hour for ts in idx])
    d = pd.DataFrame({"mo": month, "hs": hs, "pv": pv, "day": day})[np.isfinite(pv)]
    gq, gm, gd = d.groupby(["mo", "hs"]).pv.quantile(0.9), d.groupby(["mo", "hs"]).pv.mean(), d.groupby("mo").day.mean()
    clear, mean, centers = np.full((12, 24), np.nan), np.full((12, 24), np.nan), np.full(12, np.nan)
    for mo in range(1, 13):
        if mo in gd.index:
            centers[mo - 1] = gd[mo]
            for h in range(24):
                clear[mo - 1, h], mean[mo - 1, h] = gq.get((mo, h), 0.0), gm.get((mo, h), 0.0)
    for arr in (clear, mean):            # meses sin datos (noviembre): media de los vecinos
        for mo in range(12):
            if not np.isfinite(arr[mo]).all():
                a, b = arr[(mo - 1) % 12], arr[(mo + 1) % 12]
                arr[mo] = np.where(np.isfinite(a) & np.isfinite(b), (a + b) / 2, np.where(np.isfinite(a), a, b))
        arr[~np.isfinite(arr)] = 0.0
    centers[~np.isfinite(centers)] = np.nanmean(centers)
    cl, mn = sky_lookup(clear.tolist(), mean.tolist(), centers.tolist(), idx, sky)
    typ = np.where(cl > 0, mn / np.where(cl > 0, cl, 1.0), 0.0)
    dev = np.where(cl >= CLEAR_MIN, np.clip(pv / np.where(cl > 0, cl, 1.0), 0.0, KAPPA_MAX) - typ, np.nan)
    # ---- lo que el agente sabe a cada hora: última hora con sol de hoy, media de hoy hasta ahora, media de ayer
    s = pd.Series(dev, index=idx)
    dkey = idx.normalize()
    same_prev = np.r_[False, dkey[1:] == dkey[:-1]]
    last_b = s.groupby(dkey).ffill().shift(1).where(same_prev).to_numpy()
    n_b = s.notna().groupby(dkey).cumsum().shift(1).where(same_prev, 0.0).to_numpy()
    sum_b = s.fillna(0.0).groupby(dkey).cumsum().shift(1).where(same_prev, 0.0).to_numpy()
    day_b = np.where(n_b > 0, sum_b / np.where(n_b > 0, n_b, 1.0), np.nan)
    full = s.groupby(dkey).mean()
    prev_full = pd.Series(dkey, index=idx).map(full.shift(1, freq="D")).to_numpy(float)
    dnum = dkey.to_numpy().astype("int64")
    pv_a, pv_b = [0.0] * PV_LEADS, [0.0] * PV_LEADS
    nb = len(KAPPA_BINS) + 1
    pv_up_lead = [[0.0] * nb for _ in range(PV_LEADS)]

    def upper_by_bin(rel_err, kap_hat, sel) -> list:
        """Cuantil 84 % del error relativo por tramo de claridad prevista (el global si hay menos de 30 casos)."""
        if sel.sum() < 30:
            return [0.0] * nb
        glob = max(float(np.quantile(rel_err[sel], Q_HIGH)), 0.0)
        bins_ = np.digitize(kap_hat, KAPPA_BINS)
        return [max(float(np.quantile(rel_err[sel & (bins_ == b)], Q_HIGH)), 0.0) if (sel & (bins_ == b)).sum() >= 30 else glob
                for b in range(nb)]

    for k in range(PV_LEADS):
        y, c, m = lead(pv, k), lead(cl, k), lead(mn, k)
        ok = (lead(dnum.astype(float), k) == dnum) & np.isfinite(y) & (c >= CLEAR_MIN) & np.isfinite(last_b) & np.isfinite(day_b)
        if ok.sum() >= MIN_FIT_ROWS:
            coef = np.linalg.lstsq(np.c_[c * last_b, c * day_b][ok], (y - m)[ok], rcond=None)[0]
            pv_a[k], pv_b[k] = float(coef[0]), float(coef[1])
        csafe = np.where(c > 0, c, 1.0)
        kap_k = np.clip(m / csafe + pv_a[k] * np.nan_to_num(last_b) + pv_b[k] * np.nan_to_num(day_b), 0.0, KAPPA_MAX)
        pv_up_lead[k] = upper_by_bin((y - c * kap_k) / csafe, kap_k, ok)
    ok = np.isfinite(pv) & (cl >= CLEAR_MIN) & np.isfinite(prev_full)
    x = (cl * prev_full)[ok]
    pv_c = float((x * (pv - mn)[ok]).sum() / max((x * x).sum(), 1e-9))
    kap_n = np.clip(typ + pv_c * np.nan_to_num(prev_full), 0.0, KAPPA_MAX)
    pv_up_next = upper_by_bin((pv - cl * kap_n) / np.where(cl > 0, cl, 1.0), kap_n, ok)
    # ---- error de la solar de la hora actual, por tramo de claridad prevista (cuantil 84 % / cielo despejado)
    dev0 = np.where(np.isfinite(last_b) & np.isfinite(day_b), pv_a[0] * np.nan_to_num(last_b) + pv_b[0] * np.nan_to_num(day_b),
                    np.where(np.isfinite(prev_full), pv_c * np.nan_to_num(prev_full), 0.0))
    kap0 = np.clip(typ + dev0, 0.0, KAPPA_MAX)
    okp = np.isfinite(pv) & (cl >= CLEAR_MIN)
    rel = (pv - cl * kap0) / np.where(cl > 0, cl, 1.0)
    bins = np.digitize(kap0, KAPPA_BINS)
    up_all = max(float(np.quantile(rel[okp], Q_HIGH)), 0.0)
    pv_up = []
    for b in range(len(KAPPA_BINS) + 1):
        sel = okp & (bins == b)
        pv_up.append(max(float(np.quantile(rel[sel], Q_HIGH)), 0.0) if sel.sum() >= 30 else up_all)
    # ---- consumo: perfil por hora de la semana y regresión por hora del día y antelación
    how = np.array([campus_how(ts) for ts in idx])
    prof = pd.Series(load).groupby(how).mean().reindex(range(168))
    prof = prof.fillna(prof.mean()).to_numpy()
    P = prof[how]
    r = np.clip(load / P, RATIO_MIN, RATIO_MAX) - 1.0
    r1, ry1 = lead(r, -1), lead(r, -25)
    reg3 = [[[0.0, 0.0, 0.0, 0.0] for _ in range(24)] for _ in range(24)]
    reg1 = [[[0.0, 0.0] for _ in range(24)] for _ in range(24)]
    for k in range(24):
        y, ry, th = lead(r, k), lead(r, k - 24), (hour + k) % 24
        ok1 = np.isfinite(y) & np.isfinite(r1)
        ok3 = ok1 & np.isfinite(ry) & np.isfinite(ry1)
        for h in range(24):
            s1 = ok1 & (th == h)
            if s1.sum() >= 20:
                c = np.linalg.lstsq(np.c_[r1[s1], np.ones(s1.sum())], y[s1], rcond=None)[0]
                reg1[h][k] = [float(c[0]), float(c[1])]
                reg3[h][k] = [float(c[0]), 0.0, 0.0, float(c[1])]
            s3 = ok3 & (th == h)
            if s3.sum() >= 40:
                c = np.linalg.lstsq(np.c_[r1[s3], ry[s3], ry1[s3], np.ones(s3.sum())], y[s3], rcond=None)[0]
                reg3[h][k] = [float(v) for v in c]
    # ---- error del consumo de la hora actual, por hora (cuantil 16 % / perfil), con la regla de la noche
    ry0 = lead(r, -24)
    c3, c1 = np.array([reg3[h][0] for h in hour]), np.array([reg1[h][0] for h in hour])
    full3 = np.isfinite(r1) & np.isfinite(ry0) & np.isfinite(ry1)
    hat = np.where(full3, c3[:, 0] * np.nan_to_num(r1) + c3[:, 1] * np.nan_to_num(ry0) + c3[:, 2] * np.nan_to_num(ry1) + c3[:, 3],
                   c1[:, 0] * np.nan_to_num(r1) + c1[:, 1])
    load_hat = P * (1.0 + hat)
    night = np.isin(hour, list(FROZEN_HOURS)) & np.isfinite(lead(load, -1))
    load_hat = np.where(night, lead(load, -1), load_hat)
    err = (load - load_hat) / P
    oke = np.isfinite(err) & np.isfinite(r1)
    load_lo, load_lo0 = [], []
    for h in range(24):
        sel = oke & (hour == h)
        load_lo.append(max(-float(np.quantile(err[sel], Q_LOW)), 0.0) + 0.0 if sel.sum() >= 20 else 0.1)
        sel = np.isfinite(r) & (hour == h)
        load_lo0.append(max(-float(np.quantile(r[sel], Q_LOW)), 0.0) if sel.sum() >= 20 else 0.2)
    weights = {}
    if "co2_kg_kwh" in T and "price_eur_kwh" in T:          # pesos del objetivo (solo importa su proporción)
        imp = np.maximum(T.load_kw.to_numpy(float) - pv, 0.0)
        okw = np.isfinite(imp)
        weights = {"w_co2": 0.7 / max(float((imp * T.co2_kg_kwh.to_numpy(float))[okw].mean()), 1e-9),
                   "w_cost": 0.3 / max(float((imp * T.price_eur_kwh.to_numpy(float))[okw].mean()), 1e-9)}
    return {**weights, "sky": bool(sky), "pv_clear": clear.tolist(), "pv_mean": mean.tolist(), "pv_day": [float(v) for v in centers],
            "pv_a": pv_a, "pv_b": pv_b, "pv_c": pv_c, "pv_up": pv_up, "pv_up_lead": pv_up_lead, "pv_up_next": pv_up_next,
            "load_how": [float(v) for v in prof],
            "load_reg3": reg3, "load_reg1": reg1, "load_lo": load_lo, "load_lo0": load_lo0}


PRIOR_CACHE = {}


def to_prior(exclude=None, sky: bool = True) -> dict:
    """Todo lo que necesita SolarCand, como dict que se puede guardar en JSON. Sin `exclude`, con todo el train."""
    import sys
    from pathlib import Path
    repo = Path(__file__).resolve().parents[2]
    for extra in (str(repo / "src"), str(repo / "scripts")):
        if extra not in sys.path:
            sys.path.insert(0, extra)
    import p1_hard as bench
    key = (len(exclude) if exclude else 0, min(exclude) if exclude else None, sky)
    if key not in PRIOR_CACHE:
        table = bench.hard_table()
        if exclude:
            table = table[~table.timestamp.isin(exclude)]
        prior = fit_prior(table, sky=sky)
        prior["net_sd"] = bench.fit_solar(table)["net_sd"]      # la tabla antigua: solo para medir la pieza `quant`
        PRIOR_CACHE[key] = prior
    return PRIOR_CACHE[key]


def make(exclude, base, sky: bool = True, **opts):
    """Fábrica para el banco: ajusta sin las horas de `exclude` y devuelve el previsor."""
    return SolarCand(to_prior(exclude, sky=sky), base, **opts)
