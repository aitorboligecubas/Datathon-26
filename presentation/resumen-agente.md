# Qué hace el agente y por qué (resumen de P1 para el guion)

Estrategia **cerrada** el sábado 14/11. Números de la validación con datos oficiales; el detalle está en
`results/p1_ablaciones.md`.

1. **Cada hora planifica las próximas 24 h y ejecuta solo la primera**, como un GPS que recalcula. El plan es un
   programa lineal que minimiza justo lo que puntúa el reto (70 % CO₂, 30 % coste), así que no hay reglas a mano
   ni parámetros ajustados. Planificar aporta casi todo: 6,01 de los 6,09 puntos.
2. **Solo mueve energía cuando compensa la pérdida del 10 %**: carga en las horas limpias y baratas y descarga en
   las sucias y caras si la diferencia supera el 11 %. Precio y CO₂ a 24 h vienen exactos, y por eso no hace falta
   prever el consumo: con una previsión plana el resultado es el mismo (0,00 de diferencia).
3. **Nunca comete una infracción**: toda acción pasa por un control que la recorta a lo físicamente posible.
   0 infracciones en la validación, en el train, por semanas y con ruido.
4. **Dos protecciones sencillas.** Vacía la batería cuando se acaban los datos, porque la carga final no puntúa
   (+0,11; en el campus real no lo haríamos y lo decimos). Y no descarga más de lo que el campus consumió la hora
   anterior, para no tirar energía si el contador se avería (pasó 14 horas seguidas en los datos).
   Esta protección tiene dos capas: la previsión de P2 no espera consumo si el contador marcó 0, y la política
   de P1 pone el tope aunque la previsión falle.
   Y reconoce una **semana sin datos de contador** (el contador a 0 desde su primera hora, como noviembre
   en el train): no descarga y compra la carga de la semana siguiente en una hora barata, con un precio de
   reserva. En un episodio simulado con noviembre a cero vale 0,06 puntos.
5. **Está al 99,6 % del máximo teórico y aguanta.** Saca 6,09 frente a 6,12 del óptimo con todo el futuro conocido.
   En el train, 5,54 de 5,54. Si el servidor evaluase por semanas, 6,47 de 6,49. Con un 20 % de ruido en las
   previsiones, 6,01. Tarda 4 segundos de los 60 permitidos.

## Por qué la damos por cerrada

Lo que falta hasta el techo son 0,025 puntos, y **todo está en junio, el mes de la avería del contador**
(0,0245 de 0,0247; desglose por meses de P2, comprobado por P1). En los otros 10 meses, el agente y el óptimo
coinciden a la diezmilésima (0,0002 entre todos).
- **Mirar más allá de 24 h no vale nada:** fuera de la avería no queda distancia que cerrar.
- **La avería no se puede prever:** su primera hora llega sin aviso y, mientras dura, no hay consumo que cubrir.

(Una versión anterior de este resumen atribuía 0,01 al horizonte de 24 h. Era una lectura errónea de la variante
"con consumo real", que tampoco puede recolocar la descarga perdida durante la avería.)

Cualquier "mejora" de ese tamaño sería ajustarse a la validación. Preferimos una solución sin parámetros que
podamos explicar entera.

## Lo que aporta el análisis de P2 (para enlazar en el guion)

- **Toda la distancia al techo sale de 14 horas de avería del contador.** En los otros 10 meses de validación,
  el agente y el óptimo coinciden a la milésima (`analysis/calidad_datos.md`).
- **El consumo nocturno del dataset no es una medida.** De 22:10 a 06:00 el contador no se lee y repite el último
  valor; el consumo real es un 19 % menor. No cambia las decisiones del agente, pero sí el ahorro real: un 6,5 %
  en lugar de un 6,1 %.
- Patrones de la red, por qué el techo es ~6 % y escenarios de tamaño de batería: `analysis/patrones.md`,
  `analysis/techo.md` y `analysis/escenarios.md`.

## Frases para el jurado

- "No hemos entrenado nada: el agente resuelve cada hora el problema exacto que puntúa el reto."
- "Sabemos cuánto aporta cada pieza, y dos de las que probamos no aportan nada: lo decimos."
- "Con una batería de 2 MWh para un campus que consume 27 MWh al día, el máximo posible es un 6 %. Nosotros
  capturamos el 99,6 % de ese máximo."
