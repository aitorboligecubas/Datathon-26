# Por qué el ahorro máximo es de ~6 % (P2)

Cifras de `python analysis/p2_techo.py`: óptimo con información perfecta (`oracle`) sobre la validación oficial
(1.848 h, 77 días), cambiando una restricción física cada vez.

## Resumen para la presentación

1. **El techo lo pone el tamaño de la batería, no el algoritmo.** La batería (2 MWh) es el 7,6 % del consumo
   diario del campus (26,2 MWh). Con el doble de batería, el máximo se duplica: de 6,1 a 12,1.
2. **La cuenta sale con tres números.** El plan óptimo mueve cada día 2,6 MWh (el 9,9 % del consumo): hace
   1,37 ciclos al día. Compra esa energía en horas que "pesan" 0,66 y evita comprarla en horas que pesan 1,34
   (1 = hora media). Como se pierde un 10 % por el camino, hay que comprar un 11 % del consumo para ahorrar un 9,9 %:

   ```text
   9,9 % × 1,34  −  11,0 % × 0,66  =  6,12 puntos
   ```
3. **Las pérdidas cuestan 1,3 puntos y el límite de potencia, 1,1.** Una batería ideal del mismo tamaño
   (sin pérdidas y que se llenase en una hora) llegaría a 8,9.
4. **Nuestro agente está en el 99,6 % de ese techo** (6,09 de 6,12), y la diferencia es una avería del contador
   (ver `calidad_datos.md`).

## Quitar las restricciones de una en una

| Caso | Score máximo | ΔCO₂ % | ΔCoste % |
|---|---|---|---|
| **Batería real: 2 MWh, 500 kW, 10 % de pérdidas** | **6,12** | 5,78 | 6,90 |
| Sin pérdidas (rendimiento del 100 %) | 7,40 | 6,95 | 8,44 |
| Sin límite de potencia (se llena en 1 h) | 7,25 | 6,49 | 9,01 |
| Sin pérdidas y sin límite de potencia | 8,93 | 8,13 | 10,80 |
| Doble de capacidad y de potencia (4 MWh, 1.000 kW) | 12,12 | 11,45 | 13,68 |
| Referencia absurda: comprar todo el consumo del día en su mejor hora | 43,6 | — | — |

## Cuándo carga y cuándo descarga el plan óptimo

Hace **dos ciclos al día**:
- el principal: carga de 12 a 17 h (el 65 % de la carga), cuando la red es limpia y barata, y descarga de 18 a 23 h
  (el 55 % de la descarga);
- uno secundario: carga de madrugada (1–5 h) y descarga al amanecer (6–8 h), cuando sube el CO₂ antes de que
  entre la solar.

## Gráficas

| Fichero | Qué demuestra |
|---|---|
| `figs/techo_restricciones.png` | Quitar las pérdidas o el límite de potencia sube el techo un punto; doblar la batería lo dobla. El límite es físico |
| `figs/techo_carga_descarga.png` | El plan óptimo carga a mediodía y descarga al anochecer, con un segundo ciclo pequeño de madrugada |
