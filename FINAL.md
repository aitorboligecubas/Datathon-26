# Versión FINAL del modo difícil (antes llamada "v14" en la rama `p1-optimizador`)

Esta rama (`final`) es el commit `98b7037` de `p1-optimizador`, sin cambios en el código, con otro nombre para que no
se confunda con otras "v14". **No es** "la v10 con el margen 1,4 de marzo a agosto".

## Qué es

La v10 con dos cambios:
1. **El plan cuenta con la incertidumbre del consumo neto de cada hora** (antes, un margen fijo). Es la v12 de `p1-optimizador`, commit `9b75248`.
2. **Los perfiles de precio y CO₂ se interpolan entre meses según el día**, y los de sábado y domingo se suavizan con los meses vecinos (commits `3b146a8` y `98b7037`).

Enviada a la web el domingo 15/11 por la mañana con el nombre `SanHackobos`: **24,06** en el público (CO₂ 22,86 %, coste 26,88 %), 0 infracciones.

## Ficheros

- Agente: `src/battery/hard.py`, `hard_market.py`, `hard_solar.py` y los modelos `models/hard_market.json` y `models/hard_solar.json`.
- ZIP: `entrega/SanHackobos_hard_FINAL.zip`, generado en esta rama con `python scripts/build_submission.py --hard`
  (prueba aislada correcta y `check_submission.py` oficial: VÁLIDA).

## Cómo medirla

```bash
python scripts/p1_hard.py                    # validación reservada: "agente actual" = FINAL; "plan con margen fijo (v10)" = v10
python scripts/p1_hard.py --split dev        # días 8-14
python scripts/p1_lab/hard_calendario_versiones.py val    # con el calendario real (está en la rama p1-optimizador)
```

## Frente a la v10

| Medida | v10 | FINAL | Diferencia |
|---|---|---|---|
| Validación reservada (últimas 168 h de cada mes) | 20,785 | 21,073 | +0,29 |
| Calendario real, 9 ventanas (6 de P1 y 3 de P2) | — | — | gana en 9 de 9, +0,13 de media |
| Datos deformados, 6 escenarios (otro año, precios, solar, consumo) | — | — | gana en 6 de 6 |
| Público de la web | 24,15 | 24,06 | −0,09 |

El público es la mitad de las horas de cada semana y la organización ha dicho que cuenta el privado. Detalle de las
medidas de P2: `analysis/hard_v15.md` en la rama `p2-datos`; las de P1: `docs/envios.md` en `p1-optimizador`.

**Para el jurado: nombre `SanHackobos`, entregas FINAL y v10.**
