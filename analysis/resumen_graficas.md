# Resumen de las gráficas para la presentación (P2)

Las 11 gráficas están en `analysis/figs/` (PNG a 200 ppp, fondo claro, listas para pegar en una slide).
Cada una lleva su conclusión en el título. Se regeneran con los scripts `analysis/p2_*.py`.

El orden sigue el guion (`presentation/guion.md`, de momento en la rama `p1-optimizador`). **Principal** = va en la
slide del bloque. **Apoyo** = solo si hay tiempo (bloques ✂). **Reserva** = para las preguntas del jurado.

## De un vistazo

| # | Bloque del guion | Gráfica | Uso | La cifra que hay que decir |
|---|---|---|---|---|
| 1 | 2 · Lo que dicen los datos | `patrones_por_hora.png` | Principal | A las 21 h la red es 2,1 veces más sucia y 3,1 veces más cara que a mediodía |
| 2 | 2 · Lo que dicen los datos | `patrones_conflicto.png` | Apoyo | De madrugada la luz es un 10 % más barata que la media, pero un 20 % más sucia |
| 3 | 2 · Lo que dicen los datos | `patrones_mes_hora.png` | Reserva | Agosto aporta 1,08 de los 6,09 puntos; diciembre, 0,23 |
| 4 | 3 · Nuestro agente | `resultados_semana_tipo.png` | Principal (junto al esquema del GPS) | Carga cada mediodía y descarga cada anochecer: un ciclo largo y otro corto al día |
| 5 | 4 · Resultados | `resultados_estrategias.png` | Principal | 6,09 de 6,12: el 99,6 % del máximo teórico. La plantilla oficial, 0,03 |
| 6 | 5 · Lo que encontramos | `calidad_contador_congelado.png` | Principal | De 22:10 a 06:00 el contador no se lee: el 33 % de los registros repiten un valor |
| 7 | 5 · Lo que encontramos | `calidad_perfil_noche.png` | Apoyo (o en lugar de la 6) | El consumo nocturno real es de 785 kW, no de 971 kW: un 19 % menos |
| 8 | 6 · Recomendación | `techo_restricciones.png` | Principal | El techo lo pone el tamaño: con el doble de batería, de 6,1 a 12,1 |
| 9 | 6 · Recomendación | `escenarios_ahorro.png` | Principal | 2 MWh evitan 43 t de CO₂ y 92.000 € al año; 4 MWh, 86 t y 184.000 € |
| 10 | 6 · Recomendación | `escenarios_marginal.png` | Apoyo | Cada MWh evita 21,7 t al año hasta los 4 MWh; de 4 a 8, 17,9; de 8 a 16, 11,4 |
| 11 | 6 · Recomendación | `techo_carga_descarga.png` | Reserva | El 65 % de la carga es de 12 a 17 h y el 55 % de la descarga, de 18 a 23 h |

## Gráfica a gráfica

### 1. `patrones_por_hora.png` — CO₂ y precio por hora del día
- **Qué se ve:** dos paneles con la media del año por hora y la banda de la mitad central de los días.
- **Qué demuestra:** la red es limpia y barata a mediodía y sucia y cara al anochecer. Ahí está el negocio de la batería.
- **Cifras:** CO₂ de 52 g/kWh (13 h) a 111 g/kWh (21 h). Precio de 7,6 cént./kWh (14 h) a 23,5 (21 h).
- **Si preguntan:** son 6.768 h de precio y CO₂ del train, noviembre incluido.

### 2. `patrones_conflicto.png` — ¿coinciden las horas sucias y las caras?
- **Qué se ve:** a la izquierda, CO₂ y precio por hora respecto a su media; a la derecha, su correlación por mes.
- **Qué demuestra:** casi siempre apuntan a lo mismo (correlación 0,58, positiva todos los meses). El conflicto está
  en la madrugada: barata pero sucia.
- **Cifras:** optimizar solo CO₂ da 6,13 % de CO₂ y 4,56 % de coste; el 70/30 renuncia a 0,35 puntos de CO₂ y gana
  2,34 de coste. Optimizar solo el coste pierde la mitad del ahorro de CO₂ (3,06 %).
- **Mensaje para el cliente:** una batería gestionada "por precio" no es lo mismo que una gestionada por emisiones.

### 3. `patrones_mes_hora.png` — mapa de calor mes × hora
- **Qué se ve:** dos mapas (CO₂ y precio), de septiembre a agosto.
- **Qué demuestra:** el patrón diario se repite todo el año, pero es mucho más marcado en verano. Febrero es limpio a
  todas horas.
- **Cifras:** octubre es el mes más sucio (114 g/kWh) y febrero el más limpio (51).

### 4. `resultados_semana_tipo.png` — una semana de julio
- **Qué se ve:** arriba, lo "mala" que es cada hora (el peso 0,7·CO₂ + 0,3·precio) con las horas en que el agente
  carga (azul) y descarga (naranja); abajo, la carga de la batería.
- **Qué demuestra:** el agente carga en los valles y descarga en los picos, todos los días, sin reglas escritas a mano.
- **Si preguntan:** es la semana de validación del 18 al 24 de julio de 2026, con el agente real (no el óptimo).

### 5. `resultados_estrategias.png` — comparativa de estrategias
- **Qué se ve:** el score en validación de la plantilla oficial, las reglas simples, nuestro agente y el máximo teórico.
- **Qué demuestra:** planificar lo es casi todo, y nuestro agente está pegado al techo.
- **Cifras:** 0,03 (con 7 infracciones) · 0,08 · **6,09** · 6,12.
- **Si preguntan:** el máximo teórico es el mismo optimizador conociendo todo el futuro; nada puede superarlo.

### 6. `calidad_contador_congelado.png` — el contador no se lee por la noche
- **Qué se ve:** dos días de enero. La línea gris (dataset) es plana por la noche; la azul es el consumo real.
- **Qué demuestra:** el consumo nocturno del dataset no es una medida, sino el último valor repetido.
- **Cifras:** ocurre todas las noches, de 22:10 a 06:00 (el 32,9 % de los registros).
- **Si preguntan cómo lo sabemos:** a las 06:05 el contador entrega la energía consumida durante la noche; dividida
  entre 8 horas da el consumo real.

### 7. `calidad_perfil_noche.png` — el día medio, dataset frente a real
- **Qué se ve:** el consumo medio de un laborable por horas.
- **Qué demuestra:** el dataset marca ~1.000 kW toda la noche y el consumo real es de ~800 kW.
- **Cifras:** 785 kW frente a 971 kW (−19 %): unos 1.500 kWh de más cada noche, el 5,5 % del consumo diario.
- **Consecuencia:** el campus real consume 24,7 MWh al día y emite unas 750 t de CO₂ al año, no 26,2 MWh ni 805 t.
  El ahorro de la batería en kg y en € no cambia; en porcentaje pasa de 6,0 a 6,5.

### 8. `techo_restricciones.png` — por qué solo un 6 %
- **Qué se ve:** el máximo teórico al quitar una restricción física cada vez.
- **Qué demuestra:** el techo lo pone el tamaño de la batería, no el algoritmo.
- **Cifras:** real 6,1 · sin pérdidas 7,4 · sin límite de potencia 7,2 · sin las dos 8,9 · el doble de batería 12,1.
- **La cuenta, por si la piden:** `9,9 % × 1,34 − 11,0 % × 0,66 = 6,12` (energía movida × lo que pesa la hora).

### 9. `escenarios_ahorro.png` — cuánto ahorra cada tamaño de batería
- **Qué se ve:** CO₂ evitado y euros ahorrados al año según la capacidad. Línea continua: la potencia crece con la
  capacidad. Línea discontinua: potencia fija de 500 kW.
- **Qué demuestra:** el ahorro es proporcional al tamaño hasta 4 MWh y después se frena. Sin ampliar la potencia, se
  estanca enseguida.
- **Cifras:** 1 MWh, 22 t y 46.000 €; **2 MWh, 43 t y 92.000 €**; 4 MWh, 86 t y 184.000 €; 8 MWh, 158 t y 303.000 €.
- **Recomendación:** 4 MWh con 1.000 kW, y ampliar siempre la potencia a la vez que la capacidad.

### 10. `escenarios_marginal.png` — lo que rinde cada MWh añadido
- **Qué se ve:** toneladas de CO₂ evitadas al año por cada MWh que se añade.
- **Qué demuestra:** el punto de rendimientos decrecientes está en 4 MWh.
- **Por qué:** una batería de 4 MWh ya descarga a 1.000 kW, casi todo lo que consume el campus (1.100 kW de media).

### 11. `techo_carga_descarga.png` — a qué horas trabaja el plan óptimo
- **Qué se ve:** energía cargada y descargada por hora del día (media).
- **Qué demuestra:** dos ciclos al día: el principal (mediodía → anochecer) y uno pequeño (madrugada → amanecer).
- **Cifras:** 1,37 ciclos completos al día, unos 500 al año.

## Avisos para quien monte las slides

- **Dos bases distintas, no mezclarlas.** Los scores (6,09, 6,12, 99,6 %) son de la validación oficial (1.848 h).
  Las toneladas y los euros al año son del óptimo sobre todo el train limpio (258 días), anualizado.
- **Los escenarios son el óptimo teórico**, no el agente real (que queda un 0,4 % por debajo), y suponen que la
  batería no se degrada.
- **No llevar la tabla de retorno de la inversión** de `escenarios.md` sin un dato real de coste: el coste por kWh
  es un supuesto nuestro.
- **Las cifras del campus sin batería** (805 t, 1,38 M€, 26–27 MWh al día) salen del dataset, que sobrestima el
  consumo nocturno. Con el consumo real son unas 750 t, 1,30 M€ y 24,7 MWh al día. Conviene decir "según el
  dataset" o usar las reales.
- Los títulos de las gráficas ya son la conclusión: en la slide basta con una frase debajo.
