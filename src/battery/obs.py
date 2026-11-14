"""Observación interna del equipo.

Owner: INTEGRADOR. Todo el código trabaja con `Obs`, nunca con el diccionario
oficial: si el formato oficial cambia, solo se toca adapter.py.

Convenciones (las mismas unidades que el entorno oficial):
- Potencias en kW (con pasos de 1 h, kW = kWh). Acción > 0 = cargar, < 0 = descargar.
- Precio en €/kWh. CO2 en kg CO2/kWh.
- `price[0]` y `co2[0]` son la hora ACTUAL; `[1:]` son las 23 h siguientes (24 valores en total,
  menos al final de los datos).
- `load_prev_kw` y `pv_prev_kw` son medias de la hora ANTERIOR (NaN si no se conocen).
"""
from typing import Any, NamedTuple

import numpy as np


class Obs(NamedTuple):
    hour: int              # 0..23, hora actual
    weekday: int           # 0 = lunes ... 6 = domingo
    soc_kwh: float         # carga actual de la batería
    price: np.ndarray      # €/kWh, hasta 24 valores desde la hora actual
    co2: np.ndarray        # kg CO2/kWh, hasta 24 valores desde la hora actual
    load_prev_kw: float    # demanda del campus en la hora anterior
    pv_prev_kw: float      # producción solar en la hora anterior
    timestamp: Any = None  # pd.Timestamp de la hora actual (da el mes: útil para la solar)

    @property
    def hour_of_week(self) -> int:
        """0..167, lunes 00h = 0."""
        return self.weekday * 24 + self.hour
