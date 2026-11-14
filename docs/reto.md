# Reto UPC Sostenible: especificación y lista de verificación

Owner: integrador. Aquí está lo que sabemos con seguridad y lo que hay que **comprobar en `starter_kit/environment.py`**.
Cuando algo se verifique, se cambia en el código (dónde se indica) y se marca aquí con ✅.

## Lo confirmado

| Tema | Valor | Fuente |
|---|---|---|
| Interfaz | `class BatteryAgent` con `__init__()` y `act(obs: dict) -> float` | plantilla `agent.py` ✅ |
| Acción | kW: > 0 carga desde la red interna (hasta +500), < 0 descarga al campus (hasta −500) | plantilla ✅ |
| Claves de `obs` | `timestamp`, `hour`, `day_of_week` (0 = lunes), `soc_kwh`, `soc_pct`, `preu_actual` (€/kWh), `co2_actual` (kg/kWh), `preus_properes_24h`, `co2_properes_24h`, `noves_dades_5min` | plantilla ✅ |
| Batería | 2.000 kWh, ±500 kW, η = √0,9 ≈ 0,9487 por sentido, carga inicial de 1.000 kWh, sin reinicios ni degradación | web + clamp de la plantilla ✅ |
| Clamp | carga ≤ min(500, (2000 − soc)/η); descarga ≤ min(500, soc·η) | plantilla ✅ |
| Test | 12 semanas = 2.016 h, la última semana de cada mes de un año. Train = las primeras ~3 semanas de cada mes | web |
| Envío | ZIP ≤ 25 MB con `agent.py` y los .pkl en la raíz, 60 s para toda la simulación, 10 envíos al día | web |
| Librerías | numpy, pandas, scipy, sklearn, joblib, xgboost, lightgbm, math, datetime, collections, itertools, random, json, pathlib, typing | web |
| Leaderboard | 50 % público y 50 % privado. El jurado decide de forma decisiva | web |

## Por VERIFICAR con `environment.py`

| # | Pregunta | Suposición actual | Dónde se cambia | Estado |
|---|---|---|---|---|
| 1 | ¿La penalización por infracción es 0,20 o 1,00? | 0,20 | `params.W_INFRACTION` | ⏳ |
| 2 | ¿El excedente se paga a 0 o a 0,04 €/kWh? ¿Ahorra CO₂? | 0 € y sin CO₂ | `params.EXPORT_PRICE_EUR_KWH`, `sim.py` | ⏳ |
| 3 | ¿`preus_properes_24h[0]` es t+1 o t? ¿Siempre trae 24 valores, también al final del test? | t+1, 24 valores | `adapter.FORECAST_STARTS_NEXT_HOUR` | ⏳ |
| 4 | ¿Qué tipo y qué columnas tiene `noves_dades_5min`? ¿Cuántas filas? ¿Unidades? ¿Trae meteo? | DataFrame con demanda y solar en kW | `adapter.recent_load_pv` | ⏳ |
| 5 | ¿Demanda = −contador? ¿La solar es la suma de los 3 inversores? ¿Están en kW o en kWh por intervalo? | sí / sí / kW | `data.build_hourly`, `adapter` | ⏳ |
| 6 | Acción inválida: ¿se cuenta y se recorta, o se cuenta y se anula? | se cuenta y se recorta | `sim.py` | ⏳ |
| 7 | ¿El score usa el ahorro respecto a "sin batería"? ¿Cuenta la carga final? | sí / no cuenta | `sim.score`, `policy.terminal_value` | ⏳ |
| 8 | ¿Cómo se pasa de una semana de test a la siguiente? ¿Qué trae `noves_dades_5min` en la primera hora de cada semana? | continuo, sin reinicio | `sim.py`, `forecaster` | ⏳ |
| 9 | ¿Se puede leer un .pkl o .json junto a `agent.py` con `Path(__file__).parent`? ¿En qué directorio de trabajo corre? | sí | `policy.find_models_dir` | ⏳ |
| 10 | ¿Qué versión de Python y de las librerías usa el servidor? | ≥ 3.9 | `requirements.txt` | ⏳ |
| 11 | ¿Los 60 s incluyen el `__init__` del agente (cargar modelos)? | sí | `eval.py` (ya lo suma) | ⏳ |

## Fórmulas que usamos

```text
red_t      = demanda_t − solar_t + acción_t                    (acción > 0 carga)
compra_t   = max(red_t, 0)        venta_t = max(−red_t, 0)
CO2        = Σ compra_t · co2_t   (kg)
Coste      = Σ compra_t · precio_t − Σ venta_t · precio_venta  (€)
ΔCO2%      = 100 · (CO2_sin_batería − CO2) / CO2_sin_batería    (ΔCoste% igual)
Score      = max(0, 0,70·ΔCO2% + 0,30·ΔCoste% − pen·infracciones)
carga_t+1  = carga_t + η·acción   si acción > 0
           = carga_t + acción/η   si acción < 0
```

Peso de una hora para el LP: `w_t = 0,70·co2_t/co2_ref + 0,30·precio_t/coste_ref`, donde las referencias son la
media horaria sin batería del train (`models/objective_refs.json`). Mover 1 kWh de la hora A a la B solo compensa
si `0,9·w_B > w_A`.
