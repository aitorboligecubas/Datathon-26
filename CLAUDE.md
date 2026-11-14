# CLAUDE.md — Datathon FME 2026 · Reto UPC Sostenible (batería del campus)

Los Claude Code de todo el equipo leen este fichero al arrancar. Cada persona trabaja con su propio Claude,
en su portátil y en su propia rama. Aquí está lo que todos tienen que saber: el reto, quién es dueño de cada fichero,
los contratos entre módulos y las reglas. Si algo de aquí cambia, lo cambia el integrador por PR y avisa al equipo.

Responde siempre en español. Plazo de entrega: **domingo 15/11 a las 12:00**. Congelación del código: domingo a las 9:30.

## El reto en 30 segundos (verificado con el material oficial)

- `BatteryAgent.act(obs) -> float` devuelve la potencia de la batería en kW: > 0 carga, < 0 descarga.
  Se llama una vez por hora durante el test: los últimos 7 días de cada mes, **~1.700 h** según las slides
  (2.016 si no faltasen datos), sin reinicios. Cuando quedan menos de 24 h, la previsión llega recortada.
- Batería: 2.000 kWh, ±500 kW, η = √0,9 en cada sentido (90 % ida y vuelta) y carga inicial de 1.000 kWh.
- Red = demanda − solar + batería. Si es > 0, compramos al precio PVPC y emitimos CO₂ del mix.
  Si es ≤ 0, el excedente se vierte sin cobrar nada.
- `Score = max(0, 0,70·ΔCO₂% + 0,30·ΔCoste% − pen·infracciones)`, con los porcentajes respecto a no tener batería.
  pen = 0,20 en `environment.py`, y 1,00 en el enunciado y en las slides. Nuestro objetivo es 0 infracciones.
- `obs` incluye:
  - `preus_properes_24h` y `co2_properes_24h`, con las 24 h **desde la hora actual** (son exactos);
  - `noves_dades_5min = {ultim_consum_kw, ultima_solar_kw}`, la demanda y la solar de la hora anterior.
- Entrega: un ZIP de ≤ 25 MB con `agent.py` y los artefactos (.pkl/.json) en la raíz. La simulación entera
  tiene que durar menos de 60 s. Hay 10 envíos al día, que no se gastan si el envío falla. La web también tiene
  un **dry-run gratis e ilimitado (48 pasos)**: usadlo antes de gastar un envío. El leaderboard público cuenta
  el 50 % y el privado, el otro 50 %.
- **El jurado decide de forma decisiva** con la presentación, el razonamiento y la justificación.
  Cada decisión tiene que tener un número detrás (`docs/decisiones.md`).

Material oficial: el ZIP del reto descomprimido en `oficial/`, que no se sube porque el repo es público.
Lo más importante: `oficial/docs/ENUNCIAT.md`, `oficial/docs/GUIA_VARIABLES.md`, `oficial/starter_kit/environment.py`
y `oficial/starter_kit/tutorial.ipynb`. Resumen y dudas abiertas: `docs/reto.md`. Contexto del evento: `docs/contexto-chat.md`.

## Lo que ya sabemos de los datos reales (sáb 14/11)

- La **solar es minúscula**: 26 kW de media y 144 kW como máximo, frente a ~1.100 kW de consumo.
  La red casi nunca baja de 500 kW (0,5 % de las horas) y nunca hay excedente.
  → Prever la demanda y la solar apenas cambia las decisiones. El juego es **mover energía en el tiempo** según
  `w_t = 0,7·co2_t/co2_ref + 0,3·precio_t/coste_ref`, y precio y CO₂ a 24 h nos los dan exactos.
- La batería (2 MWh) es el 7 % del consumo diario (27 MWh), así que el score máximo es pequeño.
  En validación, el `oracle` con información perfecta saca 6,12 y nuestro MPC, **6,08 (99,3 % del techo)**.
  **El margen en el leaderboard es pequeño: la presentación y el análisis deciden.**
- Faltan datos: noviembre de 2025 entero, el train acaba el 16/08/2026 y hay 15 horas con consumo 0.

## Estrategia actual (v0, funciona de punta a punta)

Usamos un MPC. Cada hora prevemos la demanda y la solar de las próximas 24 h. Con eso resolvemos un LP
(HiGHS, con `scipy.optimize.linprog`) que minimiza `Σ w_t·compra_t` con la física de la batería, aplicamos
solo la primera hora y repetimos. Como η² = 0,9, el LP solo mueve energía si la hora de destino es al menos
un 11 % "peor". Cuando la previsión llega recortada (fin de los datos), la carga final vale 0 y el LP la gasta
(5,97 → 6,08). Hay un respaldo greedy si el LP falla o vamos justos de tiempo.

Referencias en `eval.py --agent all`:
- `nothing`: no usa la batería.
- `greedy`: reglas simples.
- `mpc`: nuestro agente.
- `oracle`: el mismo LP con información perfecta. Es el techo teórico.

## Reparto: quién es dueño de qué (Opción B)

| Rol | Rama | Ficheros que SOLO edita esta persona |
|---|---|---|
| **P1 · Optimizador** | `p1-optimizador` | `src/battery/policy.py`, `optimizer.py`, `safety.py`, `baselines.py`, `tests/test_safety.py`, `tests/test_agent.py` |
| **P2 · Previsión y datos** | `p2-prevision` | `src/battery/forecaster.py`, `data.py`, `synthetic.py`, `scripts/train_forecaster.py`, `models/`, `tests/test_forecaster.py` |
| **P3 · Validación y relato** | `p3-validacion` | `src/battery/sim.py`, `scripts/calibrate_sim.py`, `analysis/`, `presentation/`, `docs/decisiones.md`, `tests/test_sim.py` |
| **Integrador** (P3, o una 4.ª persona) | — | `CLAUDE.md`, `src/battery/params.py`, `obs.py`, `adapter.py`, `eval.py`, `scripts/build_submission.py`, `tests/test_adapter.py`, `tests/test_bundle.py`, `docs/reto.md`, `docs/envios.md`, `docs/equipo.md`, `.github/`, `requirements*.txt`, `README.md` |

Quién es quién: ver `docs/equipo.md`.

**Regla de oro: no edites ficheros de otro rol.** Si necesitas un cambio en uno, no lo hagas. Escribe en tu PR
(sección "Peticiones a otros roles") o en un issue qué cambio y por qué, y díselo a tu humano para que avise al dueño.
Lo que sí puedes hacer es añadir líneas a `results/experiments.csv` (vía `eval.py --log`) o crear ficheros nuevos dentro de tu zona.

## Contratos entre módulos (no se rompen sin acordarlo antes)

```text
adapter.from_official(obs_dict) -> Obs                    # único sitio que conoce el formato oficial
Obs(hour, weekday, soc_kwh, price[<=24], co2[<=24], load_prev_kw, pv_prev_kw, timestamp)
    price en €/kWh, co2 en kg CO2/kWh, [0] = hora actual

Forecaster(prior: dict | None)                            # P2 -> P1
    .update(obs)                                          # una vez por hora, antes de forecast
    .forecast(obs, h) -> (load_kw[h], pv_kw[h])           # np.ndarray, kW, >= 0, [0] = hora actual, < 2 ms

optimizer.plan(soc, load, pv, price, co2, w_co2, w_cost, terminal_value, p) -> acciones_kw[H]   # P1
safety.clip_action(a_kw, soc_kwh) -> float válido          # P1, garantiza 0 infracciones
policy.BatteryAgent().act(obs_dict) -> float kW           # P1, lo que carga el evaluador

data.load() -> DataFrame[timestamp, load_kw, pv_kw, price_eur_kwh, co2_kg_kwh]   # P2, horario
data.validation_split(df) / train_split(df)                # validación = últimas 168 h de cada mes

sim.simulate(agent, df) -> SimResult(log, totals)          # P3, idéntico a environment.py
sim.score(totals, baseline_totals(df)) -> {score, d_co2_pct, d_cost_pct, infractions}
    log hora a hora: sim.LOG_COLUMNS

models/forecaster.json, models/objective_refs.json (+ .pkl si hace falta) -> van en la raíz del ZIP
```

## Reglas para el código que va en `dist/agent.py`

Esto aplica a `params`, `obs`, `adapter`, `safety`, `forecaster`, `optimizer` y `policy`.
`build_submission.py` lo comprueba todo y además pasa el `check_submission.py` oficial.

- Solo se pueden importar `numpy`, `pandas`, `scipy`, `sklearn`, `joblib`, `xgboost`, `lightgbm`, `math`, `random`,
  `datetime`, `collections`, `itertools`, `json`, `pathlib`, `typing`, `dataclasses`, `functools`, `heapq`,
  `bisect`, `re`, `copy` y `pickle`. Están prohibidos `os`, `sys`, `subprocess`, `importlib`, `inspect`, etc.
- El escáner del servidor rechaza cualquier llamada a `.stack(...)` (también `np.stack`, mejor `np.vstack`),
  así como `eval`, `exec`, `compile`, `globals`, `locals`, `vars` y `__import__`.
- Entre módulos, imports relativos (`from .optimizer import plan`). El empaquetador los quita.
- Dos módulos no pueden definir el mismo nombre a nivel de módulo, y cada librería se importa igual en todos.
- Compatible con Python 3.9 o superior: `Optional[...]`, no `X | None`.
- Nada de `print` ni de escribir ficheros. Los artefactos se leen con `Path(__file__).parent`.
- El agente nunca lanza una excepción: ante cualquier error, devuelve una acción segura.
- Tiempo: `eval.py` proyecta el tiempo a 2.016 h, que tiene que quedar por debajo de 40 s (el límite oficial es 60 s).

`sim.py`, `data.py`, `baselines.py`, `synthetic.py`, `eval.py`, `scripts/` y `analysis/` no se empaquetan:
ahí puedes usar lo que quieras.

## Comandos

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q                         # tests (también los pasa la CI en cada PR)
python eval.py                              # nuestro agente en validación (datos oficiales si hay oficial/)
python eval.py --agent all                  # nothing / greedy / mpc / oracle
python eval.py --fc-noise 0.1               # robustez si las previsiones de precio/CO2 fallaran
python eval.py --log "qué he cambiado"      # deja constancia en results/experiments.csv
python eval.py --save-hourly                # log hora a hora en results/hourly/ (para gráficas)
python scripts/calibrate_sim.py             # nuestro sim frente al environment.py oficial (tienen que coincidir)
python scripts/train_forecaster.py          # regenera models/ con el train (P2)
python scripts/build_submission.py          # dist/agent.py + dist/submission.zip, prueba aislada y check oficial
python eval.py --agent dist                 # evalúa el agent.py empaquetado
```

`data/processed/hourly.csv` se genera solo a partir de `oficial/` la primera vez. Sin `oficial/` (por ejemplo, en la CI)
se usan datos sintéticos, que sirven para probar el circuito y **no para tomar decisiones**.

## Flujo de trabajo con git (detalle en docs/equipo.md)

1. Trabaja siempre en tu rama (`p1-optimizador`, `p2-prevision` o `p3-validacion`). **Nunca hagas push a `main`.**
2. Antes de empezar y después de cada merge: `git fetch origin && git merge origin/main`.
3. Haz PRs pequeñas y frecuentes, como mínimo una por cada punto de sincronización. Antes de abrir una:
   - `python -m pytest -q` en verde.
   - `python eval.py --log "..."`. Pega la tabla en la PR y compárala con `main`.
   - Si has tocado módulos empaquetados: `python scripts/build_submission.py` en verde.
   - Rellena la plantilla de la PR. El integrador revisa y hace el merge con "Create a merge commit".
4. "Me mejora" solo vale con `eval.py` sobre la validación con datos oficiales. Si una idea no mejora,
   apúntala igualmente en `docs/decisiones.md` mediante P3, porque al jurado también le interesa lo descartado.
5. Los cambios grandes de estrategia los decide el equipo. Claude propone; tu humano decide.

## Cosas que Claude NO debe hacer

- Editar ficheros de otro rol, hacer push a `main` o un merge de PRs (eso es del integrador).
- Subir `oficial/`, `data/` ni nada de los datos oficiales (el repo es público).
- Añadir librerías no permitidas al código empaquetado.
- Cambiar los contratos de arriba sin acordarlo.
- Afirmar que algo mejora sin un número de `eval.py`.
