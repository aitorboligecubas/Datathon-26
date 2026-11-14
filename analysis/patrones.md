# Cuándo es sucia y cara la red (P2)

Cifras de `python analysis/p2_patrones.py`. Precio y CO₂ de todo el train (6.768 h, del 1/9/2025 al 24/8/2026,
**noviembre incluido**).

## Resumen para la presentación

1. **La red es limpia y barata a mediodía, y sucia y cara al anochecer.** El CO₂ baja a 52 g/kWh a las 13 h
   (cuando produce la solar de toda España) y sube a 111 g/kWh a las 21 h, **2,1 veces más**. El precio va de
   7,6 cént./kWh a las 14 h a 23,5 a las 21 h, **3,1 veces más**.
2. **CO₂ y precio casi siempre apuntan a lo mismo.** Correlación horaria de 0,58. De las 6 horas más sucias de
   cada día, el 80 % están en la mitad cara; de las 6 más limpias, el 74 % están en la mitad barata. Las 21 h
   son a la vez la hora más sucia y la más cara.
3. **El conflicto está en la madrugada:** de 0 a 6 h la luz es barata (un 10 % por debajo de la media) pero sucia
   (un 20 % por encima). Quien solo mire el precio cargaría de madrugada; por CO₂ hay que cargar a mediodía.
4. **El 70/30 del reto resuelve bien el conflicto.** Con el óptimo teórico: optimizar solo CO₂ da 6,13 % de CO₂ y
   4,56 % de coste; el 70/30 renuncia a 0,35 puntos de CO₂ y gana 2,34 de coste.
5. **Todos los días hay margen para mover energía.** El peso de la peor hora del día es, de mediana, 2,66 veces
   el de la mejor, y ningún día baja de 1,11 (el mínimo para que compense, por el 10 % que se pierde).

## Por hora del día (media del año)

| | Mejor hora | Peor hora | Peor / mejor |
|---|---|---|---|
| CO₂ | 13 h (52 g/kWh) | 21 h (111 g/kWh) | 2,12 |
| Precio | 14 h (7,6 cént./kWh) | 21 h (23,5 cént./kWh) | 3,08 |
| Peso del score (0,7·CO₂ + 0,3·precio) | 14 h (0,60) | 21 h (1,42) | 2,36 |

## Por mes

| | sep | oct | nov | dic | ene | feb | mar | abr | may | jun | jul | ago |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CO₂ (g/kWh) | 86 | 114 | 89 | 103 | 88 | 51 | 68 | 68 | 76 | 75 | 96 | 104 |
| Precio (cént./kWh) | 13,5 | 14,5 | 13,3 | 14,7 | 14,6 | 11,4 | 14,3 | 12,3 | 12,0 | 12,7 | 16,0 | 16,8 |

Octubre y agosto son los meses más sucios; febrero, el más limpio (la mitad que octubre). En verano la diferencia
entre el mediodía y la noche es mucho mayor que en invierno, y ahí es donde más gana la batería: agosto aporta
1,08 de los 6,08 puntos de la validación, y diciembre, 0,23.

## El coste del conflicto (óptimo teórico en validación)

| Objetivo del optimizador | ΔCO₂ % | ΔCoste % | Score |
|---|---|---|---|
| Solo CO₂ (100/0) | 6,13 | 4,56 | 5,66 |
| **Score del reto (70/30)** | **5,78** | **6,90** | **6,12** |
| Mitad y mitad (50/50) | 5,32 | 7,62 | 6,01 |
| Solo coste (0/100) | 3,06 | 8,35 | 4,64 |

Optimizar solo el coste pierde la mitad del ahorro de CO₂. Es el argumento para UPC Sostenible de por qué
una batería gestionada "por precio" (lo habitual) no es lo mismo que una gestionada por emisiones.

## Gráficas

| Fichero | Qué demuestra |
|---|---|
| `figs/patrones_por_hora.png` | La red es limpia y barata a mediodía y sucia y cara a las 21 h: ahí está el negocio de la batería |
| `figs/patrones_mes_hora.png` | El patrón se repite todo el año, pero es mucho más marcado en verano; febrero es limpio a todas horas |
| `figs/patrones_conflicto.png` | CO₂ y precio van juntos de día; de madrugada la luz es barata pero sucia. La correlación es positiva todos los meses (0,4–0,7) |
