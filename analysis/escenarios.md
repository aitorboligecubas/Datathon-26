# ¿Qué ahorraría una batería de 1, 2, 4 u 8 MWh? (P2)

Cifras de `python analysis/p2_escenarios.py` (tabla completa en `escenarios.csv`). Óptimo con información perfecta
para cada tamaño, sobre todo el train limpio (258 días de 11 meses; falta noviembre), anualizado a 365 días.
Nuestro agente captura el 99,6 % de ese óptimo en validación.

Campus sin batería, al año: **9,6 GWh comprados, 805 t de CO₂ y 1,38 M€**.

## Resumen para la presentación

1. **La batería del reto (2 MWh) evita 43 t de CO₂ y 92.000 € al año.**
2. **Hasta 4 MWh, el ahorro es proporcional al tamaño:** cada MWh instalado evita unas 21,7 t de CO₂ y ahorra
   unos 46.000 € al año. Una de 4 MWh evita 86 t y 184.000 €.
3. **A partir de 4 MWh, los rendimientos son decrecientes.** De 4 a 8 MWh, cada MWh añadido evita 17,9 t (un 18 %
   menos) y ahorra 29.700 € (un 35 % menos). De 8 a 16 MWh, 11,4 t y 17.800 €.
4. **La razón es física:** una batería de 4 MWh descarga a 1.000 kW, casi todo lo que consume el campus (1.100 kW
   de media). Una más grande no tiene consumo que cubrir en las horas malas, y además agota las mejores horas.
5. **La potencia importa tanto como la capacidad.** Si se amplía la capacidad sin ampliar la potencia (500 kW),
   pasar de 2 a 4 MWh solo da 30 t más, y de 4 a 8 MWh, 16 t.

**Recomendación:** el tamaño eficiente está en torno a **4 MWh con 1.000 kW**. Hasta ahí cada euro invertido rinde
lo mismo que en la batería de 2 MWh; más allá, cada MWh rinde cada vez menos.

## Potencia proporcional a la capacidad (4 h a plena potencia, como la batería del reto)

| Capacidad | Potencia | CO₂ evitado (t/año) | Ahorro (€/año) | % de CO₂ | % de coste | Ciclos al día | t CO₂ por MWh añadido |
|---|---|---|---|---|---|---|---|
| 1 MWh | 250 kW | 21,7 | 46.200 | 2,7 | 3,4 | 1,38 | 21,7 |
| **2 MWh** | **500 kW** | **43,5** | **92.400** | **5,4** | **6,7** | **1,38** | **21,7** |
| 4 MWh | 1.000 kW | 86,4 | 183.600 | 10,7 | 13,3 | 1,36 | 21,5 |
| 8 MWh | 2.000 kW | 157,8 | 302.600 | 19,6 | 22,0 | 1,18 | 17,9 |
| 16 MWh | 4.000 kW | 248,6 | 445.300 | 30,9 | 32,4 | 0,95 | 11,4 |

## Potencia fija de 500 kW

| Capacidad | CO₂ evitado (t/año) | Ahorro (€/año) | Ciclos al día |
|---|---|---|---|
| 1 MWh | 23,9 | 57.300 | 1,65 |
| 2 MWh | 43,5 | 92.400 | 1,38 |
| 4 MWh | 73,5 | 114.000 | 1,03 |
| 8 MWh | 89,9 | 119.000 | 0,61 |

## Retorno de la inversión (solo orientativo)

Años para recuperar la inversión solo con el ahorro en la factura. **El coste instalado por kWh es un supuesto
nuestro, no un dato del reto: hay que contrastarlo con UPC Sostenible.**

| Coste instalado supuesto | 1–4 MWh | 8 MWh | 16 MWh |
|---|---|---|---|
| 200 €/kWh | 4,3 años | 5,3 | 7,2 |
| 300 €/kWh | 6,5 años | 7,9 | 10,8 |
| 400 €/kWh | 8,7 años | 10,6 | 14,4 |

## Límites de estas cifras (para las preguntas del jurado)

- Son el **óptimo con información perfecta**; el agente real queda un 0,4 % por debajo.
- Suponen las reglas del reto: se paga el PVPC hora a hora, el excedente no se cobra y la batería **no se degrada**.
  Con 1,4 ciclos al día son unos 500 ciclos al año: en la realidad la degradación cuenta.
- El ahorro en kg y en € no depende del error del contador por la noche (ver `calidad_datos.md`); el porcentaje, sí.
- Falta noviembre y el año se ha extrapolado desde 258 días.

## Gráficas

| Fichero | Qué demuestra |
|---|---|
| `figs/escenarios_ahorro.png` | El ahorro crece en proporción al tamaño hasta 4 MWh y después se frena; sin más potencia, se estanca enseguida |
| `figs/escenarios_marginal.png` | Cada MWh añadido evita 21,7 t de CO₂ al año hasta los 4 MWh; de 4 a 8, 17,9; de 8 a 16, 11,4 |
