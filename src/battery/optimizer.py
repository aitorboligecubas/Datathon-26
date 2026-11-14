"""Programación lineal para decidir carga y descarga en un horizonte de H horas.

Owner: P1 (optimizador).

Variables por hora k = 0..H-1 (todas >= 0):
    c_k   potencia de carga (lado red)       d_k   potencia de descarga (lado red)
    imp_k compra a la red                     exp_k venta a la red
    s_k   carga de la batería al FINAL de la hora k
Restricciones:
    imp_k - exp_k - c_k + d_k = demanda_k - solar_k            (balance)
    s_k = s_{k-1} + eta_c·c_k - d_k/eta_d,  s_{-1} = soc       (dinámica)
    0 <= s_k <= 2000,  c_k <= 500,  d_k <= 500
Objetivo (minimizar):
    sum_k (w_co2·co2_k + w_cost·precio_k)·imp_k - w_cost·precio_venta·exp_k - valor_final·s_{H-1}

Con w_co2 = 0,70/co2_ref y w_cost = 0,30/coste_ref el LP optimiza justo la parte
del score que depende de nosotros. Con eta_c·eta_d = 0,9, mover energía de la
hora A a la B solo compensa si w_B·0,9 > w_A: el LP ya aplica esa regla solo.
"""
import numpy as np
import scipy.sparse as sp
from scipy.optimize import linprog

from .params import DEFAULT_PARAMS, W_CO2, W_COST, BatteryParams

_LP_STRUCT_CACHE = {}


def score_weights(co2_ref: float, cost_ref: float) -> tuple:
    """Pesos del LP a partir de la media horaria de CO2 (kg) y coste (€) sin batería."""
    return W_CO2 / max(co2_ref, 1e-9), W_COST / max(cost_ref, 1e-9)


def _lp_structure(H: int, eta_c: float, eta_d: float):
    """Matriz de igualdades: solo depende de H y las eficiencias, así que se cachea."""
    key = (H, eta_c, eta_d)
    if key not in _LP_STRUCT_CACHE:
        eye = sp.identity(H, format="csr")
        zero = sp.csr_matrix((H, H))
        balance = sp.hstack([-eye, eye, eye, -eye, zero])
        shift = sp.diags([np.ones(H - 1)], [-1], shape=(H, H), format="csr")
        dynamics = sp.hstack([-eta_c * eye, (1.0 / eta_d) * eye, zero, zero, eye - shift])
        _LP_STRUCT_CACHE[key] = sp.vstack([balance, dynamics], format="csr")
    return _LP_STRUCT_CACHE[key]


def plan(soc_kwh: float, load_kw, pv_kw, price, co2, w_co2: float, w_cost: float,
         terminal_value: float = 0.0, p: BatteryParams = DEFAULT_PARAMS) -> np.ndarray:
    """Plan óptimo de acciones (kW, + carga) para las H horas del horizonte.

    Todas las series tienen longitud H y empiezan en la hora actual.
    `terminal_value`: valor (en unidades del objetivo) de cada kWh que quede en la
    batería al final del horizonte. Lanza RuntimeError si el LP no se resuelve.
    """
    load = np.asarray(load_kw, dtype=float)
    H = load.shape[0]
    net = load - np.asarray(pv_kw, dtype=float)
    price = np.asarray(price, dtype=float)
    co2 = np.asarray(co2, dtype=float)

    cost_s = np.zeros(H)
    cost_s[-1] = -terminal_value
    c = np.concatenate([
        np.zeros(2 * H),
        w_co2 * co2 + w_cost * price,
        np.full(H, -w_cost * p.export_price_eur_kwh),
        cost_s,
    ])
    b_dyn = np.zeros(H)
    b_dyn[0] = soc_kwh
    bounds = ([(0.0, p.max_charge_kw)] * H + [(0.0, p.max_discharge_kw)] * H
              + [(0.0, None)] * (2 * H) + [(0.0, p.capacity_kwh)] * H)
    res = linprog(c, A_eq=_lp_structure(H, float(p.eta_charge), float(p.eta_discharge)),
                  b_eq=np.concatenate([net, b_dyn]), bounds=bounds, method="highs")
    if res.status != 0:
        raise RuntimeError("LP sin solución: " + str(res.message))
    return res.x[:H] - res.x[H:2 * H]
