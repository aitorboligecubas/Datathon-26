# Encargo "mercado": prever precio y CO2 más allá de las 3 horas conocidas (HARD MODE)

Autor: Claude (P1), sábado 14/11, 17:37 a 18:15. Ficheros: `scripts/p1_lab/hard_market_cand.py` (candidato),
`scripts/p1_lab/hard_market_lab.py` (laboratorio), `results/p1_hard/mercado_lab.txt` (tabla completa),
`results/p1_hard/mercado_dev.csv` (banco oficial).

## 1. Resultado

Banco oficial, dev, misma ejecución (`python scripts/p1_hard.py --split dev --market scripts/p1_lab/hard_market_cand.py:make`):

| Agente | Score dev | Vertido kWh | ms/paso |
|---|---|---|---|
| agente actual (v3, con festivos) | 19,719 | 5.775 | 2,8 |
| **CANDIDATO** | **19,922 (+0,203)** | 5.561 | 2,6 a 2,9 |
| precio y CO2 reales a 24 h (techo) | 20,492 | 5.616 | 2,4 |

- Recupera el 26 % del hueco de previsión en dev (0,203 de 0,773). 0 infracciones. Ajuste: 0,1 s. JSON: +72 KB.
- **Lectura honesta: la mejora es pequeña y poco segura.** En otras tres ventanas de diseño (días 1-7, 3-9 y 5-11
  de cada mes) gana +0,02, +0,01 y +0,01. No pierde en ninguna, pero fuera de dev son centésimas. Media de las
  cuatro ventanas: +0,06. En el test, esperad entre 0,0 y +0,2.
- El error de previsión casi no cambia: 18,13 % -> 18,07 % del peso medio (a 9-23 h: 19,44 -> 19,42). Lo que cambia
  son unas pocas decisiones. Mi lectura: el techo de 0,77 es casi todo ruido que no se puede prever con lo que da
  el entorno (el nivel del día siguiente depende del viento y del sol de toda España). Ver la tabla de R2 de abajo.
- No he ejecutado el split val. **Aviso para el equipo:** dev y val no son del todo independientes. Los datos de
  agosto acaban el día 16, así que su semana de validación es del 9 al 16 y comparte 121 horas con dev (8 al 14).
  De mis ventanas, la de los días 1-7 no comparte ninguna; la de 3-9, una hora; la de 5-11, 49 horas.

## 2. Qué hace el candidato

Lo mismo que el agente actual (perfil por mes, tipo de día y hora + regresión lineal por antelación de la desviación
z = log(real / perfil)), con cuatro cambios:

1. **Memoria del train ("semilla").** El test de cada mes empieza justo donde acaba el train (train: días 1 a 23/24;
   test: los 7 últimos). "Ayer" y "las últimas 24 h" de la primera hora de cada semana están en el train. Se guardan
   los últimos 7 días de cada mes (12 tramos de 168 h) y la semana ya no arranca a ciegas.
2. **El nivel del día.** El precio de un día entero se fija de una vez (mercado diario). Dos pistas nuevas: la media
   de z del día en curso (hasta la última hora conocida) y la del día anterior entero.
3. **Más memoria.** Ayer a la hora de la última conocida (mide el salto de ayer a hoy a la misma hora) y anteayer a
   la hora objetivo.
4. **La otra variable.** El precio ayuda a prever el CO2 y al revés: última hora conocida, media de 24 h y ayer a
   la hora objetivo.

Total: 13 pistas y una regresión común por antelación (21 antelaciones x 2 variables x 14 coeficientes), ajustada por
mínimos cuadrados con 3.792 filas por antelación en el banco de dev y 6.168 con todo el train. No hay constantes
numéricas afinadas (los 7 días de semilla son margen: las pistas miran 48 h atrás). Lo que sí se eligió mirando
las cuatro ventanas es qué pistas entran (tabla de la sección 3).
Si falta alguna pista (semana sin memoria del train), decide **exactamente** como el agente actual.

**Por qué el techo está tan lejos.** Cuánto de la desviación z explica la regresión fuera de muestra (R2; ajuste en
la mitad de los meses, prueba en la otra mitad; solo train sin dev):

| Antelación | 4 h | 8 h | 12 h | 18 h | 23 h |
|---|---|---|---|---|---|
| Precio | 0,49 | 0,09 | 0,06 | 0,00 | -0,01 |
| CO2 | 0,79 | 0,46 | 0,33 | 0,27 | 0,23 |

La desviación del precio deja de ser previsible a partir de unas 8 horas: más allá, lo mejor que se sabe es el
perfil. La del CO2 dura más.

## 3. Qué aporta cada pieza

Ganancia de score frente al agente actual, misma ejecución (18:03). "B" = las 6 pistas del agente actual + semilla.

| Variante | dev (8-14) | días 1-7 | días 3-9 | días 5-11 |
|---|---|---|---|---|
| techo: precio y CO2 reales a 24 h | +0,773 | +0,361 | +0,543 | +0,515 |
| B: solo la semilla | -0,011 | 0,000 | +0,004 | -0,010 |
| B + ayer a la hora de la última conocida (zyL) | +0,067 | -0,092 | -0,029 | -0,056 |
| B + anteayer a la hora objetivo (zy2) | -0,012 | +0,010 | +0,033 | -0,011 |
| B + nivel del día (zd, zyd) | +0,047 | +0,025 | +0,014 | -0,051 |
| B + la otra variable (o2, om24, oy) | +0,025 | -0,017 | -0,009 | -0,003 |
| B + una regresión por hora del día | -0,002 | -0,015 | -0,031 | -0,055 |
| **FINAL (todo junto, regresión común)** | **+0,203** | **+0,022** | **+0,014** | **+0,013** |
| FINAL sin semilla | +0,124 | +0,022 | +0,008 | +0,024 |
| FINAL sin zyL | +0,152 | +0,027 | +0,007 | -0,017 |
| FINAL sin zy2 | +0,195 | +0,003 | +0,014 | +0,004 |
| FINAL sin nivel del día | +0,128 | -0,037 | +0,008 | +0,002 |
| FINAL sin la otra variable | +0,097 | -0,027 | -0,003 | -0,026 |
| FINAL + por hora del día | +0,133 | -0,008 | -0,010 | -0,044 |
| FINAL + corrección del sesgo del logaritmo | +0,209 | -0,005 | -0,009 | +0,001 |
| FINAL + perfil cruzado | +0,176 | -0,006 | -0,003 | -0,011 |

Cómo leerla:
- Ninguna pieza sola es fiable: sola, cada una gana en unas ventanas y pierde en otras. El ruido de una pieza es de
  unos +-0,05.
- El conjunto es lo único que no pierde en ninguna ventana. Quitarle el nivel del día o la otra variable lo empeora
  en las 4 ventanas. Quitarle zyL lo empeora en 3 (hasta -0,05). Quitarle zy2 casi no cambia nada (-0,02 como mucho).
- La semilla, dentro del conjunto: +0,08 en dev y entre -0,01 y +0,01 en las otras.
- En los días 1-7 no hay semilla (los días anteriores son del test): ahí la primera jornada es idéntica al agente actual.
- Las ventanas se solapan (son los días 1 a 14 de cada mes): no son cuatro pruebas independientes.
- La línea "techo" enseña cuánto se mueve el propio hueco de una ventana a otra: de 0,36 a 0,77.

## 4. Descartado, con el número

- **Solo la semilla** (-0,011 en dev). Sorpresa: saber lo de ayer no mejora la previsión del primer día con las pistas
  del agente actual. El error del primer día no baja (21,7 % -> 21,9 %). Con las pistas nuevas sí aporta (+0,08 en dev).
- **Una regresión por antelación y hora del día**, encogida hacia la común (probado con 3, 10, 30, 100 y 300):
  baja el error de previsión (18,07 -> 17,91) pero **pierde score** en las 4 ventanas (-0,07 en dev). Es el mejor
  ejemplo de que el error de previsión no es el score.
- **Perfil cruzado** (ajustar la regresión con desviaciones medidas contra un perfil que no ha visto ese bloque de
  días, como pasa en el test): -0,03 en dev y peor en las otras tres. Con solo 10 pistas llegó a -0,17 en los días 1-7.
- **Corregir el sesgo de volver del logaritmo** (estimador de Duan): quita el sesgo (-2,4 % -> -0,9 %) pero no da
  score (+0,006 en dev, -0,02 de media en las demás).
- **Encoger la regresión** con un lambda por antelación elegido por validación cruzada dentro del train (6 pliegues
  de unos 2 meses): elige lambdas pequeños (0 a 300) y da -0,01 en las cuatro ventanas (19,913 en dev). No hace falta.
- **Meteo local** (irradiancia, viento y temperatura de la hora anterior, como anomalía frente a su mes y hora): no
  explica nada del residuo. R2 fuera de muestra con y sin meteo: precio a 8 h 0,081 frente a 0,092; CO2 a 12 h
  0,333 frente a 0,332; CO2 a 23 h 0,208 frente a 0,226. El tiempo de Barcelona no dice cómo está la red de España.
  No llegó al banco.
- **Solo zyL** o **solo "por hora"**: pierden en 3 o 4 de las 4 ventanas.
- **Festivos**: ya los integró otro agente (v3) mientras trabajaba; el candidato usa la misma regla
  (`market_day_type`), así que se suma a ellos.

No probado (por tiempo o porque el banco no lo mide):
- Horizonte de más de 24 h: lo fija la política (`HardPolicy.horizon`), no el previsor.
- Prever en niveles en vez de en logaritmos; términos no lineales.
- **Puente a la semana siguiente.** En las últimas 23 h de cada semana, las horas del mes siguiente se prevén solo
  con el perfil. Con la semilla del mes siguiente se podría usar la misma regresión. El banco no lo puede medir: en
  dev las semanas acaban a mitad de mes y la política no salta de mes.

## 5. Riesgos

1. **La ganancia puede ser ruido.** +0,20 en dev, +0,01 a +0,02 en las otras ventanas. Dos semanas (diciembre y
   agosto) concentran el 85 % del hueco de dev. Hay que pasar la validación reservada antes de enviarlo.
2. **La semilla supone que el test empieza justo después del train de cada mes.** Si el servidor usa otras fechas
   u otra serie de precios, la memoria no casa. Protección parcial: la semilla va por fecha y hora exactas; si las
   fechas no casan, no se usa, y sin memoria el candidato decide como el agente actual. Si las fechas casan pero la
   serie es otra, el daño se limita a las primeras 48 h de cada semana.
3. **Línea base móvil.** El agente actual cambió tres veces durante el trabajo (19,59 -> 19,61 -> 19,64 -> 19,72 en
   dev). Todas las comparaciones de estas notas son dentro de una misma ejecución.
4. **Transiciones entre semanas**: el banco de dev no las reproduce (ver "puente").
5. **Cambio de hora** (26/10 y 29/03 caen en semanas del test): la memoria indexa por hora del reloj. Una hora
   repetida o ausente desplaza una posición ese día. Efecto pequeño; no probado.
6. Robustez comprobada: fecha None, 1 o 2 horas conocidas, NaN, precio 0 o negativo, listas, saltos de fecha,
   fecha lejana, última hora del mes y del test, tablas ausentes o rotas. Nunca lanza y devuelve siempre la
   longitud pedida, con valores finitos y >= 0.

## 6. Pasadas de dev gastadas

- 8 rondas del banco en dev (unas 90 simulaciones de variantes en total) y 5 tablas de error de previsión en dev.
- 6 rondas en los días 1-7 y 3 rondas en los días 3-9 y 5-11.
- 6 ejecuciones del banco oficial con el candidato final (todas 19,922; la última a las 18:12).
- La elección final no sale de un máximo en dev: es la única variante que no pierde en ninguna de las 4 ventanas.

## 7. Pasos para integrarlo

1. `src/battery/hard_market.py`: copiar de `scripts/p1_lab/hard_market_cand.py` el bloque "inferencia": las
   constantes (`NAMES`, `LEADS` (= `REG_LEADS`), `STORE_PAST_H`, `STORE_LEN_H`, `Z_CLIP`), las funciones `log_ratio`
   y `window_mean`, y la clase `MarketCand` entera. Añadir `import pandas as pd`. Ningún nombre choca con otro
   módulo de `src/battery/` (comprobado con grep). Solo usa numpy, pandas y math; no hay `.stack(`.
2. `src/battery/hard.py`, en `HardPolicy.__init__`: `self.market = MarketCand(prior)`.
3. `scripts/p1_hard.py`: copiar el bloque "ajuste" (`dense_market`, `day_types`, `profile_sums`, `profile_from`, `at`,
   `roll_mean`, `day_means`, `training_rows`, `ridge_by_hour`, `seed_segments`, `fit_cand`). En `fit_market`, antes
   del `return`: `out["cand"] = fit_cand(exclude)`. En `hard_agent`: `pol.market = MarketCand(prior, ...)`.
   El agente "mercado sin regresión (v1)" sigue igual: sin `"reg"` el candidato se apaga solo.
4. `python scripts/p1_hard.py --fit`: regenera `models/hard_market.json` con la clave nueva `"cand"`:
   `{"feats": [13 nombres], "full": {"price": [21][14], "co2": [21][14]}, "seed": [12 tramos de 168 h]}`.
   Atajo sin mover el ajuste: `from hard_market_cand import to_prior; prior["cand"] = to_prior(None)`.
5. Comprobar: `python scripts/p1_hard.py --split dev` (el "agente actual" tiene que dar lo que hoy da CANDIDATO),
   `python -m pytest -q` y `python scripts/build_submission.py --hard`.
6. Solo entonces, la validación reservada: `python scripts/p1_hard.py --split val`. Si no gana ahí, no se envía.
