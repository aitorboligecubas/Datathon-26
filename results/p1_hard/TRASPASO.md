# Traspaso: estado final del modo difícil (domingo 15/11, ~11:20 hora local)

## Decisión: entregar la v10
- Equipo a dar al jurado: **"SanHackobos"**. Entrega a evaluar: **la v10** (enviada el sábado 22:40, 24,15 en el público,
  CO2 22,92 %, euros 27,02 %). ZIP: `dist/hard/submission.zip` construido desde la rama `mejora-score-hard-z10`.
- Comprobad en la web que la entrega seleccionada de "SanHackobos" es esa y NO la v13 (23,66) ni la v12+truco (23,41).
- Lo que cuenta es el ranking PRIVADO (aviso de la organización). No perseguir el público.

## Por qué la v10
- v10 = semilla de consumo y solar al empezar cada semana + margen de seguridad 1,0. Nada que haya fallado en datos reales.
- Descartadas: la mezcla del perfil de mercado (v12/v13) hundió el público real dos veces; el vaciado a fin de febrero
  (truco de la hora 1.008) baja el privado; margen < 1,0 hundió el público.
- v14 (margen 1,4 solo de marzo a agosto) frente a v10, solo meses del privado, 12 claves: +0,012 de media, peor -0,044,
  pierde en 4: NO pasa el criterio (ruido).

## Revisión con subagentes (en curso al escribir esto)
Cuatro revisores partieron de `revision-base` (v10 + comparador) y suben a su rama SOLO si cumplen el criterio:
`revision-auditoria` (fallos de la v10 en las semanas del privado), `revision-solar` (consumo/solar y márgenes en verano),
`revision-mercado` (previsión de CO2), `revision-decision` (última semana, transiciones, tope de descarga).
Si alguna de esas ramas existe en GitHub, revisar su commit y repetir la medida:
`python scripts/p1_lab/mejora_privado.py <cands.py> --procs 4` (meses del privado y del público, 10 ventanas + 2 episodios).

Criterio para aceptar un cambio: privado media >= +0,02, pierde (< -0,005) en 2 claves como mucho, peor >= -0,03;
público media >= -0,01; 0 infracciones; tests (`python -m pytest -q`) y `python scripts/build_submission.py --hard` en verde;
mecanismo explicable. Si no hay rama o no cumple: se queda la v10. Con poco tiempo, NO cambiar la entrega.

Todo lo probado, con números: `results/p1_hard/mejora_score_notas.md` (ramas mejora-score-hard-*).
