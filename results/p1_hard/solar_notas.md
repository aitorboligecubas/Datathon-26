# Encargo "solar": prever consumo y solar, y actuar con su incertidumbre (HARD MODE)

Autor: Claude (P1), sábado 14/11, 18:13 a 18:50. Ficheros: `scripts/p1_lab/hard_solar_cand.py` (candidato),
`scripts/p1_lab/hard_solar_lab.py` (laboratorio), `results/p1_hard/solar_lab.txt` (todas las tablas),
`results/p1_hard/solar_dev.csv` (banco oficial).

## 1. Resultado

Banco oficial, dev, misma ejecución
(`python scripts/p1_hard.py --split dev --solar scripts/p1_lab/hard_solar_cand.py:make --only "agente actual,CANDIDATO"`):

| Agente | Score dev | Vertido por descarga | Excedente solar perdido | ms/paso |
|---|---|---|---|---|
| agente de partida (v5/v6, "solar sencilla") | 19,922 | 2.674 kWh | 2.887 kWh | 2,5 a 3,0 |
| **CANDIDATO** | **20,073 (+0,151)** | 3.821 kWh | 2.417 kWh | 2,5 a 3,0 |
| precio y CO2 reales a 24 h (con la solar de partida) | 20,492 | 3.015 | 2.601 | 2,5 |
| óptimo con todo el futuro | 21,418 | 0 | 0 | |

- **Aviso: el banco cambió a las 18:46.** El integrador pasó el candidato a `src/battery/hard_solar.py` (v7)
  mientras yo terminaba. Desde entonces "agente actual" ya lleva el candidato y da 20,073, idéntico a
  CANDIDATO; el agente de partida sale como "solar sencilla (v6)" (19,922). Ver sección 7.
- Segunda ventana (días 1-7 de cada mes, ajustando sin ellos): 20,803 -> **20,977 (+0,174)**.
- Con precio y CO2 reales (aísla mi parte), dev: 20,492 -> 20,696 (+0,204).
- 0 infracciones. La previsión cuesta 0,06 ms por hora. El ajuste tarda 0,6 s. JSON: 88 KB.
- No he ejecutado el split val.
- El vertido por descarga sube porque los márgenes son más estrechos. Aun así gana: lo que deja de
  cubrirse en las horas caras costaba más que lo que se vierte.

**Lectura honesta del techo.** De los 1,35 puntos que separan al candidato del óptimo en dev:

| Tramo | Puntos | Cómo se mide |
|---|---|---|
| Previsión de precio y CO2 | 0,62 | candidato con mercado real: 20,696 |
| Consumo y solar de la HORA ACTUAL | 0,40 | + consumo y solar reales de esta hora: 21,094 |
| Consumo y solar de las 23 horas siguientes | 0,18 | + reales en las 24 h: 21,273 |
| Horizonte de 24 h y valor final | 0,15 | óptimo: 21,418 |

Los "1,10 puntos" del encargo eran sobre todo la hora actual. Y ahí el límite es la solar: de una hora a la
siguiente cambia 142 kW (error típico de día) y ninguna pista de las que da el entorno lo baja (sección 4).

## 2. Qué hace el candidato

Cada pieza se puede apagar con una opción de `make` (entre paréntesis).

1. **Consumo: regresión por hora del día y antelación** (`reg`). Tres pistas: el cociente consumo/perfil de la
   hora anterior, el de ayer a la hora que se prevé y el de ayer a la hora anterior. 24 x 24 celdas de 4
   coeficientes, por mínimos cuadrados (170 a 250 filas por celda). El primer día de cada semana, sin "ayer",
   usa solo la hora anterior. Error fuera de muestra (kW), receta actual -> regresión:

   | Antelación | dev (8-14) | días 1-7 |
   |---|---|---|
   | hora actual | 45,3 -> 37,9 | 45,8 -> 39,2 |
   | 1 h | 69,6 -> 53,9 | 68,4 -> 54,0 |
   | 3 h | 106,6 -> 78,4 | 102,0 -> 76,5 |

   Donde más baja: 21 h (42 -> 25), 9 h (68 -> 48) y 6 h (111 -> 94).
2. **Noche: el contador está congelado de 23 a 5 h** (`freeze`). En el train, el consumo de 0 a 5 h es idéntico
   al de las 23 h el 100 % de las noches (el 96 % a las 0 h), y el de las 23 h difiere 0,7 kW del de las 22 h.
   Desde las 23 h el consumo hasta las 6 h se conoce: es la última lectura. Margen cero en esas horas.
3. **Márgenes por cuantiles** (`quant`). Antes: 1 desviación típica fija por hora del día (mezcla de todos los
   meses). Ahora: cuantil 16 % del error del consumo (por hora, relativo al perfil) y cuantil 84 % del error
   de la solar (por tramo de claridad prevista, relativo al cielo despejado de la fecha), en cuadratura.
   Con cielo claro el margen solar es el 8 % del cielo despejado; con nubes, el 23 %. De 0 a 5 h, cero.
   A las 20 h pasa de 46 kW a unos 22 kW. El plan ve el mismo margen en todas las horas, también la actual.
4. **Tope de descarga** (`uncap`). La política recorta la descarga al consumo neto de la hora anterior. Si
   ese tope ha actuado, se descarga hasta el consumo neto previsto menos el margen. Con el contador a 0 no
   se toca. Medido: quitar el tope de la política da lo mismo (20,075 frente a 20,073).
5. **Solar: claridad con memoria** (`pvreg`). La claridad prevista usa la última hora con sol y la media del
   día, con un coeficiente por antelación ajustado (0,71 y 0,16 para la hora actual). Para mañana, la media
   de hoy por 0,23. Error: igual en la hora actual (143 -> 142 kW) y un 3-4 % menos a 2-4 horas.
6. **Cielo despejado en hora solar e interpolado entre meses** (`sky`). El test son los días 25-31 y el train
   los días 1-24: la curva del test está a medio camino de la del mes siguiente. Además, el cambio de hora
   (26/10 y 29/03) cae dentro de dos semanas del test y mueve la curva una hora: con la tabla actual, 9 días
   del test tendrían la solar desplazada. En dev no se nota (son días centrales); en los días 1-7, que
   también caen en un extremo, vale +0,04.

Constantes: ninguna afinada con dev. Las heredadas (30 kW, claridad máxima 1,5, cocientes 0,3-3, z = 1) son
las del agente actual. Las nuevas son estructurales: cuantiles 16/84 % (= 1 desviación típica), tramos de
claridad de 0,25 en 0,25, 16 antelaciones solares (horas de sol), 200 filas mínimas por coeficiente solar,
3 horas de sol para usar la media de hoy, 30,4 días por mes.

## 3. Qué aporta cada pieza

Dev y días 1-7, misma ejecución por columna. "Sola": sobre el candidato con todo apagado (19,926, que
reproduce al agente actual, 19,922). "Al quitarla": lo que pierde el candidato completo sin ella.

| Pieza | Sola (dev) | Al quitarla (dev) | Al quitarla (días 1-7) |
|---|---|---|---|
| `reg` regresión del consumo | +0,064 | -0,112 | -0,139 |
| `quant` márgenes por cuantiles | +0,037 | -0,060 | -0,051 |
| `reg` + `quant` juntas | +0,124 | | |
| `uncap` tope de descarga | +0,016 | -0,009 | -0,019 |
| `pvreg` claridad con memoria | +0,017 | -0,012 | +0,013 |
| `freeze` noche congelada | -0,001 | -0,008 | -0,019 |
| `sky` hora solar e interpolación | 0,000 | -0,003 | -0,042 |
| margen también en la hora actual del plan | | +0,003 | |
| **TODO** | **+0,147** | | |

Cómo leerla:
- Lo que gana son dos piezas que van juntas: prever mejor el consumo y medir el margen con el error real.
  Solas dan +0,06 y +0,04; juntas, +0,12. Las dos ganan en las dos ventanas.
- `uncap` y `freeze` suman poco, pero en las dos ventanas.
- `pvreg` es ruido en score (+0,012 y -0,013). La dejo porque baja el error a 2-4 horas en las dos ventanas
  y no tiene nada afinado. Quitarla no cambia el resultado.
- `sky` no se puede medir en dev. La prueba es la ventana de los días 1-7 y el calendario.

## 4. Descartado, con el número

- **Margen según lo que vale la hora** (`value_z`: z = F^-1(mu/w), con mu = séptima peor hora de las últimas
  24): -0,034 en dev y -0,033 en días 1-7. La idea es buena pero mu está mal medido así. Haría falta el
  precio sombra del LP (ver sección 8).
- **Margen distinto** (`z`): 0,6 -> -0,099 y -0,062; 1,4 -> +0,031 y +0,002; 1,8 -> +0,012 y -0,022. Plano
  entre 1,0 y 1,4. Me quedo con 1,0 (el heredado). Cuadra con la teoría: lo que no se descarga ahora se
  usa en una hora que vale un 85-90 % de esta, y eso da z entre 1 y 1,3.
- **Margen solar por antelación** (`room`, para dejar hueco antes del excedente): +0,011 en dev, -0,003 en
  días 1-7. Ruido.
- **Solar por hora del día** (una regresión por hora): 143 -> 144 kW. Peor.
- **Tendencia de la claridad** (última hora menos la anterior): 141,8 -> 142,3 kW. Nada.
- **Claridad de ayer** como pista de hoy, con sol ya visto: 141,8 -> 142,3 kW. Nada (sí se usa antes de amanecer).
- **Irradiancia y temperatura del panel**: la irradiancia es la solar medida (correlación 0,994). No añade.
  El viento vale 0 en todo el train.
- **Más pistas de consumo** (dos horas atrás): 37,9 -> 37,9 kW. Nada.
- No probado: semilla con las últimas horas del train (como en mercado). Solo afectaría a la primera hora y
  al primer día de cada semana.

## 5. Riesgos

1. **Márgenes más estrechos.** El vertido por descarga sube un 43 % en dev (2.674 -> 3.821 kWh). Si en el
   test el consumo es más raro que en el train (Navidad, Semana Santa), se verterá más. Salida fácil:
   `z = 1,4` baja el vertido a 2.107 kWh y no pierde en ninguna de las dos ventanas.
2. **Cambio de hora.** Supongo que las fechas del test son hora local, como las del train (el centro de la
   curva solar pasa de las 12,3 h en marzo a las 13,0 h en abril). No hay datos del train después del cambio
   para comprobarlo. El día del cambio falta o se repite una hora: el candidato borra su memoria y sigue.
3. **Contador congelado.** Regla del 100 % de las noches del train. Si una noche del test no se congela, el
   consumo previsto es la última lectura (razonable), pero el margen es cero.
4. **Primera hora de cada semana.** Sin lectura anterior: solo el perfil, con margen ancho (7-14 %).
5. **`uncap` depende de cómo recorta la política.** Detecta el tope porque la descarga es igual al consumo
   neto anterior. Si `hard.py` cambia ese tope, la pieza deja de actuar (sin daño).
6. **Línea base móvil.** `src/battery/hard.py` cambió mientras trabajaba (otro agente). Todas las
   comparaciones son dentro de una misma ejecución. El agente de partida dio 19,922 en todas menos una
   (19,923). Desde las 18:46 `hard_agent()` ya lleva el candidato dentro. Mi laboratorio le quita las tablas
   `cand` para que "base" siga siendo el agente de partida (repetido a las 18:48: base 19,922, cand 20,073).
7. **dev y val comparten 121 horas de agosto** (aviso del encargo de mercado). Los días 1-7 no comparten ninguna.
8. Robustez comprobada: 1.500 observaciones hostiles (fecha None o texto, NaN, contador a 0, lecturas
   negativas o absurdas, listas cortas, saltos de fecha): 0 excepciones, 0 infracciones, 0 respaldos.

## 6. Pasadas de dev gastadas

- 12 rondas en dev con variantes del candidato (39 simulaciones) y 2 de diagnóstico del agente de partida.
- 6 rondas en los días 1-7 (20 simulaciones).
- 3 tablas de error de previsión fuera de muestra (dev y días 1-7).
- 5 ejecuciones del banco oficial con el candidato: todas 20,073.
- Ninguna constante sale de un máximo en dev. Decisiones tomadas con las dos ventanas: mantener z = 1,
  descartar `room` y `value_z`, dejar `pvreg`.

## 7. Integración

**Estado a las 18:47: ya está hecha (v7), no por mí.** Lo que veo en el árbol de trabajo (sin commit todavía):
- `src/battery/hard_solar.py`: copia del bloque "inferencia" (clase `SolarCand`) y `make_netload()`, que usa
  las tablas de la clave `cand` de `models/hard_solar.json` y, si faltan, el previsor sencillo.
- `src/battery/hard.py`: `self.netload = make_netload(...)`.
- `scripts/p1_hard.py`: `fit_solar()` añade `cand = fit_prior(table)` importando **mi fichero**
  (`scripts/p1_lab/hard_solar_cand.py`). No borrarlo ni cambiar `fit_prior` sin mover antes el ajuste.
- `models/hard_solar.json`: regenerado a las 18:46.
- Comprobado en el banco (18:47, misma ejecución): solar sencilla (v6) 19,922 | agente actual 20,073 |
  CANDIDATO 20,073. La copia decide igual que el candidato.

Lo que queda por hacer o vigilar:
1. La copia de `src` lleva una regla propia para el contador caído (`meter_down and not pv_alive`). No es
   mía y no la he medido aparte; en dev da el mismo score.
2. Borrar de la copia las opciones descartadas (`room`, `value_z`, `discharge_z`, `VALUE_RANK`, `w_hist`) o
   dejarlas apagadas, como están.
3. Si se regenera el JSON a mano: `to_prior(None)` devuelve las tablas con todo el train (88 KB). Van en la
   clave `cand`. `pv_clear` y `pv_mean` de `cand` están en hora solar: no mezclarlas con las de fuera.
4. Pasar una sola vez `--split val`, `python -m pytest -q` y `python scripts/build_submission.py`.
5. Opcional: quitar `cap_discharge` en el modo difícil (da lo mismo que `uncap`: 20,075 frente a 20,073).

Si hubiera que repetirla desde cero: copiar el bloque "inferencia" del candidato (constantes, `last_sunday`,
`summer_time`, `campus_how`, `neighbour_month`, `SolarCand`), multiplicar `base.pv_prior` por 12 una sola vez
(`pv_factor`), guardar `to_prior(None)` en `models/` y construir el previsor con esas tablas. Solo usa numpy,
pandas, math y typing. No hay `.stack(`, `print`, `eval` ni `X | None`. Ningún nombre choca con otro módulo.

## 8. Lo que queda por ganar

- **El precio sombra del LP.** El margen ideal de cada hora es z = F^-1(mu/w): mu es lo que vale la energía
  que se queda en la batería. Lo tiene el LP (`res.eqlin.marginals` en `optimizer.plan`), pero el contrato no
  lo devuelve. Mi aproximación sin él pierde. Techo de esta vía: una parte de los 0,40 puntos de la hora actual.
- **Semilla del train** para la primera hora y el primer día de cada semana (centésimas).
- La solar de una hora a la siguiente no se puede prever mejor con lo que da el entorno. Con datos de 5
  minutos de verdad (los últimos 5 minutos, no la media de la hora) sí se podría.
