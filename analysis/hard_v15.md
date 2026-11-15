# Modo difícil, v15: la v14 con un detector de la hora de la irradiancia (P2, domingo 15/11)

ZIP listo para subir: `entrega/SanHackobos_hard_v15.zip` (el mismo que genera `python scripts/build_submission.py --hard`).

## Qué cambia respecto a la v14

Una sola cosa, en `src/battery/hard_solar.py`. La organización dice que la meteo de `noves_dades_5min` es "de la hora
anterior". El agente ahora lo comprueba sobre la marcha: compara la irradiancia de cada observación con la solar que
llega en esa misma observación y con la que llega en la siguiente.

- **Si la irradiancia es de la hora anterior (lo documentado): no cambia nada.** Decide exactamente igual que la v14:
  diferencia máxima de acción 0,0 en las 5.993 horas del histórico.
- **Si la irradiancia fuese de la hora actual:** la solar de esta hora se conoce casi exacta (error de 43 kW, frente
  a 142 kW con la previsión) y el agente la usa en la hora que decide, con un margen más estrecho.

## Por qué

Los líderes nos sacan 0,22 puntos y toda la ventaja es de coste (+0,66 puntos de coste con el mismo CO₂). En nuestro
banco, lo único que da coste sin dar CO₂ es conocer mejor el consumo neto de la hora actual: se descarga más ajustado
en las horas caras y se vierte menos. Si el servidor diese la irradiancia de la hora actual, un equipo que lo hubiera
notado tendría justo esa firma. No sabemos si es así: por eso el cambio es una opción gratis y no una apuesta.

## Medidas (banco del modo difícil)

| Mundo | Ventana | v14 | v15 |
|---|---|---|---|
| Meteo de la hora anterior (documentado) | días 8–14 | 20,302 | 20,302 (idéntica) |
| Meteo de la hora actual (hipótesis) | días 8–14 | 20,302 | **20,373** (+0,07; coste +0,16, CO₂ +0,03) |
| Meteo de la hora actual (hipótesis) | validación, modelos del ZIP | coste 179.359 €, vertido 3.087 kWh | coste 179.005 € (−354 €), vertido 1.725 kWh |

Techo si la solar de la hora actual se conociese exacta: 20,398 (+0,10). Lo que queda hasta el +0,43 de "hora actual
exacta" es el consumo, no la solar.

Reproducir: `python scripts/p1_hard.py --split dev --only "agente actual"` y lo mismo con `HARD_METEO_NOW=1` delante.

## Comprobaciones

- 44 tests en verde (uno nuevo del detector).
- `build_submission.py --hard`: prueba aislada con y sin ficheros auxiliares, mismas acciones que `src/`;
  `check_submission.py` oficial: VÁLIDA.
- Ataque de formato del equipo (72 casos): idéntico a la v14 en score, infracciones y excepciones.
- Simulador oficial frente al banco: coinciden (18,98, 0 infracciones).
- Ataque propio: irradiancia con basura, ruido, ausente o en otra unidad, en los dos mundos, con el `agent.py`
  empaquetado: 0 infracciones, 0 excepciones, 0 acciones no finitas.

## Cómo leer el resultado en la web

- **Si saca 24,06 (lo mismo que la v14):** la meteo es de la hora anterior. No se ha perdido nada y la selección para
  el jurado no cambia (v14 y v10).
- **Si saca más que la v14, sobre todo en coste:** la meteo es de la hora actual. Seleccionar la v15 en lugar de la v14.

## Otro hallazgo de datos (no cambia el agente)

La lectura del contador ya lleva descontada la solar real: en las horas de sol, cada kW más de solar baja la lectura
1 kW (pendiente −1,0 a mediodía; −1,12 en diferencias horarias, correlación −0,46). El "consumo" del dataset es el
consumo menos la solar, así que en el modo difícil el consumo neto es consumo real − 13 × solar, no − 12. Los márgenes
del agente están calibrados sobre el consumo neto medido, así que no hay que corregir nada.

## Qué versión es la mejor: comprobación independiente (domingo, 11:05 h)

Las versiones enviadas, medidas con el calendario real del episodio (`scripts/p1_lab/hard_calendario_versiones.py`)
en tres ventanas que no se habían usado para decidir nada. 0 infracciones en todas.

| Ventana | v10 | v10b (margen 0,8) | v12 | v14 | v14 − v10 |
|---|---|---|---|---|---|
| Días 5–11 | 20,901 | 20,865 | 21,032 | **21,074** | +0,173 |
| Días 10–16 | 19,415 | 19,392 | 19,464 | **19,505** | +0,090 |
| Días 17–23 | 18,821 | 18,782 | 18,927 | **18,929** | +0,108 |

Con las seis ventanas de P1 (`docs/envios.md`), la v14 gana a la v10 en 9 de 9 (+0,13 de media) y la v12 gana a la
v10 en 9 de 9 (+0,10). La v14 gana o empata con la v12 en 8 de 9 (+0,03 de media): entre esas dos la diferencia es
pequeña. La v10b pierde frente a la v10 en las tres (−0,03), que es lo que salió en la web (−0,02).

En el público el orden es el contrario (v10 24,15; v12 24,11; v14 24,06), pero el público es la mitad de las horas de
cada semana y la organización ha dicho que cuenta el privado. La v15 decide igual que la v14 salvo que la irradiancia
sea de la hora actual.

**Conclusión: la mejor versión es la v14 (la v15 es la misma con una opción más). Para el jurado, la v14 (o la v15) y la
v10 como cobertura, con el nombre `SanHackobos`.**

## ¿Cuál aguanta mejor datos distintos? Prueba de generalización (domingo, 11:15 h)

`python scripts/p2_hard_generaliza.py <escenario>`. Los modelos se ajustan sin la ventana (últimas 168 h de cada mes) y
se evalúan en esa ventana deformada. 0 infracciones en las 18 simulaciones.

| Datos de evaluación | v10 | v12 | v14 | Óptimo | v14 / óptimo |
|---|---|---|---|---|---|
| Sin deformar | 20,785 | 20,917 | **21,073** | 22,404 | 94,1 % |
| Otro año (fechas +364 días: ni la memoria del train ni los festivos casan) | 20,765 | 20,903 | **21,042** | 22,404 | 93,9 % |
| Precio ×1,5 y CO₂ ×0,7 | 19,945 | 20,124 | **20,217** | 22,404 | 90,2 % |
| Solar a la mitad | 17,370 | 17,398 | **17,530** | 18,705 | 93,7 % |
| Consumo ×1,3 | 15,490 | 15,557 | **15,647** | 16,585 | 94,3 % |
| Todo a la vez | 13,288 | 13,317 | **13,320** | 14,741 | 90,4 % |

La v14 es la mejor en los seis escenarios y el orden v14 ≥ v12 ≥ v10 no cambia en ninguno. Las tres pierden lo mismo
cuando cambian los niveles de precio y CO₂ (unos 4 puntos del óptimo): es la parte aprendida del train. Con todo
deformado a la vez las tres casi empatan (13,29 a 13,32).
