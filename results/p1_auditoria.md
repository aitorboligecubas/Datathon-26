# P1 · Auditoría del agente

Generado por `python scripts/p1_auditoria.py` con los datos oficiales del train.

## 1. ¿Nuestro simulador da lo mismo que el oficial en todos los datos?

| Datos | Horas | Score oficial | Score nuestro | Infr. oficial | Infr. nuestro |
|---|---|---|---|---|---|
| Validación | 1848 | 6,09 | 6,09 | 0 | 0 |
| Train | 4145 | 5,54 | 5,54 | 0 | 0 |
| Todo | 5993 | 5,67 | 5,67 | 0 | 0 |

Coinciden.

## 2. Episodios tipo test: 12 semanas al azar del histórico, concatenadas

20 episodios de 2.016 h. Cada uno son 12 bloques de 168 h seguidas, elegidos al azar y puestos uno detrás de otro, como hace el test oficial con la última semana de cada mes.

| | Episodios | Score medio del agente | Score medio del óptimo | Distancia media | Distancia máxima | Infracciones |
|---|---|---|---|---|---|---|
| Sin averías del contador | 18 | 5,50 | 5,50 | 0,0003 | 0,0015 | 0 |
| Con alguna hora de avería | 2 | 5,79 | 5,79 | 0,0031 | 0,0032 | 0 |
| Todos | 20 | 5,53 | 5,53 | 0,0006 | 0,0032 | 0 |

El score de un episodio va de 5,06 a 6,15 según las semanas que le toquen: la cifra del leaderboard depende sobre todo de las semanas, no del agente.

## 3. ¿Y si el test trae una semana sin datos de contador?

En el train, noviembre no tiene datos de contador. El test son 12 semanas completas, así que la de noviembre existe y no sabemos cómo la han rellenado. Episodio con las fechas del test oficial; los datos de cada semana son los de la última semana del train de ese mes, con Navidad al 55 % de consumo.

Todos los planteamientos usan el mismo optimizador; solo cambia cómo tratan el consumo. "Mitad 1" y "mitad 2" son el score contando solo las primeras o las últimas 1.008 horas, como hace el simulador oficial con el ranking público y el privado.

| Escenario | Planteamiento | Completo | Mitad 1 | Mitad 2 | Vertido (kWh) |
|---|---|---|---|---|---|
| Noviembre a cero | Nuestro agente | 6,412 | 5,550 | 7,076 | 23 |
| Noviembre a cero | Nuestro agente antes | 6,352 | 5,413 | 7,076 | 23 |
| Noviembre a cero | LP con consumo = última hora | 6,391 | 5,501 | 7,076 | 23 |
| Noviembre a cero | LP que ignora el consumo | 5,295 | 3,083 | 6,994 | 22698 |
| Noviembre a cero | Óptimo (conoce el futuro) | 6,461 | 5,603 | 7,121 | 0 |
| Noviembre normal | Nuestro agente | 6,289 | 5,475 | 7,076 | 23 |
| Noviembre normal | Nuestro agente antes | 6,289 | 5,475 | 7,076 | 23 |
| Noviembre normal | LP con consumo = última hora | 6,290 | 5,475 | 7,076 | 23 |
| Noviembre normal | LP que ignora el consumo | 6,226 | 5,431 | 6,994 | 2014 |
| Noviembre normal | Óptimo (conoce el futuro) | 6,314 | 5,479 | 7,121 | 0 |

Con noviembre a cero, la gestión de la semana sin datos sube el score de la primera mitad en 0,137 puntos; con noviembre normal no cambia nada. Quien ignora el consumo vierte la batería cada día de esa semana.

Poniendo a cero, de una en una, cada una de las otras semanas (score completo):

| Semana a cero | Nuestro agente | Antes | Óptimo |
|---|---|---|---|
| 2025-10 | 6,342 | 6,343 | 6,441 |
| 2025-12 | 6,271 | 6,257 | 6,330 |
| 2026-01 | 6,353 | 6,342 | 6,418 |
| 2026-02 | 6,394 | 6,394 | 6,423 |
| 2026-03 | 6,372 | 6,363 | 6,407 |
| 2026-04 | 6,245 | 6,245 | 6,323 |
| 2026-05 | 6,231 | 6,227 | 6,310 |
| 2026-06 | 6,330 | 6,325 | 6,386 |
| 2026-07 | 6,433 | 6,392 | 6,495 |

Diferencia con la lógica anterior: de -0,001 a +0,042 (media +0,009). Lo que queda hasta el óptimo es casi todo inevitable: el óptimo sabe de antemano que la semana viene sin datos y llega a ella con la batería vacía.

## 4. El leaderboard público solo cuenta la mitad de las horas

El mismo agente con distinto reparto entre CO₂ y coste (multiplicador del peso del coste). "Completo" es el score sobre todas las horas; las demás columnas son el score que se vería si solo contara esa mitad, calculado como hace el simulador oficial con su máscara.

| Peso del coste | Completo | Semanas alternas (pares) | Semanas alternas (impares) | Primera mitad | Segunda mitad | Horas al azar (50 %) |
|---|---|---|---|---|---|---|
| ×0,50 | 6,038 | 6,298 | 5,721 | 4,792 | 7,416 | 6,669 |
| ×0,70 | 6,082 | 6,282 | 5,836 | 4,904 | 7,382 | 6,603 |
| ×0,85 | 6,089 | 6,227 | 5,914 | 4,913 | 7,388 | 6,533 |
| ×1,00 | 6,090 | 6,215 | 5,932 | 4,913 | 7,389 | 6,574 |
| ×1,15 | 6,085 | 6,214 | 5,920 | 4,904 | 7,387 | 6,525 |
| ×1,40 | 6,069 | 6,199 | 5,904 | 4,884 | 7,375 | 6,469 |
| ×2,00 | 6,001 | 6,067 | 5,915 | 4,880 | 7,236 | 6,572 |

Sobre todas las horas, ningún otro reparto mejora al nuestro. Sobre una mitad, otro reparto puede salir hasta 0,095 puntos por encima sin ser mejor agente: lo que gana en esa mitad lo pierde en la otra.

## 5. Fuzzing: observaciones hostiles

12000 observaciones con previsiones con NaN, infinitos, negativos, vacías o recortadas; listas, tuplas, arrays y Series; batería justo en los límites; lecturas del contador a cero, ausentes o en texto; campos que faltan.

| Excepciones | Respuestas no numéricas | Infracciones | Veces que el agente actuó |
|---|---|---|---|
| 0 | 0 | 0 | 8167 |

## 6. Latencia por paso (en esta máquina)

| Media | Percentil 99 | Máximo | Proyección a 2.016 pasos | Respaldos usados |
|---|---|---|---|---|
| 2,24 ms | 3,45 ms | 5,22 ms | 4,5 s (límite 60 s) | 0 |

En el servidor oficial, el dry-run midió 2,07 ms por paso.

