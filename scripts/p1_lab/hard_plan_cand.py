"""Candidato del encargo "plan" (HARD MODE): el plan cuenta con la incertidumbre del consumo neto de cada hora.

Owner: P1 (laboratorio). NO se empaqueta tal cual: el bloque "inferencia" está escrito para poder copiarse a
src/battery/ (solo numpy, scipy, math y typing; tablas en JSON; Python 3.9).

    python scripts/p1_hard.py --split dev --only "agente actual,CANDIDATO" --agent scripts/p1_lab/hard_plan_cand.py:make

Qué cambia respecto al agente actual (v8):
- Hoy el plan rebaja el consumo neto de TODAS las horas con el mismo margen (1,4 "desviaciones típicas", que en
  los datos es el cuantil 10 %) y la descarga de la hora actual se recorta siempre a ese cuantil.
- Aquí cada hora del plan lleva la distribución entera del consumo neto que se verá al llegar: K cuantiles del
  error de la previsión de la hora actual (medido pasando el previsor del agente por el train, sin las horas
  que se evalúan), en unidades del margen que ya calcula el previsor. Descargar d kW saca d/eta de la batería
  pero solo ahorra min(d, n): el primer kW se aprovecha casi seguro y el último casi nunca. El LP lo ve como
  tramos de descarga con rendimiento decreciente (peso de la hora x probabilidad de que el consumo neto supere
  el tramo) y tramos de carga con coste creciente (peso x probabilidad de que ese tramo no sea excedente).
  Es el problema del vendedor de periódicos resuelto dentro del LP: en cada hora se descarga hasta el cuantil
  en que P(n > d) = L / (eta_d·w), donde L (lo que vale un kWh guardado) sale del propio plan.
- La acción de la hora actual es la del LP: sin margen fijo, sin el tope "lo comprado la hora anterior" y sin
  el recorte posterior. Se mantienen los seguros: con el contador caído no se descarga; en una semana sin
  datos, sin fecha, sin tablas o ante cualquier fallo, decide el agente actual (mismo código de src/).

Es la forma (A) del encargo (LP con escenarios), escrita de manera equivalente y más barata: como la compra
esperada de una hora solo depende de la acción de esa hora, las K copias de la compra se convierten en tramos
con cota (K tramos de descarga y K + 1 de carga por hora) y el LP sigue teniendo 24 restricciones.
"""
import math
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import scipy.sparse as sp
from scipy.optimize import linprog

REPO = Path(__file__).resolve().parents[2]
for extra in (str(REPO / "src"), str(REPO / "scripts")):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from battery.hard import HardPolicy  # noqa: E402
from battery.hard_market import KNOWN_HOURS  # noqa: E402
from battery.hard_solar import SolarCand  # noqa: E402
from battery.safety import clip_action  # noqa: E402

# ------------------------------------------------------------------------------------ inferencia
# Niveles de los cuantiles del consumo neto (más finos abajo, que es donde cae casi siempre la decisión de
# descarga). Elegidos a mano antes de medir; no se han afinado con dev.
SCEN_ALPHAS = (0.02, 0.05, 0.10, 0.16, 0.25, 0.35, 0.50, 0.65, 0.80, 0.90, 0.97)
SCEN_LP_CACHE = {}
SCEN_METHODS = ("highs", "highs-ds", "highs-ipm")


def scen_probs(alphas) -> tuple:
    """Para K cuantiles de niveles `alphas`: probabilidad de que el consumo neto supere cada tramo de descarga
    (tail, K valores) y de que haya que comprar en cada tramo de carga (head, K + 1 valores). Cada cuantil
    representa la masa que va de la mitad del hueco anterior a la mitad del siguiente."""
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


def scen_structure(H: int, K: int, eta_c: float, eta_d: float):
    """Matriz de la dinámica: s_k - s_(k-1) + (suma de tramos de descarga)/eta_d - eta_c·(suma de tramos de carga) = 0.
    Columnas: H·K tramos de descarga, H·(K+1) tramos de carga y H cargas al final de cada hora."""
    key = (H, K, eta_c, eta_d)
    if key not in SCEN_LP_CACHE:
        nd, nc = H * K, H * (K + 1)
        dis = sp.csr_matrix((np.full(nd, 1.0 / eta_d), (np.repeat(np.arange(H), K), np.arange(nd))), shape=(H, nd))
        cha = sp.csr_matrix((np.full(nc, -eta_c), (np.repeat(np.arange(H), K + 1), np.arange(nc))), shape=(H, nc))
        eye = sp.identity(H, format="csr")
        shift = sp.diags([np.ones(H - 1)], [-1], shape=(H, H), format="csr")
        SCEN_LP_CACHE[key] = sp.hstack([dis, cha, eye - shift], format="csr")
    return SCEN_LP_CACHE[key]


def plan_scen(soc_kwh: float, nodes, tail, head, weight, terminal_value: float, p) -> tuple:
    """Plan con la incertidumbre del consumo neto. Devuelve (acciones_kw[H], valor de un kWh guardado tras la hora 0).

    nodes[H][K]: cuantiles del consumo neto de cada hora (kW), ascendentes. weight[H]: peso de comprar en cada
    hora. Minimiza la compra ESPERADA ponderada: suma_k w_k·E[max(n_k + c_k - d_k, 0)] - valor_final·s_(H-1).
    Lanza RuntimeError si el LP no se resuelve."""
    nodes = np.asarray(nodes, dtype=float)
    weight = np.asarray(weight, dtype=float)
    H, K = nodes.shape
    pos = np.clip(nodes, 0.0, p.max_discharge_kw)
    wd = np.diff(pos, axis=1, prepend=0.0)                               # anchos de los tramos de descarga
    neg = np.clip(-nodes[:, ::-1], 0.0, p.max_charge_kw)
    wc = np.diff(np.c_[neg, np.full(H, float(p.max_charge_kw))], axis=1, prepend=0.0)   # ídem de carga
    nd, nc = H * K, H * (K + 1)
    cost = np.zeros(nd + nc + H)
    cost[:nd] = -(weight[:, None] * tail[None, :]).ravel()
    cost[nd:nd + nc] = (weight[:, None] * head[None, :]).ravel()
    cost[-1] = -terminal_value
    bounds = np.zeros((nd + nc + H, 2))
    bounds[:nd, 1] = np.maximum(wd, 0.0).ravel()
    bounds[nd:nd + nc, 1] = np.maximum(wc, 0.0).ravel()
    bounds[nd + nc:, 1] = p.capacity_kwh
    b_eq = np.zeros(H)
    b_eq[0] = soc_kwh
    A_eq = scen_structure(H, K, float(p.eta_charge), float(p.eta_discharge))
    for method in SCEN_METHODS:
        try:
            res = linprog(cost, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method=method)
        except Exception:
            continue
        if res.status == 0:
            x = res.x
            actions = x[nd:nd + nc].reshape(H, K + 1).sum(axis=1) - x[:nd].reshape(H, K).sum(axis=1)
            try:
                value = -float(res.eqlin.marginals[0])
            except Exception:
                value = float("nan")
            return actions, value
    raise RuntimeError("LP con escenarios sin solución")


class PlanSolar(SolarCand):
    """El previsor de consumo y solar del agente, que además da los cuantiles del consumo neto de cada hora."""

    scen_ok = False        # hay tabla de cuantiles válida
    scen_used = False      # la acción de esta hora ha salido del plan con escenarios
    hold = False           # update() ya se ha hecho en esta hora (para no aprender dos veces si hay que volver atrás)

    def set_scenarios(self, scen: Optional[dict]) -> None:
        """scen = {"alphas": [K niveles], "u": [K cuantiles del error / margen]} (se guarda en JSON)."""
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

    def update(self, obs, weather: Optional[dict] = None) -> None:
        if self.hold:
            return
        SolarCand.update(self, obs, weather)

    def scenarios(self, times: list) -> tuple:
        """Consumo y solar previstos (sin margen) y margen de cada hora, con las tablas del agente."""
        z, z_plan = self.z, getattr(self, "z_plan", None)      # desde la v10 el plan tiene su propio margen (z_plan)
        try:
            self.z = 0.0
            if z_plan is not None:
                self.z_plan = 0.0
            load, pv = self.forecast_tables(times)
            self.z = 1.0
            if z_plan is not None:
                self.z_plan = 1.0
            pv1 = self.forecast_tables(times)[1]
        finally:
            self.z = z
            if z_plan is not None:
                self.z_plan = z_plan
            self.fresh = False          # net_lo0 ha quedado calculado con otro margen: que nadie lo use
        return load, pv, np.maximum(pv1 - pv, 0.0)

    def adjust_action(self, action_kw: float, obs, p) -> float:
        if self.scen_used:
            # La acción ya cuenta con la incertidumbre. Único seguro: con el contador caído no se descarga.
            return max(action_kw, 0.0) if self.meter_down else action_kw
        return SolarCand.adjust_action(self, action_kw, obs, p)


class PlanPolicy(HardPolicy):
    """HardPolicy con el plan con escenarios. Si no se puede usar, decide HardPolicy tal cual."""

    scen_all_hours = True      # False: escenarios solo en la hora actual (las demás, con el margen fijo de hoy)
    scen_charge = True         # False: la carga de la hora actual, como hoy (al menos el excedente posible)
    n_scen = 0                 # horas decididas con el plan con escenarios

    def plan_action(self, obs) -> float:
        nl = self.netload
        action = None
        try:
            nl.scen_used = False
            if getattr(nl, "scen_ok", False):
                nl.hold = False
                nl.update(obs, self.weather)
                nl.hold = True          # si hay que volver a la política actual, que no aprenda dos veces de esta hora
                action = self.plan_scenarios(obs)
        except Exception:
            action = None
        try:
            if action is not None:
                nl.scen_used = True
                self.n_scen += 1
                return action
            return HardPolicy.plan_action(self, obs)
        finally:
            try:
                nl.hold = False         # siempre: la semilla del principio de cada semana entra por update()
            except Exception:
                pass

    def cap_discharge(self, action_kw: float, obs) -> float:
        if getattr(self.netload, "scen_used", False):
            return action_kw        # el tope "lo comprado la hora anterior" ya no hace falta (ver PlanSolar.adjust_action)
        return HardPolicy.cap_discharge(self, action_kw, obs)

    def plan_scenarios(self, obs) -> Optional[float]:
        """Acción de esta hora con el plan con escenarios, o None si toca decidir como el agente actual."""
        nl = self.netload
        if self.no_data_block or self.elapsed_s > self.time_budget_s:
            return None                 # semana sin datos de contador o sin tiempo: la política actual
        times = self.horizon_times(obs)
        if times and len(obs.price) < KNOWN_HOURS:
            times = times[:len(obs.price)]
        if not times or times[0] is None:
            return None
        H = len(times)
        load, pv, margin = nl.scenarios(times)
        price, co2 = self.market.forecast(obs, times, self.weather)
        weight = self.w_co2 * co2 + self.w_cost * price
        ends = H < self.horizon
        terminal = 0.0 if ends else float(np.quantile(weight, self.terminal_quantile)) * self.p.eta_discharge
        net = load - pv
        nodes = net[:, None] + margin[:, None] * nl.scen_u[None, :]
        if not self.scen_all_hours and H > 1:
            nodes[1:] = (net[1:] - nl.z * margin[1:])[:, None]      # las horas siguientes, con el margen fijo
        if not (np.isfinite(nodes).all() and np.isfinite(weight).all() and math.isfinite(obs.soc_kwh)):
            return None
        actions, _ = plan_scen(obs.soc_kwh, nodes, nl.scen_tail, nl.scen_head, weight, terminal, self.p)
        action = float(actions[0])
        if not self.scen_charge and action >= 0:
            action = max(action, min(-(float(net[0]) - nl.z * float(margin[0])), self.p.max_charge_kw))
        return clip_action(action, obs.soc_kwh, self.p)


# ------------------------------------------------------------------------------------ ajuste (no se empaqueta)
def replay_errors(table, tables: dict):
    """Pasa el previsor del agente por las horas de `table` como en el test (hora a hora, con su memoria, y
    sin lectura tras cada salto de fechas) y devuelve, por hora: consumo neto real, previsto y margen."""
    import pandas as pd
    from battery.obs import Obs
    t = table.sort_values("timestamp").reset_index(drop=True)
    cand = SolarCand(tables, None)
    stamps = pd.DatetimeIndex(t.timestamp)
    load, pv = t.load_kw.to_numpy(float), t.pv_kw.to_numpy(float)
    price, co2 = t.price_eur_kwh.to_numpy(float), t.co2_kg_kwh.to_numpy(float)
    one = pd.Timedelta(hours=1)
    rows, prev = [], None
    for i, ts in enumerate(stamps):
        seguido = prev is not None and ts - prev == one
        if not seguido:
            cand.new_block()
        obs = Obs(ts.hour, ts.dayofweek, 3000.0, price[i:i + 3], co2[i:i + 3],
                  load[i - 1] if seguido else float("nan"), pv[i - 1] if seguido else float("nan"), ts)
        cand.update(obs, {})
        cand.z = 0.0
        l0, p0 = cand.forecast_tables([ts])
        cand.z = 1.0
        p1 = cand.forecast_tables([ts])[1]
        rows.append((ts, load[i] - pv[i], float(l0[0] - p0[0]), float(p1[0] - p0[0]), seguido, load[i], cand.meter_down))
        prev = ts
    return pd.DataFrame(rows, columns=["timestamp", "net", "net_hat", "margin", "seguido", "load", "meter_down"])


def fit_scen(table, tables: dict, alphas=SCEN_ALPHAS) -> dict:
    """Cuantiles del error de la previsión del consumo neto de la hora actual, en unidades del margen del
    previsor (1 = cuantiles 16 % y 84 %). Solo horas con lectura anterior, contador vivo y margen > 0 (de 0 a
    5 h el contador está congelado: margen 0 y error 0)."""
    r = replay_errors(table, tables)
    ok = r.seguido & (r.load > 0) & ~r.meter_down & (r.margin > 1e-6) & np.isfinite(r.net) & np.isfinite(r.net_hat)
    u = ((r.net - r.net_hat) / r.margin)[ok].to_numpy(float)
    return {"alphas": [float(a) for a in alphas], "u": [float(v) for v in np.quantile(u, alphas)], "n": int(len(u))}


SCEN_FIT_CACHE = {}


def scen_tables(solar_prior: dict, exclude, alphas=SCEN_ALPHAS) -> dict:
    """Tabla de escenarios ajustada SIN las horas de `exclude` (con las mismas tablas de previsión del agente)."""
    import p1_hard as bench
    key = (len(exclude) if exclude else 0, min(exclude) if exclude else None, tuple(alphas))
    if key not in SCEN_FIT_CACHE:
        table = bench.hard_table()
        if exclude:
            table = table[~table.timestamp.isin(exclude)]
        SCEN_FIT_CACHE[key] = fit_scen(table, solar_prior["cand"], alphas)
    return SCEN_FIT_CACHE[key]


def make(prior: dict, solar_prior: dict, exclude: set, alphas=SCEN_ALPHAS, scen: Optional[dict] = None, **cfg):
    """Fábrica para el banco. cfg: atributos de PlanPolicy (scen_all_hours, scen_charge, ...)."""
    import p1_hard as bench
    agent = bench.hard_agent(prior, solar_prior)      # política actual con las tablas ajustadas sin el split
    pol = agent.policy
    pol.__class__ = PlanPolicy                        # mismas tablas y estado, con el plan del candidato
    if isinstance(pol.netload, SolarCand):
        pol.netload.__class__ = PlanSolar
        pol.netload.set_scenarios(scen if scen is not None else scen_tables(solar_prior, exclude, alphas))
    for k, v in cfg.items():
        setattr(pol, k, v)
    return agent
