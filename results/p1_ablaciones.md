# P1 · Desglose de piezas y robustez

Validación con datos oficiales: 1848 h (11 semanas, una por mes). Generado por `python scripts/p1_ablaciones.py`.

## 1. ¿Cuánto aporta cada pieza?

| Variante | Score | ΔCO₂ % | ΔCoste % | Infr. | Diferencia con el agente | Qué mide |
|---|---|---|---|---|---|---|
| Reglas simples (greedy) | 0,08 | 0,10 | 0,05 | 0 | −6,01 | Sin planificar: lo que aporta el LP |
| **Agente completo (MPC)** | 6,09 | 5,73 | 6,92 | 0 | — |  |
| MPC sin valor de la carga al final del horizonte | 6,09 | 5,73 | 6,92 | 0 | −0,00 | El plan de 24 h vacía la batería cada día |
| MPC sin vaciar al final del episodio | 5,98 | 5,63 | 6,81 | 0 | −0,11 | La carga final se queda sin usar |
| MPC sin tope de descarga (última lectura del contador) | 6,08 | 5,73 | 6,89 | 0 | −0,01 | Avería del contador: 14 h marcando 0 |
| MPC con previsión plana (1.000 kW, sin solar) | 6,09 | 5,73 | 6,92 | 0 | +0,00 | Lo que aporta nuestra previsión |
| MPC con consumo y solar reales (trampa) | 6,11 | 5,77 | 6,92 | 0 | +0,02 | Lo que ganaríamos con previsión perfecta |
| Óptimo con todo el futuro (oracle) | 6,12 | 5,78 | 6,90 | 0 | +0,02 | Techo teórico |

## 2. ¿Y si el servidor evalúa cada semana por separado?

Cada semana con un agente nuevo, la carga reiniciada al 50 % y la previsión recortada al final de la semana (el agente vacía la batería al final de cada una).

| Agente | Seguido (nuestra validación) | Por semanas | Infr. por semanas |
|---|---|---|---|
| MPC | 6,09 | 6,47 | 0 |
| Oracle | 6,12 | 6,49 | 0 |

## 3. ¿Y si las previsiones de precio y CO₂ fallan?

Ruido multiplicativo que crece con la antelación (hasta el porcentaje indicado a 24 h). Media de 5 semillas.

| Ruido | Score medio | Peor semilla | Infracciones (total) |
|---|---|---|---|
| 0 % (oficial) | 6,09 | 6,09 | 0 |
| 5 % | 6,08 | 6,08 | 0 |
| 10 % | 6,06 | 6,06 | 0 |
| 20 % | 6,01 | 5,99 | 0 |

## 4. ¿Se sostiene fuera de la validación?

El agente no tiene parámetros ajustados sobre la validación, así que el train también sirve de prueba. Episodios largos (> 2.016 h) incluidos: el agente no depende de la duración del test.

| Datos | Horas | MPC | Oracle | % del techo | Infr. | Tiempo |
|---|---|---|---|---|---|---|
| Validación | 1848 | 6,09 | 6,12 | 99,60 % | 0 | 4,32 s |
| Train (3 primeras semanas de cada mes) | 4145 | 5,54 | 5,54 | 99,97 % | 0 | 8,50 s |
| Todo el histórico seguido | 5993 | 5,67 | 5,68 | 99,85 % | 0 | 12,73 s |
