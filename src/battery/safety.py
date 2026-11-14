"""Límites físicos de la batería: ninguna acción sale del agente sin pasar por aquí.

Owner: P1 (optimizador). Objetivo: cero infracciones.

Clamp oficial (verificado con oficial/starter_kit/environment.py):
    |p| <= 500 kW
    cargando:    p <= (2000 - soc) / eta - 1e-4
    descargando: |p| <= soc · eta - 1e-4          con eta = sqrt(0,9)
"""
import math

from .params import DEFAULT_PARAMS, BatteryParams

SAFETY_MARGIN_KW = 1e-4


def feasible_range(soc_kwh: float, p: BatteryParams = DEFAULT_PARAMS) -> tuple:
    """Rango (lo, hi) de acciones válidas en kW con la carga actual."""
    hi = (p.capacity_kwh - soc_kwh) / p.eta_charge
    lo = -soc_kwh * p.eta_discharge
    if p.max_charge_kw is not None:
        hi = min(hi, p.max_charge_kw)
    if p.max_discharge_kw is not None:
        lo = max(lo, -p.max_discharge_kw)
    return lo, hi


def clip_action(action_kw: float, soc_kwh: float, p: BatteryParams = DEFAULT_PARAMS) -> float:
    """Recorta la acción al rango válido (con margen). NaN, inf o basura -> 0."""
    try:
        a = float(action_kw)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(a):
        return 0.0
    lo, hi = feasible_range(soc_kwh, p)
    lo = min(0.0, lo + SAFETY_MARGIN_KW)
    hi = max(0.0, hi - SAFETY_MARGIN_KW)
    return min(max(a, lo), hi)


def is_infraction(action_kw: float, soc_kwh: float, p: BatteryParams = DEFAULT_PARAMS,
                  tol: float = 1e-9) -> bool:
    """True si la acción pide cargar más de lo que cabe, descargar más de lo que queda
    o superar la potencia máxima."""
    a = float(action_kw)
    if not math.isfinite(a):
        return True
    lo, hi = feasible_range(soc_kwh, p)
    return a > hi + tol or a < lo - tol


def soc_after(soc_kwh: float, action_kw: float, p: BatteryParams = DEFAULT_PARAMS) -> float:
    """Carga tras aplicar una acción válida durante 1 h."""
    if action_kw >= 0:
        s = soc_kwh + action_kw * p.eta_charge
    else:
        s = soc_kwh + action_kw / p.eta_discharge
    return min(max(s, 0.0), p.capacity_kwh)
