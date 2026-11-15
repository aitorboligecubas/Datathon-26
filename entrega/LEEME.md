# ENTREGA DEFINITIVA: las dos entregas del modo difícil marcadas para el jurado (equipo `SanHackobos`)

| Fichero | Qué es | Código | Público en la web | Cómo reconocerla en la web |
|---|---|---|---|---|
| `SanHackobos_hard_ENTREGA_1_FINAL2.zip` | **FINAL2**: el plan que cuenta con la incertidumbre del consumo neto, los perfiles de precio y CO₂ interpolados entre meses y el final del test por duración de la semana | rama `p1-optimizador`, commit `2ba3b8f` | 24,06 (13.772,5 kg; 25.525,83 €; 0 infracciones) | el 24,06 de hora más tardía (domingo, ~10:47 UTC) |
| `SanHackobos_hard_ENTREGA_2_v10_fin_agosto.zip` | **La v10 con el mismo arreglo del final del test**: semilla de consumo y solar al empezar cada semana y margen fijo 1,0 | commit `34a0f5f` + `results/p1_hard/v10_fin_de_agosto.patch` | 24,15 (13.809,7 kg; 25.665,85 €; 0 infracciones) | el 24,15 de hora más tardía (domingo, ~10:52 UTC) |

## Por qué estas dos

- **FINAL2 es la mejor en el banco con el calendario real del test:** su base (la FINAL, commit `98b7037`) gana a la v10 en
  9 de 9 ventanas (+0,13 de media) y en 6 de 6 escenarios con datos deformados. En el público sale 0,09 por debajo de la
  v10, pero el público es la mitad de las horas de cada semana y la organización ha dicho que cuenta el privado.
- **La v10 es la cobertura:** es la mejor nota pública y es estructuralmente distinta (margen fijo en lugar del plan con
  incertidumbre). Cubre el caso de que el público acierte.
- **El arreglo del final del test no puede restar.** El train de agosto acaba el 16/08 a las 22:00, 168 horas antes del
  23/08 a las 22:00: la última semana del test puede ser 16–23/08 y no 25–31/08. Con 25–31/08 las dos entregas deciden
  igual que sus versiones anteriores (0 acciones distintas; en la web salen idénticas hasta el céntimo). Con 16–23/08
  dejan de quedarse con unos 4.000 kWh sin usar: +0,124 y +0,122 puntos.

## Comprobaciones de cada ZIP

Validador oficial (`check_submission.py`): VÁLIDA. Prueba aislada del empaquetador: mismas acciones que el código.
Frente a su versión anterior: diferencia 0,0 en las 1.680 horas de la validación anteriores a agosto, 0 infracciones.
Tests: 43 en verde (FINAL2) y 40 en verde (árbol de la v10).

Detalle y todo lo descartado: `docs/envios.md` (secciones "FINAL2" y "Selección definitiva para el jurado").
