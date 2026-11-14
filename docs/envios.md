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

| 2 | pendiente | — | v2: semana sin datos de contador, primera hora de cada semana, adaptador con huecos, modelos incrustados | 6,09 | | | | | En semanas normales decide igual que el envío 1. Si la mitad pública incluye una semana con el contador a 0, debería subir; si no, quedará en 6,43 |

Referencia de la mitad pública sin batería (1.008 h): 71.816 kg de CO₂ y 118.746 €, es decir, 71,2 kg/h y 117,8 €/h.
Los datos del train dan unos 92 kg/h y 157 €/h: la referencia pública es un 20–25 % más baja. Cuadra con que la
mitad pública sean las seis primeras semanas (septiembre a febrero), con noviembre a cero y Navidad con poco consumo
(estimación con los datos del train: 68–76 kg/h y 119–131 €/h).

Lectura del leaderboard tras el envío 1 (sábado 13:10, 17 equipos): 15 equipos en 6,43. Con más decimales (calculados
con los kg y € de la tabla): líder 6,43805; después 6,43145, 6,43142, 6,43141 y nosotros 6,43138.
