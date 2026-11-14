# CLAUDE.md — Datathon FME 2026 · Reto UPC Sostenible (batería del campus)

Este fichero lo leen al arrancar los Claude Code de todo el equipo. Cada persona trabaja con su
propio Claude, en su portátil, en su propia rama. Aquí está lo que todos tienen que saber:
el reto, quién es dueño de cada fichero, los contratos entre módulos y las reglas de trabajo.
Si algo de este fichero cambia, lo cambia el integrador por PR y avisa al equipo.

Responde siempre en español. Plazo de entrega: **domingo 15/11 a las 12:00**. Congelación del código: domingo a las 9:30.

## El reto en 30 segundos

- `BatteryAgent.act(obs) -> float` devuelve la potencia de la batería en kW: > 0 carga, < 0 descarga.
  Se llama una vez por hora durante 2.016 h, que son 12 semanas de test (la última de cada mes) sin reinicios.
- Batería: 2.000 kWh, ±500 kW, η = √0,9 en cada sentido (90 % ida y vuelta) y carga inicial de 1.000 kWh.
- Red = demanda − solar + batería. Si es > 0, compramos al precio PVPC y emitimos CO₂ del mix.
  Si es < 0, el excedente se paga a 0 € o a 0,04 €/kWh (está por VERIFICAR).
- `Score = max(0, 0,70·ΔCO₂% + 0,30·ΔCoste% − pen·infracciones)`, con pen = 0,20 o 1,00 (está por VERIFICAR).
  Los porcentajes se calculan respecto a no usar la batería. **El CO₂ pesa más que el coste.**
- Infracción: pedir más carga de la que cabe, más descarga de la que queda o más de 500 kW.
  Tolerancia cero: toda acción sale de `battery.safety.clip_action`.
- Ni la demanda ni la solar de la hora actual vienen en `obs`: hay que preverlas.
  Sí vienen el precio y el CO₂ de las próximas 24 h, y los sensores de la última hora (`noves_dades_5min`).
- Entrega: un ZIP de ≤ 25 MB con `agent.py` y los artefactos (.pkl/.json) en la raíz. La simulación entera tiene
  que durar menos de 60 s. Hay 10 envíos al día. El leaderboard público cuenta el 50 % y el privado, el otro 50 %.
- **El servidor solo carga `agent.py`**: no puede importar otros ficheros, y ni `sys`, ni `os`, ni `importlib`,
  ni `time` están permitidos. Por eso el código vive en módulos dentro de `src/battery/` y
  `scripts/build_submission.py` los junta en `dist/agent.py`.
- **El jurado decide de forma decisiva** con la presentación, el razonamiento y la justificación.
  Cada decisión tiene que tener un número detrás (`docs/decisiones.md`).

Detalle completo y la lista de cosas por VERIFICAR: `docs/reto.md`. Contexto del evento: `docs/contexto-chat.md`.

## Estrategia actual (v0, ya funciona de punta a punta)

Usamos un MPC. Cada hora prevemos la demanda y la solar de las próximas 25 h. Con eso resolvemos un LP
(HiGHS, con `scipy.optimize.linprog`) que minimiza `Σ (0,7·co2/co2_ref + 0,3·precio/coste_ref)·compra`
con la física de la batería, aplicamos solo la primera hora y repetimos. Como η² = 0,9, el LP solo mueve energía
de una hora a otra si la de destino es al menos un 11 % "peor". Hay respaldo greedy si el LP falla o vamos
justos de tiempo.

Referencias en `eval.py --agent all`:
- `nothing`: no usa la batería (score 0).
- `greedy`: reglas simples.
- `mpc`: nuestro agente.
- `oracle`: el mismo LP con información perfecta. Es el techo teórico: ningún agente real lo supera.

## Reparto: quién es dueño de qué (Opción B)

| Rol | Rama | Ficheros que SOLO edita esta persona |
|---|---|---|
| **P1 · Optimizador** | `p1-optimizador` | `src/battery/policy.py`, `optimizer.py`, `safety.py`, `baselines.py`, `tests/test_safety.py`, `tests/test_agent.py` |
| **P2 · Previsión y datos** | `p2-prevision` | `src/battery/forecaster.py`, `data.py`, `synthetic.py`, `scripts/train_forecaster.py`, `models/`, `tests/test_forecaster.py` |
| **P3 · Validación y relato** | `p3-validacion` | `src/battery/sim.py`, `analysis/`, `presentation/`, `docs/decisiones.md`, `tests/test_sim.py` |
| **Integrador** (P3, o una 4.ª persona) | — | `CLAUDE.md`, `src/battery/params.py`, `obs.py`, `adapter.py`, `eval.py`, `scripts/build_submission.py`, `tests/test_adapter.py`, `tests/test_bundle.py`, `docs/reto.md`, `docs/envios.md`, `docs/equipo.md`, `.github/`, `requirements*.txt`, `README.md` |

Quién es quién: ver `docs/equipo.md`.

**Regla de oro: no edites ficheros de otro rol.** Si necesitas un cambio en uno, no lo hagas. Escribe en tu PR
(sección "Peticiones a otros roles") o en un issue qué cambio y por qué, y díselo a tu humano para que avise al dueño.
Lo que sí puedes hacer es añadir `results/experiments.csv` (vía `eval.py --log`) o crear ficheros nuevos dentro de tu zona.

## Contratos entre módulos (no se rompen sin acordarlo antes)

```text
adapter.from_official(obs_dict) -> Obs                    # único sitio que conoce el formato oficial
Obs(hour, weekday, soc_kwh, price[25], co2[25], load_prev_kw, pv_prev_kw, timestamp)
    price en €/kWh, co2 en kg CO2/kWh, [0] = hora actual, [1:] = 24 h siguientes

Forecaster(prior: dict | None)                            # P2 -> P1
    .update(obs)                                          # una vez por hora, antes de forecast
    .forecast(obs, h) -> (load_kw[h], pv_kw[h])           # np.ndarray, kW, >= 0, [0] = hora actual, < 2 ms

optimizer.plan(soc, load, pv, price, co2, w_co2, w_cost, terminal_value, p) -> acciones_kw[H]   # P1
safety.clip_action(a_kw, soc_kwh) -> float válido          # P1, garantiza 0 infracciones
policy.BatteryAgent().act(obs_dict) -> float kW           # P1, lo que carga el evaluador

data.load() -> DataFrame[timestamp, load_kw, pv_kw, price_eur_kwh, co2_kg_kwh]   # P2, horario
data.validation_split(df) / train_split(df)                # validación = últimas 168 h de cada mes

sim.simulate(agent, df) -> SimResult(log, totals)          # P3, imita a starter_kit/environment.py
sim.score(totals, baseline_totals(df)) -> {score, d_co2_pct, d_cost_pct, infractions}
    log hora a hora: t, timestamp, hour, weekday, load_kw, pv_kw, price_eur_kwh, co2_kg_kwh,
    action_req_kw, action_kw, infraction, soc_kwh, grid_kw, import_kw, export_kw, cost_eur, co2_kg

models/forecaster.json, models/objective_refs.json (+ .pkl si hace falta) -> van en la raíz del ZIP
```

## Reglas para el código que va en `dist/agent.py`

Esto aplica a `params`, `obs`, `adapter`, `safety`, `forecaster`, `optimizer` y `policy`.
`build_submission.py` lo comprueba y falla si no se cumple.

- Solo se pueden importar `numpy`, `pandas`, `scipy`, `sklearn`, `joblib`, `xgboost`, `lightgbm`, `math`, `datetime`,
  `collections`, `itertools`, `random`, `json`, `pathlib` y `typing`.
  Eso deja fuera `from __future__`, `dataclasses`, `functools`, `time`, `os`, `sys` y `warnings`.
- Entre módulos, imports relativos (`from .optimizer import plan`). El empaquetador los quita.
- Dos módulos no pueden definir el mismo nombre a nivel de módulo. Usa nombres específicos (`_lp_structure`, no `_helper`).
- La misma librería se importa igual en todos los módulos (`import numpy as np`, `import scipy.sparse as sp`).
- Compatible con Python 3.9 o superior: `Optional[...]`, no `X | None`.
- Nada de `print` ni de escribir ficheros. Los artefactos se leen de la carpeta de `agent.py`.
- El agente nunca lanza una excepción: ante cualquier error, devuelve una acción segura.
- Tiempo: `eval.py` proyecta el tiempo a 2.016 h, que tiene que quedar por debajo de 40 s (el límite oficial es 60 s).

`sim.py`, `data.py`, `baselines.py`, `synthetic.py`, `eval.py`, `scripts/` y `analysis/` no se empaquetan:
ahí puedes usar lo que quieras.

## Comandos

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q                         # tests (también los pasa la CI en cada PR)
python eval.py                              # nuestro agente en validación
python eval.py --agent all                  # nothing / greedy / mpc / oracle
python eval.py --fc-noise 0.1               # robustez si las previsiones de precio/CO2 fallan
python eval.py --log "qué he cambiado"      # deja constancia en results/experiments.csv
python eval.py --save-hourly                # log hora a hora en results/hourly/ (para gráficas)
python scripts/train_forecaster.py          # regenera models/ (P2)
python scripts/build_submission.py          # genera dist/agent.py + dist/submission.zip y los prueba aislados
python eval.py --agent dist                 # evalúa el agent.py empaquetado
```

Datos: el ZIP oficial va descomprimido en `starter_kit/`, que no se sube porque el repo es público.
Mientras no exista `data/processed/hourly.csv` (lo genera P2), todo funciona con datos sintéticos. Sirven para
probar el circuito, **no para tomar decisiones**.

## Flujo de trabajo con git (detalle en docs/equipo.md)

1. Trabaja siempre en tu rama (`p1-optimizador`, `p2-prevision` o `p3-validacion`). **Nunca hagas push a `main`.**
2. Antes de empezar y después de cada merge: `git fetch origin && git merge origin/main`.
3. Haz PRs pequeñas y frecuentes, como mínimo una por cada punto de sincronización. Antes de abrir una:
   - `python -m pytest -q` en verde.
   - `python eval.py --log "..."`. Pega la tabla en la PR y compárala con `main`.
   - Si has tocado módulos empaquetados: `python scripts/build_submission.py` en verde.
   - Rellena la plantilla de la PR. El integrador revisa y hace el merge con "Create a merge commit".
4. "Me mejora" solo vale con `eval.py` sobre la validación con datos oficiales. Si una idea empeora el score,
   apúntala igualmente en `docs/decisiones.md` mediante P3, porque al jurado también le interesa lo descartado.
5. Los cambios grandes de estrategia los decide el equipo. Claude propone; tu humano decide.

## Cosas que Claude NO debe hacer

- Editar ficheros de otro rol, hacer push a `main` o un merge de PRs (eso es del integrador).
- Subir `starter_kit/`, `data/` ni nada de los datos oficiales (el repo es público).
- Añadir librerías no permitidas al código empaquetado.
- Cambiar los contratos de arriba sin acordarlo, ni la fórmula del score sin haberla verificado contra `environment.py`.
- Afirmar que algo mejora sin un número de `eval.py`.
