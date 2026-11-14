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
| H2 | pendiente | `dc7cb16` | v4: festivos, semana sin contador, el plan cuenta con el margen | 20,55 | | | | | |
| H3 | pendiente | `dc7cb16` | v4e: como la v4, pero vacía la batería al final de cada semana | — | | | | | Si saca más que la v4, cada semana se simula por separado |
| H4 | pendiente | `dc7cb16` | v4c: como la v4, pero vacía la batería en la hora 1.008 | — | | | | | Si saca más que la v4, el conjunto público se simula solo |
