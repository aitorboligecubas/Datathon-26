# Rama `mejora-score-hard`: qué se probó para subir la nota del modo difícil (sábado 14/11 noche)

Punto de partida: v8 (`main` 77e0157 + banco de `p1-optimizador`). Todo medido con el banco del modo difícil,
ajustando SIN las horas de cada ventana. Banco paralelo: `python scripts/p1_lab/mejora_grid.py scripts/p1_lab/mejora_cands.py --windows val,1-7,8-14,15-21`.

## Resultado: v9 = v8 + semilla de consumo y solar al empezar cada semana

Cada semana del test (días 25-31) empieza justo donde acaba el train de su mes (días 1-24). Hasta ahora, la primera
hora de cada semana se planificaba a ciegas (la lectura del entorno es de hace un mes). La v9 guarda las últimas 48 h
de cada tramo del train (`models/hard_solar.json`, clave `"seed"`) y, al empezar una semana, se las pasa al previsor
de consumo y solar como si las hubiera visto. Cubre 10 de las 12 semanas (noviembre no tiene train; agosto acaba el 16).

Seguridad: la semilla solo da memoria al previsor; la decisión de la primera hora es la de siempre. En la segunda hora
se comprueba: con el contador congelado de 23 a 5 h, la lectura de las 00 h tiene que ser la de las 23 h anteriores
(la última de la semilla; pasa en el 100 % de las noches del train). Si no coincide, se olvida la semilla.

| Ventana | v8 | v9 | dif. |
|---|---|---|---|
| validación reservada | 20,831 | 20,838 | +0,007 |
| días 1-7 (sin train justo antes: no aplica) | 20,979 | 20,979 | 0,000 |
| días 3-9 | 20,877 | 20,889 | +0,012 |
| días 5-11 | 20,881 | 20,881 | +0,001 |
| días 8-14 | 20,104 | 20,120 | +0,016 |
| días 10-16 | 19,392 | 19,389 | -0,002 |
| días 12-18 | 18,880 | 18,887 | +0,007 |
| días 15-21 | 18,590 | 18,610 | +0,021 |
| días 16-22 | 18,541 | 18,552 | +0,010 |
| episodio con el calendario del test (`hard_ataque_comun.episodio_test`; ahí la semilla no casa) | 18,791 | 18,791 | 0,000 |

Media +0,008, nunca peor que -0,002. Con una semilla falsa (consumo x1,3) y la comprobación: +0,001 frente a v8
(con la primera hora usando la semilla, `seed_first_hour=True`, ganaba +0,002 más pero perdía -0,047 con la semilla falsa).
0 infracciones, `agent.py` empaquetado idéntico a `src/` también en el camino de la semilla.

## Descartado (con el número)

| Idea | Resultado |
|---|---|
| Horizonte de 36 / 48 h | 0,000 en dev. Ni con información perfecta: 22,036 a 24, 48 y 72 h en validación |
| Valor terminal (cuantil 10 / 40 / 50 %) | 0,000 |
| Desempate en el LP (coste diminuto por kWh cargado, descargado o vertido) | -0,001 a -0,135: el vertido de la descarga con información perfecta era un empate inocuo |
| Pesos del objetivo con las referencias reales del test | +0,002 (no es por ahí) |
| Márgenes separados (descarga / carga / plan) | todos a menos de ±0,02 salvo plan 2,0: +0,013 en 4 ventanas, +0,001 en otras 5 y -0,027 con el calendario del test |
| Tope de descarga por hora en el LP en vez de inflar la solar | -0,026 a -0,050 |
| Escalar la desviación prevista del mercado (x0,8 / 1,2 / 1,5) | -0,03 a -0,42: la regresión ya está en su punto |

## Dónde está el hueco (validación reservada)

| Agente | Score |
|---|---|
| v8 | 20,83 |
| consumo y solar perfectos a 24 h | 21,45 (+0,61) |
| precio y CO2 perfectos a 24 h | 21,56 (+0,73) |
| todo perfecto a 24 h | 22,04 |
| óptimo con todo el futuro | 22,40 |

Ojo: ninguna ventana del banco tiene el calendario del test (todas acaban antes del día 25), así que el final de cada
semana no se reproduce: el óptimo sí lo sabe y el agente no. Parte de los 0,37 entre "todo perfecto a 24 h" y el
óptimo es eso, no algo que se pueda ganar en el test.
