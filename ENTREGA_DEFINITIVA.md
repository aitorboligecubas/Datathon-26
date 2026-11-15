# ENTREGA DEFINITIVA · Modo difícil · Equipo `SanHackobos`

**Estas son las dos entregas marcadas para el jurado** (ranking privado del modo difícil, que es el que cuenta para los
premios). Todo lo demás que hay en el repo y en sus ramas son versiones anteriores, pruebas o análisis.

| | Entrega 1 · **FINAL2** | Entrega 2 · **v10 con el arreglo del final del test** |
|---|---|---|
| ZIP | [`entrega/SanHackobos_hard_ENTREGA_1.zip`](entrega/SanHackobos_hard_ENTREGA_1.zip) | [`entrega/SanHackobos_hard_ENTREGA_2.zip`](entrega/SanHackobos_hard_ENTREGA_2.zip) |
| Qué es | MPC con previsión propia de precio, CO₂, consumo y solar; el plan cuenta con la incertidumbre del consumo neto; perfiles de precio y CO₂ interpolados entre meses | La misma base, con margen de seguridad fijo (1,0) en lugar del plan con incertidumbre y sin interpolar los perfiles |
| Código | **Este árbol**: `src/battery/hard.py`, `hard_market.py`, `hard_solar.py` y `models/hard_*.json` (commit `2ba3b8f`) | Commit `34a0f5f` más `results/p1_hard/v10_fin_de_agosto.patch` (4 líneas) |
| Público en la web | 24,06 (CO₂ 22,86 %, coste 26,88 %), 0 infracciones | 24,15 (CO₂ 22,92 %, coste 27,02 %), 0 infracciones |
| Enviada (hora de la web, UTC) | Domingo 15/11, 10:48:09 | Domingo 15/11, 10:49:23 |
| Papel | La mejor en el banco con el calendario real del test | Cobertura: la mejor nota pública y un diseño distinto |

**Confirmado en la web** (historial de `SanHackobos`, 9 envíos): "Selecció Mode Difícil confirmada per l'equip (2/2):
2026-11-15 10:49:23, 2026-11-15 10:48:09". Son estas dos. Los ZIP de `entrega/` son copias byte a byte de los ficheros
subidos (194.490 y 185.918 bytes).

## Por qué estas dos

- **FINAL2.** Su base gana a la v10 en 9 de 9 ventanas del banco con el calendario real del test (+0,13 de media) y en
  6 de 6 pruebas con datos deformados. En el público sale 0,09 por debajo, pero el público es la mitad de las horas de
  cada semana y la organización avisó de que cuenta el privado.
- **La v10 arreglada.** Cubre el caso contrario: que el público acierte.
- **El arreglo del final del test, en las dos.** El train de agosto acaba el 16/08 a las 22:00, 168 horas antes del
  23/08 a las 22:00, así que la última semana del test puede ser 16–23/08 y no 25–31/08. Ahora la última semana dura 168
  horas desde su primera hora. Con 25–31/08 no cambia ninguna decisión (en la web salen idénticas hasta el céntimo a sus
  versiones anteriores); con 16–23/08 dejan de quedarse con unos 4.000 kWh sin usar: +0,124 y +0,122 puntos.

## Cómo reproducirlo

```bash
python -m pytest -q                          # 43 tests
python scripts/build_submission.py --hard    # genera dist/hard/submission.zip, idéntico byte a byte a la entrega 1
python scripts/p1_hard.py                    # validación reservada del modo difícil ("agente actual" = FINAL2)
python scripts/p1_lab/hard_calendario_versiones.py val   # las versiones con el calendario real del test
python scripts/p1_lab/hard_fin_agosto.py <carpeta con un agent.py anterior>   # el arreglo en los dos calendarios de agosto
```

## Qué NO es la entrega definitiva

- Las entregas anteriores de la web: v6 a v14 (la v14 es la "FINAL" sin el arreglo), la prueba con margen 0,8 y las
  pruebas con el perfil mezclado (23,66 y 23,41).
- Las ramas `final` (la FINAL sin el arreglo), `p2-datos` (la v15), `revision-*` y `mejora-score-hard-*`.
- El modo estándar (6,43 en el público): la organización avisó de que solo el modo difícil cuenta para los premios.

Toda la historia, con lo que se descartó y por qué: [`docs/envios.md`](docs/envios.md) y [`docs/decisiones.md`](docs/decisiones.md).
