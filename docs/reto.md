# Reto UPC Sostenible: especificación verificada

Owner: integrador. Resumen de lo que dicen los documentos oficiales (`oficial/docs/ENUNCIAT.md`,
`oficial/docs/GUIA_VARIABLES.md`, `oficial/starter_kit/environment.py`, `agent.py`, `check_submission.py`,
`battery_spec.json` y `tutorial.ipynb`) y de lo que sigue abierto.

## Confirmado ✅

| Tema | Valor | Fuente |
|---|---|---|
| Interfaz | `class BatteryAgent` con `__init__()` sin argumentos y `act(obs: dict) -> float` | agent.py, ENUNCIAT |
| Acción | kW: > 0 carga (hasta +500), < 0 descarga (hasta −500) | ENUNCIAT |
| `obs["preus_properes_24h"]` | `df[t : t+24]`: **empieza en la hora actual** (`[0] == preu_actual`) y al final de los datos trae menos de 24 | environment.py |
| `obs["noves_dades_5min"]` | `{"ultim_consum_kw": demanda de t−1, "ultima_solar_kw": solar de t−1}`; en t = 0 da los valores de t | environment.py |
| Otras claves | `timestamp` (pd.Timestamp; en check_submission es str), `hour`, `day_of_week` (0 = lunes), `soc_kwh`, `soc_pct`, `soc_percent`, `preu_actual` (€/kWh), `co2_actual` (kg/kWh) | environment.py |
| Batería | 2.000 kWh, ±500 kW, η = 0,9 ida y vuelta (√0,9 por sentido), carga inicial del 50 % (1.000 kWh), carga permitida entre 0 y 2.000 kWh, Δt = 1 h, sin degradación | battery_spec.json |
| Física | carga: soc += P·√0,9; descarga: soc += P/√0,9; la acción se recorta a ±500 y a la capacidad | environment.py |
| Infracciones | +1 si se recorta la potencia, +1 si se recorta por capacidad (puede haber 2 en una hora) | environment.py |
| Excedente | No se paga (`export_price = 0`) y no ahorra CO₂ | environment.py, ENUNCIAT |
| Referencia | Sin batería: compra = max(demanda − solar, 0) | environment.py |
| Score | `max(0, 100·(0,7·ΔCO₂ + 0,3·ΔCoste − 0,002·infracciones))`, es decir, **0,20 puntos por infracción** | environment.py |
| Test | 12 semanas = los últimos 7 días de cada mes de sep 2025 a ago 2026 (2.016 h). El train es el resto | ENUNCIAT |
| Envío | `submission.zip` (o solo `agent.py`) ≤ 25 MB, 60 s por simulación, 10 envíos/día (los fallidos no cuentan), PIN de equipo en el primer envío | ENUNCIAT |
| Librerías | numpy, pandas, scipy, scikit-learn, joblib, xgboost, lightgbm, math, random, datetime, collections, itertools, json, pathlib, typing, dataclasses (+ functools, heapq, bisect, re, copy, pickle) | ENUNCIAT |
| Vetado (AST) | os, sys, subprocess, importlib, inspect, socket, threading…; llamadas `.stack()`, `.system()`, `.popen()`, `.rmtree()`…; `eval`, `exec`, `compile`, `globals`, `locals`, `vars`, `__import__` | check_submission.py |
| Artefactos | Se cargan con `Path(__file__).parent / "fichero"` | ENUNCIAT, check_submission.py |
| Tabla horaria | demanda = −`Contador - POTENCIA ACTIVA EXPORTADA (kW)` (recortada a 0..5000); solar = suma de las `Inversor i - POTENCIA ACTIVA (kW)`; medias horarias; `dropna()` | tutorial.ipynb, GUIA_VARIABLES |

Nuestro `src/battery/sim.py` reproduce `environment.py` exactamente: `python scripts/calibrate_sim.py` da el mismo
score, CO₂, coste e infracciones con la plantilla oficial y con nuestro MPC.

## Contradicciones y dudas abiertas

| # | Duda | Qué hacemos |
|---|---|---|
| 1 | Penalización: `environment.py` resta 0,20 por infracción y el ENUNCIAT, 1,00 | Da igual: nuestro objetivo es 0 infracciones (clamp con margen de 1e-4) |
| 2 | ¿El servidor ejecuta las 12 semanas seguidas en un solo episodio o cada semana por separado con la carga reiniciada al 50 %? `evaluate_results` admite una máscara, lo que sugiere un episodio continuo con máscaras público/privado | Validamos con las 12 semanas seguidas. Si fuese por semanas, el valor de la carga final de cada semana cambiaría (P1) |
| 3 | En la primera hora de cada semana de test, ¿`noves_dades_5min` trae la última hora de la semana anterior (un mes antes)? | La previsión es robusta a eso. Irrelevante en la práctica (ver abajo) |
| 4 | ¿Qué versiones de Python y de las librerías usa el servidor? | El código es compatible con Python ≥ 3.9. Evitar APIs muy nuevas |

## Lo que dicen los datos (train oficial)

- 5.993 horas útiles entre el 01/09/2025 y el 16/08/2026. **Falta noviembre de 2025 entero** y agosto se corta el 16.
  Hay 15 horas con consumo 0 (probablemente fallos de comunicación).
- Consumo: 1.123 kW de media (de 0 a 2.503). Solar: 26 kW de media y 144 kW como máximo. Precio: 0,138 €/kWh de media.
  CO₂: 0,085 kg/kWh de media (de 0,028 a 0,222).
- La red (demanda − solar) baja de 500 kW solo el 0,5 % de las horas y **nunca hay excedente**.
  Por eso la previsión de demanda y solar casi no cambia las decisiones.
- La batería son 2 MWh frente a 27 MWh de consumo diario (7 %). El score máximo posible es pequeño:
  en validación, el oracle con información perfecta saca **6,12**.

## Fórmulas que usamos

```text
red_t      = demanda_t − solar_t + acción_t                    (acción > 0 carga)
compra_t   = max(red_t, 0)
CO2        = Σ compra_t · co2_t   (kg)          Coste = Σ compra_t · precio_t   (€)
ΔCO2%      = 100 · (CO2_sin_batería − CO2) / CO2_sin_batería    (ΔCoste% igual)
Score      = max(0, 0,70·ΔCO2% + 0,30·ΔCoste% − 0,20·infracciones)
```

Peso de una hora para el LP: `w_t = 0,70·co2_t/co2_ref + 0,30·precio_t/coste_ref`, donde las referencias son la media
horaria sin batería del train (`models/objective_refs.json`: 93,2 kg/h y 156,3 €/h). Mover 1 kWh de la hora A a la B
solo compensa si `0,9·w_B > w_A`. Como el score es lineal en las compras, el LP con información perfecta (`oracle`)
es el **óptimo exacto** del score: nada puede superarlo con los mismos datos.
