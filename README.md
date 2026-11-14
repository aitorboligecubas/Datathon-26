# Datathon FME 2026 · Reto UPC Sostenible: control de la batería del campus

Agente que decide, hora a hora, cuánto carga o descarga la batería de 2.000 kWh del campus para reducir
el CO₂ (70 %) y el coste (30 %) de la electricidad comprada a la red.

**Método:** control predictivo (MPC). Cada hora prevemos la demanda y la producción solar, resolvemos un
programa lineal a 25 h con la previsión de precio y CO₂ y aplicamos la primera decisión.
Lo comparamos con el óptimo teórico con información perfecta.

## Empezar

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
python eval.py --agent all
```

Datos oficiales: descomprimid el ZIP del reto en la raíz y renombrad la carpeta a `oficial/` (no se sube a git).
Sin ellos, todo funciona con datos sintéticos.

**Resultado en validación (últimas 168 h de cada mes del train, datos oficiales):** MPC 5,97 puntos
(ΔCO₂ 5,62 %, ΔCoste 6,78 %, 0 infracciones, 4 s) frente a 6,12 del óptimo con información perfecta.

## Estructura

```text
src/battery/        código del agente (se empaqueta en un solo agent.py) + simulador y datos
  params, obs, adapter      formato oficial y constantes             (integrador)
  policy, optimizer, safety MPC, LP, límites físicos, BatteryAgent    (P1)
  forecaster, data          previsión de demanda y solar, carga de datos (P2)
  sim                       simulador local y score                   (P3)
  baselines, synthetic      referencias (nothing/greedy/oracle) y datos de prueba
eval.py             único comando de evaluación
scripts/            build_submission.py (genera dist/submission.zip), train_forecaster.py, calibrate_sim.py
models/             artefactos que van en el ZIP
analysis/, presentation/    gráficas y pitch (P3)
docs/               reto, equipo, prompts de arranque, decisiones, envíos
```

## Trabajo en equipo

Cada persona trabaja con su propio Claude Code en su portátil, en su rama, con PRs pequeñas a `main`:
- [`CLAUDE.md`](CLAUDE.md): contexto compartido, reparto de ficheros y contratos.
- [`docs/equipo.md`](docs/equipo.md): preparación, flujo de git y puntos de sincronización.
- [`docs/prompts-arranque.md`](docs/prompts-arranque.md): el primer mensaje para cada Claude.
- [`docs/registro-montaje.md`](docs/registro-montaje.md): todo lo que se hizo al montar el repo y por qué.
