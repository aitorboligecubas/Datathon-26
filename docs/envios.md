# Envíos oficiales

Owner: integrador. Equipo en la web: **SanHackobos**. El PIN no se apunta aquí (el repo es público).

Reglas que muestra la web (más precisas que las del enunciado):
- **10 envíos por turno**, no por día. Turno 1: sábado hasta las 21:00.
- Cada envío ejecuta **2.016 horas** (12 semanas: los últimos 7 días de cada mes, empezando el 24/09/2025).
- **El jurado evaluará en el ranking privado solo las 2 entregas que seleccionemos** ("Selecció Oficial per al
  Jurat"). Si no elegimos, cuentan las 2 mejores del test público. Se puede cambiar hasta el cierre.
- Antes de cada envío, "Validació Ràpida" (48 pasos, no gasta intento).

| # | Fecha y hora | Commit | Qué lleva | Score local (val.) | Score público | ΔCO₂ | ΔCoste | Infr. | Notas |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Sáb 14/11, 13:06 | `668ec9f` | MPC con LP a 24 h, vaciado al final, tope de descarga, adaptador robusto | 6,09 | **6,43** | 5,97 % (4.288 kg) | 7,51 % (8.913 €) | 0 | Dry-run previo correcto (2,07 ms por paso). Dentro del rango esperado (5,5–6,5). Seleccionada por defecto para el jurado |

| 2 | Sáb 14/11, 16:27 | `9dcf4c3` | v2: semana sin datos de contador, primera hora de cada semana, adaptador con huecos, modelos incrustados | 6,09 | **6,43** | 5,97 % (4.288,0 kg) | 7,51 % (8.913,11 €) | 0 | Exactamente lo mismo que el envío 1: en el test público no hay ninguna semana con el contador a 0. Hipótesis de "noviembre a cero" descartada |
| 3 | pendiente | `41c0c1f` | v2 + una semana con lecturas vacías (NaN) se trata como semana sin datos | 6,09 | | | | | Experimento: si sale 6,43 exacto, descartado; si sube ~0,1, una semana del público llega con lecturas vacías |

Referencia de la mitad pública sin batería (1.008 h): 71.816 kg de CO₂ y 118.746 €, es decir, 71,2 kg/h y 117,8 €/h.
Los datos del train dan unos 92 kg/h y 157 €/h: la referencia pública es un 20–25 % más baja. Cuadra con que la
mitad pública sean las seis primeras semanas (septiembre a febrero), con noviembre a cero y Navidad con poco consumo
(estimación con los datos del train: 68–76 kg/h y 119–131 €/h).

Lectura del leaderboard tras el envío 1 (sábado 13:10, 17 equipos): 15 equipos en 6,43. Con más decimales (calculados
con los kg y € de la tabla): líder 6,43805; después 6,43145, 6,43142, 6,43141 y nosotros 6,43138.

Lo que ha dicho la organización (Discord, sábado 14/11):
- 15:04: en el ranking **público** varios equipos han llegado al máximo; en el **privado**, ninguno. Seguir trabajando.
- 16:33: se abre el **Hard Mode**, con ranking y cupo de envíos propios. El modo estándar sigue abierto y no cambia.
- La tabla ordena por nota redondeada a dos decimales y, a igualdad, por hora de envío. Los primeros del estándar
  tienen 6,44 (entre 6,438 y 6,445); nosotros, 6,4314.

## Hard Mode (ranking propio)

Reglas que muestra la pestaña "Mode Difícil": batería de 6.000 kWh y ±1.500 kW, solar ×12, `preus_properes_24h` y
`co2_properes_24h` con solo 3 valores (la hora actual y las 2 siguientes), meteo de la hora anterior en
`noves_dades_5min`, y `cap_max_kwh` y `power_max_kw` en la observación. Conjunto público: 1.008 horas. Cupo:
10 envíos el sábado hasta las 21:00, 10 de sábado 21:00 a domingo 8:00 y 10 el domingo desde las 8:00. Hay
validación rápida que no gasta cupo. El ZIP se genera con `python scripts/build_submission.py --hard`.

| # | Fecha y hora | Commit | Qué lleva | Validación reservada | Score público | ΔCO₂ | ΔCoste | Infr. | Notas |
|---|---|---|---|---|---|---|---|---|---|
| H1 | Sáb 14/11, 17:39 | `96bd4ef` | v2 del modo difícil: MPC con previsión propia de precio y CO₂ (regresión por antelación), solar por claridad y margen al descargar | 20,37 | **23,35** | 22,10 % (13.317,9 kg) | 26,25 % (24.936,50 €) | 0 | 2.º de 22 equipos, a 0,02 del 1.º (23,37). Equivalencia: 20,4 en casa ≈ 23,35 en la web |
| H2 | Sáb 14/11, 18:43 | `e8dab4c` | v6: previsor de precio y CO₂ con memoria del train (13 pistas) y blindaje del ataque de robustez (final por calendario solo en agosto, reinicios semanales, lecturas vacías, contador a 0 con solar viva) | 20,66 | **23,70** | 22,58 % (13.607,2 kg) | 26,30 % (24.974,56 €) | 0 | **1.º de 32 equipos** (2.º: 23,50). En casa +0,29 sobre H1; en la web +0,35 |
| H3 | pendiente | `9f7cfc9` | v7: previsor ampliado de consumo y solar (regresión del consumo, noche con el contador congelado, márgenes por cuantiles, cielo despejado en hora solar e interpolado entre meses) | 20,78 | | | | | En reserva; puede saltarse si se sube la v8 |
| H4 | pendiente | `b0d65ee` | v8: la v7 con el margen de seguridad en 1,4 desviaciones típicas (antes 1,0) | 20,83 | | | | | En reserva. Tira la mitad de energía al descargar (2.865 kWh frente a 4.443 en validación) |

Las horas son las que muestra la web, que van en UTC: una hora menos que la hora local.

**Decisión del equipo (sábado por la tarde): las versiones 7 y 8 se guardan en reserva** y no se envían mientras
sigamos primeros con la v6. Ojo: el jurado solo evalúa en el ranking privado entregas enviadas y seleccionadas, así
que la mejor versión tiene que subirse antes del cierre (como tarde, el domingo a primera hora), después de pasarle
la validación rápida, que no gasta cupo.

Las variantes "e" y "c" (vaciar la batería cada semana o en la hora 1.008) **no se envían**. Suben el ranking público
en cualquier caso, porque esa carga se paga en la mitad pública y se usa en la privada, y pueden hundir el privado
(−0,8 a −1,1 en nuestros episodios). No sirven para averiguar cómo encadena el servidor las semanas. En su lugar, el
agente lo detecta solo: si la segunda semana empieza con la batería al 50 % y no como él la dejó, cierra cada semana vacía.

Cómo se relacionan la nota de casa y la de la web (mismo agente):

| Versión | Validación reservada (casa) | Ranking público (web) |
|---|---|---|
| v2 (H1) | 20,37 | 23,35 |
| v6 (H2) | 20,66 | 23,70 |
| v8 (H4) | 20,83 | pendiente |
