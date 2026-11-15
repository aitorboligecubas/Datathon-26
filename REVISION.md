# Revisión de la versión FINAL del modo difícil (domingo 15/11, 11:25–11:40 hora local)

Cuatro revisores independientes en paralelo, 8 minutos cada uno, sobre la rama `final` (código del commit `98b7037`).
Solo lectura: no se ha cambiado nada del código. Además, la medida de las 12 claves de `revision-base`.

## Veredicto

**Ningún error que afecte al test anunciado.** Con el formato de observación del modo difícil y las fechas del reto:
0 infracciones, 0 excepciones, 0 respaldos y 7,9 s de los 60 permitidos. No hay nada que arreglar antes del cierre.

## Medida con el criterio de las 12 claves (`scripts/p1_lab/mejora_privado.py` de `revision-base`)

| Frente a la v10 | Meses mar–ago: media / peor / gana / pierde | Meses sep–feb: media / peor / gana / pierde | Infr. |
|---|---|---|---|
| **FINAL** (v14 de `p1-optimizador`) | +0,214 / +0,069 / 12 / 0 | +0,095 / −0,157 / 9 / 2 | 0 |
| v12 de `p1-optimizador` (`9b75248`) | +0,124 / +0,053 / 12 / 0 | +0,073 / −0,001 / 11 / 0 | 0 |

Las dos cumplen el criterio (mar–ago: media ≥ +0,02, pierde en 2 como mucho, peor ≥ −0,03; sep–feb: media ≥ −0,01).
La FINAL gana más de media; la v12 es más regular (no pierde en ninguna clave). La FINAL pierde 0,157 en los meses de
invierno del episodio `ep7`, uno de los dos con el calendario del test.

## Riesgos encontrados (ninguno se dispara con el test anunciado)

| # | Gravedad | Dónde | Qué pasa | Cuándo se dispara | Arreglo propuesto (no aplicado) |
|---|---|---|---|---|---|
| 1 | Crítico si se da | `hard.py:418-426` (`read_battery`) | Si la observación no trae `cap_max_kwh` y `power_max_kw`, el agente supone 6.000 kWh y 1.500 kW. Con una batería de 2.000/500: 283–341 infracciones en 500 horas | Solo si se evalúa con una batería menor y sin esas claves (el entorno del modo estándar no las envía). Con las claves: 0 infracciones con 2.000/500, 6.000/1.500 y 10.000/3.000 | Deducir la capacidad de `soc_kwh / soc_pct` y la potencia como capacidad / 4 |
| 2 | Medio | `hard.py:44`, `safety.py:14` | Con la carga redondeada a 2 decimales: 14 infracciones en 500 horas | Solo si el servidor redondea `soc_kwh` (el oficial no lo hace) | `ACTION_MARGIN_KW = 0.01` |
| 3 | Medio | `hard.py:32` (`LAST_MONTHS`), festivos de `hard_market.py:30` y `hard_solar.py:47` | El vaciado final y los festivos son fechas de 2025-26 | Con datos de otro año: la batería acaba medio llena y los festivos cuentan como laborables. No falla | Documentarlo; no hay arreglo general sin riesgo |
| 4 | Medio | `hard_solar.py:470-485`, `load_lo` | De 23 a 5 h se descarga justo hasta la última lectura, sin margen, porque en el train el contador está congelado | Si en otros datos el contador sí se lee de noche: se vertería energía la mitad de las noches | Confiar en la lectura congelada solo si coincide con la anterior |
| 5 | Medio | `hard_market.py:50-52` | Del 25 al 31 de agosto de 2026 el perfil se mezcla con el de septiembre de 2025 (once meses antes): el precio de agosto empeora un 10–19 %, el CO₂ mejora | Siempre, en la última semana del test. Efecto neto no claro | Peso 0 para agosto |
| 6 | Medio | `hard.py:277-294` | Con fecha vacía o ilegible, el agente vacía la batería y no vuelve a cargar | Solo si la fecha no llega | `ends = len(obs.price) < KNOWN_HOURS` en esa rama |
| 7 | Menor | `hard_solar.py:415-419` | En los dos cambios de hora (26/10 y 29/03, dentro del test) se pierde la memoria del día si la hora llega repetida o falta | Unas horas con previsión solo de perfil | Aceptar saltos de 0 y 2 horas esos dos días |
| 8 | Menor | `hard_solar.py:409-419` | `meter_down` se borra en un salto de fechas | Una hora con el contador caído justo al empezar una semana | Reasignarlo después de `new_block()` |
| 9 | Menor | `adapter.py`, `hard.py:428-453` | Sin `soc_kwh`, o sin la lista de precios, el agente se queda parado o descarga sin avisar | Formatos improbables | Reconstruir desde `soc_pct`; no tratar una lista ausente como fin de datos |

## Comprobado y correcto

- **Calendario:** saltos entre semanas (30/09 → 25/10, 31/01 → 22/02, 28/02 → 25/03), corte el 31/08/2026 y vaciado final (acaba con 164 kWh).
- **Reinicios:** detecta si el servidor reinicia la batería cada semana y si la prueba rápida va seguida del test.
- **Previsor de consumo y solar:** índices de la memoria, cambio de día, hora solar e interpolación entre meses, correctos. Con un 31 % de lecturas corruptas: 0 excepciones.
- **Previsor de precio y CO₂:** el ajuste y la ejecución usan exactamente el mismo perfil (diferencia 0 en 8.760 horas); la semilla está alineada. **La interpolación entre meses no tiene ningún fallo** y, en el caso más parecido al test (ajustar sin los días 15–24 y evaluar en 20–24), baja el error del precio de 0,147 a 0,134 y el del CO₂ de 0,168 a 0,141. La ganancia depende mucho del mes.
- **Seguridad:** 1,8 millones de pruebas del recorte de la acción contra la física: 0 infracciones. La ruta de respaldo es segura.
- **Empaquetado:** solo librerías permitidas, ninguna llamada vetada, compatible con Python 3.9 (comprobado por análisis del código, no ejecutando 3.9), funciona sin los `.json`.

## Qué no se ha hecho

- No se ha aplicado ningún arreglo: a 20 minutos del cierre, un cambio sin pasar el banco entero es más riesgo que beneficio.
- No se ha probado con Python 3.9 real ni con datos reales de los días del cambio de hora (no están en el train).
