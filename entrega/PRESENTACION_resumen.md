# Resumen para la presentación final — SanHackobos · Reto UPC Sostenible

Datathon FME 2026 · domingo 15/11 · demos a las 14:00.

Fuentes: la guía técnica en PDF (28 páginas, describe la versión 8), el enunciado oficial y lo medido en el repo.
La web de la datathon solo da el horario y los premios; la web del reto y las slides de la UPC no se han podido leer.

---

## 1. Lo que se sabe del formato

- **Domingo:** demos a las 14:00, deliberación a las 17:00 y premios a las 17:30.
- **Qué cuenta**, según la organización: solo el modo difícil y el ranking privado, y el jurado mira un único nombre de equipo (`SanHackobos`).
- **Criterios orientativos de la datathon:** idea e innovación, tecnología, aprendizaje, diseño, presentación, resolución del problema y eficiencia.
- **Duración de la demo:** no está publicada. Preguntadla en el Discord y llevad una versión de 3 minutos y otra de 5.

---

## 2. El relato en cinco ideas

1. **El problema.** El campus compra casi toda su electricidad, y el precio y el CO₂ cambian cada hora. La batería no genera nada: cambia en qué horas se compra.
2. **La idea clave.** El score es una suma de compras ponderadas, así que es lineal. Por eso se puede optimizar de forma exacta con programación lineal, sin reglas a mano.
3. **El método.** Cada hora se prevé lo que no se conoce, se calcula el plan óptimo de 24 horas y se ejecuta solo la primera hora. Es control predictivo, como un GPS que recalcula.
4. **La regla del 11 %.** La batería pierde un 10 % en cada ida y vuelta. Mover energía solo compensa si la hora mala es al menos un 11 % peor que la buena.
5. **La medida.** El mismo optimizador con todo el futuro conocido da el máximo teórico, y con él medimos cuánto nos falta.

---

## 3. Las cifras que hay que saberse

| | Modo estándar | Modo difícil |
|---|---|---|
| Batería | 2.000 kWh, ±500 kW | 6.000 kWh, ±1.500 kW |
| Solar | 26 kW de media, casi no cuenta | 12 veces mayor, sobra a mediodía |
| Precio y CO₂ conocidos | 24 horas | 3 horas |
| Nuestra nota en casa / máximo teórico | 6,09 / 6,12 (99,6 %) | 21,07 / 22,40 (versión final) |
| Nota pública en la web | 6,43 | 24,15 (v10) y 24,06 (final) |
| Infracciones | 0 | 0 |
| Tiempo | 4 s de 60 | 8 s de 60 |

- **Score:** 0,7 × % de CO₂ ahorrado + 0,3 × % de coste ahorrado, menos las infracciones.
- **Física:** rendimiento √0,9 por sentido (90 % ida y vuelta), carga inicial al 50 %, el excedente se vierte sin cobrar.
- **Test:** los últimos 7 días de cada mes, 12 semanas y 2.016 horas. La mitad es pública.
- **Red:** limpia y barata a mediodía (52 g CO₂/kWh a las 13 h) y sucia y cara a las 21 h (111 g/kWh; precio 3 veces mayor).
- **Campus sin batería, al año** (según el contador): 9,6 GWh, 805 t de CO₂ y 1,38 M€. Con el consumo nocturno real: unas 750 t y 1,30 M€.

---

## 4. Cómo funciona una hora del agente

1. Llega la observación y se traduce al formato interno.
2. Se prevé lo que falta: precio y CO₂ (en el modo difícil), consumo y solar.
3. Se resuelve un programa lineal de 24 horas que minimiza la suma del peso de lo comprado, con la física de la batería.
4. Se ejecuta solo la primera hora, recortada a lo físicamente posible.
5. A la hora siguiente se repite todo con datos nuevos y con la carga real de la batería.

**Peso de una hora:** `0,7 · CO₂ / CO₂ medio + 0,3 · precio / precio medio`. Es lo "mala" que es esa hora para comprar.

---

## 5. Las tres piezas del modo difícil

- **Previsión de precio y CO₂.** Un perfil por mes, tipo de día y hora, más una regresión que corrige la desviación con 13 pistas. El CO₂ se prevé mejor que el precio (R² de 0,79 a 4 horas y 0,23 a 23 horas; el precio, 0,49 y casi 0).
- **Previsión de consumo y solar.** El consumo sale de un perfil semanal corregido con la hora anterior y con ayer. La solar es el "cielo despejado" de la fecha por la claridad de hoy.
- **Decidir con incertidumbre.** Descargar de más es tirar la energía; descargar de menos solo la aplaza. El plan cuenta con cuánto suele fallar la previsión y decide cuánto apurar.

Además:
- **Calendario del test:** son 12 semanas sueltas encadenadas. El agente detecta el salto entre semanas y descarta la lectura anterior, que es de un mes antes.
- **Memoria al empezar cada semana:** arranca con los últimos días del train de ese mes.
- **Fin del test:** se detecta por calendario (31/08/2026) y la batería llega vacía.

### Progresión en el modo difícil

| Versión | Qué añade | Nota en casa | Nota pública |
|---|---|---|---|
| Sin batería | — | 0,00 | — |
| Solo las 3 horas conocidas | — | 15,5 | — |
| v2 | Primera previsión propia | 20,37 | 23,35 |
| v6 | Previsión de precio y CO₂ con memoria | 20,66 | 23,70 |
| v10 | Previsión ampliada de consumo y solar, memoria semanal | 20,79 | 24,15 |
| v12 | El plan cuenta con la incertidumbre | 20,92 | 24,11 |
| Final | Perfiles interpolados entre meses | 21,07 | 24,06 |
| Máximo teórico | Todo el futuro conocido | 22,40 | — |

---

## 6. Hallazgos propios que diferencian

- **El contador no se lee de 22:10 a 06:00** y el dataset repite el último valor. El consumo nocturno real es un 19 % menor (785 kW frente a 971 kW).
- **Una avería de 14 horas** (17–18 de junio) explica toda la distancia al máximo en el modo estándar. El agente tiene dos protecciones y el vertido baja de 666 kWh a 0.
- **El 70/30 resuelve el conflicto entre CO₂ y precio.** De madrugada la luz es barata pero sucia. Optimizar solo el coste pierde la mitad del ahorro de CO₂ (3,06 % frente a 5,78 %).
- **Por qué solo un 6 % en el estándar:** la batería es el 7,6 % del consumo diario. Con el doble de batería, el doble de ahorro.
- **Recomendación para UPC Sostenible:** con la batería de 2 MWh se evitan 43 t de CO₂ y 92.000 € al año. El tamaño eficiente es de unos 4 MWh con 1.000 kW; a partir de ahí cada MWh rinde menos.

---

## 7. Preguntas difíciles y su respuesta

| Pregunta | Respuesta |
|---|---|
| ¿Por qué no aprendizaje automático o refuerzo? | El score es lineal y el óptimo se calcula exacto. Solo se aprende lo que no se conoce: las previsiones. |
| ¿Por qué no llegáis al máximo? | En el estándar, por una avería del contador. En el difícil, por no conocer el CO₂ más allá de 3 horas (unos 0,7 puntos) y la solar de la hora actual. |
| ¿Habéis sobreajustado? | Diseñamos con los días 8–14 y verificamos con otros. La versión final gana a la anterior en 9 ventanas de 9 y en 6 escenarios con datos deformados. |
| Hay equipos con más nota pública. | El público es la mitad de las horas. No hemos enviado variantes para subirlo, porque vaciar o llenar la batería en el momento justo sube una mitad y hunde la otra. |
| ¿Por qué vaciáis la batería al final? | Porque la carga final no puntúa. En un campus real no lo haríamos, y lo decimos. |
| ¿Qué pasa si falla algo? | Cada pieza tiene un respaldo y toda acción pasa por un recorte físico: 0 infracciones y 0 excepciones. |
| ¿Qué supuestos son frágiles? | El calendario del test y los festivos están escritos en el código. La noche "congelada" es un artefacto del dataset. |
| ¿Funcionaría en otro campus? | El método sí. Los perfiles y las previsiones habría que reajustarlos con sus datos. |
| ¿Por qué 70/30 y no solo CO₂? | Lo fija el reto. Frente a optimizar solo CO₂, renuncia a 0,35 puntos de CO₂ y gana 2,34 de coste. |
| ¿Por qué un horizonte de 24 horas? | Ver más lejos no aporta: 0,0002 puntos en el estándar y 0,000 en el difícil, incluso con información perfecta. |
| ¿Cuánto tarda? | 2–4 ms por hora. Todo el test, 4–8 segundos de los 60 permitidos. |

---

## 8. Límites que conviene decir antes de que los pregunten

- La previsión del precio más allá de 8 horas no tiene señal; la del CO₂ aguanta algo más.
- El calendario del test, el fin el 31/08/2026 y los festivos están escritos a mano.
- Vaciar la batería al final es una consecuencia de las reglas del reto, no una práctica real.
- Los escenarios de tamaño de batería son el óptimo teórico y suponen que la batería no se degrada.
- La tabla de retorno de la inversión usa un coste por kWh supuesto por nosotros: no llevarla sin un dato real.

---

## 9. Dónde la guía en PDF está desactualizada

El PDF describe la versión 8 (commit `77e0157`). Si presentáis la versión final, corregid esto:

- **El margen fijo de 1,4 ya no es lo que decide.** Ahora el plan lleva dentro la incertidumbre del consumo neto (versión 12).
- **Los perfiles de precio y CO₂ se interpolan entre meses**, porque el test son los días 25–31 y el train los días 1–24.
- **Cada semana arranca con memoria del train**, también para consumo y solar.
- **Las notas del PDF** (20,83 en casa, primeros de 32 equipos) son del sábado por la tarde.

---

## 10. Material listo

- **Gráficas del modo estándar:** `analysis/figs/` (11 figuras), con la frase de cada una en `analysis/resumen_graficas.md`. Del modo difícil no hay ninguna hecha.
- **Guion:** `presentation/guion.md` (pensado para el modo estándar; hay que añadir el modo difícil, que es el que cuenta).
- **Versión final y su revisión:** `FINAL.md` y `REVISION.md` en la rama `final`.
- **Medidas de generalización:** `analysis/hard_v15.md` en la rama `p2-datos`.
