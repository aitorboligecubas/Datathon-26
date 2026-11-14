"""Constantes del reto y parámetros físicos de la batería.

Owner: INTEGRADOR. Fichero compartido: se cambia solo por PR, avisando al equipo.

Valores verificados con oficial/starter_kit/environment.py y battery_spec.json.
"""
import math
from typing import NamedTuple, Optional

# --- Episodio ---------------------------------------------------------------------
N_STEPS = 2016            # 12 semanas de test (última semana de cada mes) x 168 h
FORECAST_HOURS = 24       # valores de precio y CO2 que da el entorno, desde la hora actual (t..t+23)

# --- Tiempo de ejecución -------------------------------------------------------------
TIME_LIMIT_S = 60.0       # límite oficial para toda la simulación
TIME_BUDGET_S = 40.0      # nuestro límite interno (margen si su máquina es más lenta)

# --- Score: max(0, 0,70·ΔCO2% + 0,30·ΔCoste% − W_INFRACTION·infracciones) -------------
W_CO2 = 0.70
W_COST = 0.30
W_INFRACTION = 0.20       # environment.py: 0,20 por infracción; ENUNCIAT.md dice 1,00. Objetivo: 0 infracciones

# --- Mercado ---------------------------------------------------------------------------
EXPORT_PRICE_EUR_KWH = 0.0   # verificado: environment.py y ENUNCIAT.md -> el excedente no se paga


class BatteryParams(NamedTuple):
    """Física de la batería. Potencias en kW; con pasos de 1 h, kW = kWh por paso."""

    capacity_kwh: float = 2000.0
    soc_init_kwh: float = 1000.0              # sin reinicios entre semanas
    max_charge_kw: Optional[float] = 500.0
    max_discharge_kw: Optional[float] = 500.0
    eta_charge: float = math.sqrt(0.9)        # rendimiento de ida y vuelta 90 %
    eta_discharge: float = math.sqrt(0.9)
    export_price_eur_kwh: float = EXPORT_PRICE_EUR_KWH


DEFAULT_PARAMS = BatteryParams()
