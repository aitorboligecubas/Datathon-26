# Calidad de los datos oficiales (P2)

Cifras de `python analysis/p2_calidad_datos.py` y de `eval.py` (filas "P2 calidad" de `results/experiments.csv`).
Todo sobre el train oficial (`oficial/data/train/`).

## Resumen para la presentación

1. **El consumo nocturno del dataset no es una medida: es un valor repetido.** De 22:10 a 06:00 el contador
   no se lee (el 33 % de los registros) y la potencia repite la última lectura. A las 06:05 el contador sí
   entrega la energía consumida durante la noche, y con ella se reconstruye el consumo real:
   **785 kW de media, frente a los 971 kW que dice el dataset (−19 %)**. Son unos 1.500 kWh de más cada noche,
   el 5,5 % del consumo diario.
2. **Toda la distancia entre nuestro agente y el óptimo teórico viene de 14 horas de avería del contador.**
   El 17–18 de junio el contador perdió la comunicación y marcó 0 kW. El agente no puede saberlo a tiempo y
   descarga la batería contra un consumo que "no existe" (666 kWh vertidos gratis). En los otros 10 meses de
   validación, agente y óptimo coinciden a la milésima.
3. **Corregir los datos no cambia las decisiones**, porque el campus siempre consume más de 500 kW: la batería
   nunca se queda sin consumo que cubrir. Lo que cambia es el porcentaje de ahorro, porque cambia la referencia.

## Qué falla y cuánto

| Problema | Cuánto | Qué hacemos |
|---|---|---|
| Contador sin lectura por la noche (22:10–06:00): la potencia repite el último valor | 24.405 registros de 5 min (32,9 %), todas las noches | Variante `real`: se sustituye por la energía realmente consumida (dato del propio contador a las 06:05). Solo para análisis: el test oficial lleva el valor repetido |
| Fallo de comunicación (`ESTADO COM` = 255): contador e inversores marcan 0 | 200 registros (0,27 %): 17–18 jun (14 h seguidas), 6 ago (1 h) y ratos sueltos en enero. **15 horas con consumo 0** en la tabla horaria | Variante `limpio`: se imputan con el perfil del mismo mes, tipo de día y hora |
| Inversores sin datos del 17 al 24 de agosto (el contador sí tiene) | 8 días. El `dropna` del tutorial tira esos días enteros | Variante `limpio`: solar del perfil de agosto. Se recuperan 192 h de consumo |
| Horas sin registros dentro de un día | 2 huecos: 17 jun (2,5 h) y 4 ago (5,5 h) | Variante `limpio`: se imputan |
| Noviembre de 2025 | Falta entero en contador e inversores. **Sí está en precio y CO₂** | Nada: no se puede inventar el consumo. Los patrones de precio y CO₂ sí usan noviembre |
| Cambios de hora | Las fechas están en hora local (el mediodía solar pasa de las 12:45 en invierno a las 13:25 en verano). Los dos cambios (26 oct y 29 mar) caen en la **última semana del mes: están en el test, no en el train** | El agente usa la hora que le da el entorno y no cuenta horas por su cuenta: un día de 23 o 25 h no le afecta |
| Valores anómalos | Ninguno fuera de rango: consumo entre 0 y 2.696 kW (el filtro oficial es 0–5.000) y solar entre 0 y 150 kW | Nada |

## ¿Cambia el score? (validación, oracle = óptimo teórico)

| Datos | mpc | oracle | Qué demuestra |
|---|---|---|---|
| Oficiales (como el tutorial) | 6,08 | 6,12 | Punto de partida. La diferencia de 0,04 está toda en junio (avería del contador) |
| Oficiales, con la regla "si el contador marcó 0, esta hora no descargo" | **6,09** | 6,12 | Recupera 0,012 de los 0,037. El resto es inevitable: la primera hora de la avería no se puede prever |
| Limpios (averías imputadas, agosto recuperado) | 6,04 | 6,04 | **Sin averías de medida, el agente iguala al óptimo.** La cifra baja porque cambia la semana de agosto |
| Consumo nocturno real | 6,46 | 6,46 | La batería ahorra lo mismo en kg y en €, pero el campus consume menos de lo que dice el dataset: el ahorro real es de un 6,5 %, no de un 6,1 % |
| Modelos entrenados con datos limpios, validación oficial | 6,08 | 6,12 | Limpiar los datos de entrenamiento no cambia nada: se mantienen los modelos actuales |

Las cifras de "limpios" y "real" no son comparables con el leaderboard: el test oficial se construye como el tutorial.
Por eso **la validación del equipo sigue usando los datos oficiales** y las variantes solo se usan para el análisis.

## Cómo usar las variantes

```bash
BATTERY_DATOS=limpio python eval.py --agent all     # oficial (por defecto) | limpio | real
```

`battery.data.read_meter()` devuelve el contador a 5 min con las banderas `com_fail`, `frozen` y `night_real_kw`.

## Gráficas

| Fichero | Qué demuestra |
|---|---|
| `figs/calidad_contador_congelado.png` | Dos días de enero: por la noche la línea del dataset es plana (no hay lectura) y el consumo real está un 20 % por debajo |
| `figs/calidad_perfil_noche.png` | En el perfil medio de un laborable, el dataset marca ~1.000 kW toda la noche y el consumo real es de ~800 kW |
