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
| H3 | Sáb 14/11, 19:22 | `9f7cfc9` | v7: previsor ampliado de consumo y solar (regresión del consumo, noche con el contador congelado, márgenes por cuantiles, cielo despejado en hora solar e interpolado entre meses) | 20,78 | **24,10** | 22,86 % (13.776,6 kg) | 26,99 % (25.636,04 €) | 0 | |
| H4 | Sáb 14/11, 19:59 | `b0d65ee` | v8: la v7 con el margen de seguridad en 1,4 desviaciones típicas (antes 1,0) | 20,83 | **24,06** | 22,88 % (13.789,2 kg) | 26,79 % (25.442,25 €) | 0 | En casa +0,05 sobre la v7; en la web −0,04 |
| H5 | Sáb 14/11, 21:15 | `7a45e40` | v9: la v8 con la semilla de consumo y solar al empezar cada semana (otra sesión, rama `mejora-score-hard`) | 20,84 | **24,10** | 22,94 % (13.822,8 kg) | 26,82 % (25.468,67 €) | 0 | |
| H6 | Sáb 14/11, 22:40 | `34a0f5f` | v10: la v9 con el margen 1,0 (rama `mejora-score-hard-z10`) | 20,79 | **24,15** | 22,92 % (13.809,7 kg) | 27,02 % (25.665,85 €) | 0 | **2.º de 41 equipos** (1.º: Fanboy & Chum Chum, 24,25). Mejor nota pública nuestra |
| H7 | Dom 15/11, madrugada | `9b75248` | v12: la v10 con el plan que cuenta con la incertidumbre del consumo neto (sin margen fijo) | **20,92** | **24,11** | 22,93 % (13.815,8 kg) | 26,86 % (25.511,18 €) | 0 | En casa gana a la v10 en 6 ventanas de 6 (+0,04 a +0,13); en la web −0,04. Ver "Cómo leer el ranking público" |

| H8 | sin enviar | `3b146a8` | v13: la v12 con el perfil de precio y CO₂ interpolado entre meses según el día | 21,06 | | | | | Gana donde la ventana se aleja del centro del mes (días 1–7: +0,11; validación: +0,14), que es la situación del test |
| H9 | **sin enviar: es la que hay que subir** | `98b7037` | v14: la v13 con los perfiles de sábado y domingo suavizados con los meses vecinos | **21,07** | | | | | Gana o empata a la v13 en 6 ventanas de 6 (media +0,05). Fichero: `entregas/HARD_v14_SUBIR_ESTE.zip` |

Las horas son las que muestra la web, que van en UTC: una hora menos que la hora local. La v11 (margen 0,7 de
septiembre a febrero, rama `mejora-score-hard-v11`) no se integra: en el banco pierde frente a la v10 en las tres
ventanas (validación 20,75 frente a 20,79) y se apoya en suponer qué meses son públicos.

## Cómo leer el ranking público (análisis del domingo de madrugada)

- **El servidor simula como nuestro banco.** El desplegable del modo difícil usa el `CampusBatteryEnv` oficial con
  `forecast_horizon: 3` y la solar ×12, que es lo que hace `scripts/p1_hard.py` (comprobado además con
  `scripts/p1_lab/hard_ataque_oficial.py`).
- **El conjunto público es una mezcla de todo el año**, no las seis primeras semanas. La solar ×12 baja la referencia
  pública un 16,1 % en CO₂ y un 20,0 % en coste (71.816 → 60.255 kg; 118.746 → 94.985 €). En el train, el año entero
  da 16,0 % y 19,5 %; de septiembre a febrero, 12,0 % y 14,9 % (`scripts/p1_lab/hard_publico_referencias.py`). Y una
  nota de 24 solo cuadra con una mezcla anual: en invierno el banco da unos 14 y en verano unos 26.
- **Comparar dos versiones en el público tiene mucho ruido si el público es la mitad de las horas al azar.** Medido
  con los registros hora a hora del banco (`scripts/p1_lab/hard_publico_ruido.py`): v12 frente a v10, desviación de
  0,15 a 0,21 puntos; margen 1,0 frente a 1,4, de 0,08 a 0,10. Con seis semanas enteras sería de 0,02 a 0,04, y
  entonces cuatro de nuestras comparaciones (v7–v6, v8–v7, v9–v8 y v12–v10) quedarían a entre 2 y 5 desviaciones
  de lo que mide el banco. La lectura más sencilla es que el reparto es por horas.
- **Consecuencia.** Las diferencias de la web entre v7, v8, v9, v10 y v12 (de 24,06 a 24,15) y la distancia al líder
  (0,10) están dentro del ruido. Si el privado son las otras horas de la misma simulación, lo que una versión pierde
  por azar en el público lo gana en el privado: manda la nota sobre el episodio completo, que es lo que mide el banco.
- **Confirmado con la web (FAQ y código oficial).** "El rànquing que veieu correspon al 50 % públic de cada setmana
  de test", y `evaluate_results(mask=...)` calcula la nota sobre una máscara de horas de una única simulación. El
  excedente no se paga (`export_price = 0.0`). Según qué mitad de las horas de cada semana sea pública, la
  diferencia entre la v12 y la v10 en nuestro banco va de −0,20 (horas pares) a +0,46 (horas impares), con +0,13
  en el episodio entero (`scripts/p1_lab/hard_publico_mitades.py`): la v12 compra menos en las horas de carga y
  pierde un poco en las de descarga, y el resultado depende de qué horas caigan en cada mitad.
- **Selección para el jurado: las dos mejores por nota del episodio completo, que hoy son la v14 y la v12.** Hay que
  marcarlas a mano en "Selecció Oficial per al Jurat": por defecto el sistema coge las dos mejores del público.
  La v10 (mejor nota pública, 24,15) es la alternativa prudente si se prefiere no depender de este análisis.

Las variantes "e" y "c" (vaciar la batería cada semana o en la hora 1.008) **no se envían**. Suben el ranking público
en cualquier caso, porque esa carga se paga en la mitad pública y se usa en la privada, y pueden hundir el privado
(−0,8 a −1,1 en nuestros episodios). No sirven para averiguar cómo encadena el servidor las semanas. En su lugar, el
agente lo detecta solo: si la segunda semana empieza con la batería al 50 % y no como él la dejó, cierra cada semana vacía.

Cómo se relacionan la nota de casa y la de la web (mismo agente):

| Versión | Validación reservada (casa) | Ranking público (web) |
|---|---|---|
| v2 (H1) | 20,37 | 23,35 |
| v6 (H2) | 20,66 | 23,70 |
| v7 (H3) | 20,78 | 24,10 |
| v8 (H4) | 20,83 | 24,06 |
| v10 (H6) | 20,79 | 24,15 |
| v12 (H7) | 20,92 | 24,11 |
| v14 (H9) | 21,07 | sin enviar |
