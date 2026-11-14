# Registro del montaje del repo (sábado 14/11/2026)

Este documento explica con detalle todo lo que se hizo en la sesión de Claude Code que montó este repositorio.
Incluye qué se ha construido, por qué, cómo se ha comprobado, qué resultados da y qué falta.
Si eres un miembro del equipo o su Claude, lee primero `CLAUDE.md`. Este fichero es el "por qué" y el "cómo se llegó aquí".

---

## 1. Punto de partida

- **Petición:** montar el repo del reto de la batería (UPC Sostenible) para trabajar con la **Opción B**:
  cada miembro del equipo con su propio Claude Code en su portátil, sobre un repo de GitHub compartido, con una rama
  por persona, PRs pequeñas y frecuentes a `main` y una persona integradora. La prioridad era dejarlo todo
  preparado para que **tres Claudes en tres portátiles** trabajen en paralelo sin pisarse.
- **Repo:** `aitorboligecubas/Datathon-26`. Solo tenía `retos-datathon-fme-2026.md` (el resumen de los 3 retos).
  Es **público**.
- **Información que fue llegando durante la sesión, en este orden:**
  1. El resumen de los tres retos (chat anterior).
  2. `CONTEXTO-datathon-fme-2026.md` de otro chat: horario, normas, física (±500 kW, η = √0,9), el aviso de que el
     servidor solo carga `agent.py`, y la propuesta de roles P1/P2/P3.
  3. La plantilla oficial `agent.py`, con los nombres reales de las claves de `obs`.
  4. El ZIP oficial `paquet_participants_datathon_upc_2.zip`, con datos, `environment.py`, `check_submission.py`,
     el tutorial y el enunciado.

  El código se rehízo dos veces para incorporar cada novedad. Lo que hay ahora en el repo está **verificado contra
  el material oficial**.
- **Lo que no se pudo hacer:** leer directamente la carpeta `/Users/aiitor/Downloads/...` del Mac. Esta sesión
  corre en un contenedor en la nube y no tiene acceso a tu ordenador. Se resolvió cuando adjuntaste el ZIP.

---

## 2. Decisiones de diseño (y por qué)

### 2.1 Organización para tres Claudes en paralelo

| Decisión | Por qué |
|---|---|
| Un `CLAUDE.md` en la raíz como fuente de verdad compartida | Claude Code lo lee automáticamente al arrancar en cada portátil, así que los tres Claudes parten del mismo contexto: el reto, el reparto, los contratos y las reglas |
| **Cada fichero tiene un único dueño** (tabla en `CLAUDE.md`) | Si dos Claudes nunca editan el mismo fichero, no hay conflictos de merge. Cada Claude sabe qué puede tocar y qué tiene que pedir |
| Roles P1 optimizador, P2 previsión y datos, P3 validación y relato, más un integrador | Es el reparto que proponía el chat de contexto. Se recomienda que P3 sea el integrador (ve todo lo que entra y lo necesita para la presentación) o, si sois 4, una cuarta persona |
| Ramas persistentes `p1-optimizador`, `p2-prevision` y `p3-validacion` | Las proponía el contexto. Se sincronizan con `git merge origin/main` y el integrador fusiona con "merge commit", para que las ramas personales no den conflictos |
| **Contratos** escritos entre módulos (firmas y unidades) | Cada persona puede trabajar sin esperar a las demás: mientras se respete el contrato, las piezas encajan |
| Un **único comando de medida**, `python eval.py` | Nadie puede decir "a mí me mejora" sin un número comparable. Todos miden igual |
| `results/experiments.csv` con `merge=union` en `.gitattributes` | Registro común de experimentos al que los tres añaden líneas sin conflictos de git |
| Plantilla de PR + CI de GitHub Actions | Cada PR trae su tabla de resultados y un checklist. La CI pasa los tests y una evaluación rápida en cada PR |
| `docs/prompts-arranque.md` | El primer mensaje que cada persona pega en su Claude, con su rol, sus ficheros, sus tareas en orden y las reglas |

### 2.2 Arquitectura del código

**El problema:** el servidor carga un `agent.py` como módulo suelto. Además, el escáner de seguridad veta `sys`,
`os` e `importlib`, así que no se pueden hacer imports entre ficheros propios de forma fiable. Pero si los tres
trabajasen en un solo `agent.py`, habría conflictos constantes.

**La solución:**
- El código vive en **módulos separados** dentro de `src/battery/`, uno o varios por dueño.
- `scripts/build_submission.py` los **concatena** en un único `dist/agent.py`:
  - quita los imports relativos y une los imports;
  - comprueba que solo hay librerías permitidas y que ningún nombre se repite entre módulos;
  - aplica las mismas reglas del escáner AST oficial: rechaza `.stack()`, `eval`, `globals`, etc.
- Después genera `dist/submission.zip` con `agent.py` y los artefactos de `models/` en la raíz, y lo prueba de dos maneras:
  - **Prueba aislada:** descomprime el ZIP en una carpeta temporal y ejecuta `agent.py` en un Python aislado
    (`-I`), sin acceso al repo. Comprueba que da **exactamente las mismas acciones** que el código de `src/`.
  - **Validador oficial:** pasa `oficial/starter_kit/check_submission.py` sobre el ZIP.

**Capas del agente (y su dueño):**

```text
obs oficial (dict)
   │  adapter.from_official           ← integrador: único sitio que conoce el formato oficial
   ▼
Obs (NamedTuple interna)            ← integrador: obs.py
   │  forecaster.update / forecast    ← P2: demanda y solar de las próximas 24 h
   ▼
optimizer.plan (LP con HiGHS)       ← P1: decide carga/descarga de las 24 h
   │  safety.clip_action              ← P1: garantiza 0 infracciones
   ▼
policy.BatteryAgent.act → float kW  ← P1: lo que llama el evaluador
```

### 2.3 Estrategia del agente (v0)

**MPC** (control predictivo con horizonte deslizante). Cada hora:
1. Traduce la observación oficial (`adapter`).
2. Actualiza la previsión de demanda y solar con los datos de la hora anterior (`forecaster`).
3. Resuelve un **programa lineal** (HiGHS, con `scipy.optimize.linprog`) de 24 h:
   - variables: carga, descarga, compra, venta y estado de carga;
   - restricciones: balance de potencia, dinámica con η = √0,9, ±500 kW y 0–2.000 kWh;
   - objetivo: minimizar `Σ (0,7·co2_t/co2_ref + 0,3·precio_t/coste_ref)·compra_t`.

   Con esos pesos el LP optimiza **exactamente el score** (que es lineal en las compras), con las referencias
   del train como normalización.
4. Aplica solo la primera hora, recortada a los límites físicos, y repite.

Robustez:
- Valor terminal de la carga al final del horizonte; vale 0 cuando el episodio se acaba.
- Respaldo greedy si el LP falla o si se pasa de 40 s de presupuesto interno.
- El agente nunca lanza excepciones.

Referencias de comparación (`src/battery/baselines.py`):
- `nothing`: no usa la batería. Es la base del score.
- `greedy`: reglas simples.
- `oracle`: el mismo LP con **información perfecta** de todo el episodio. Es el **óptimo exacto** del score
  y sirve como techo teórico para la presentación.

### 2.4 Validación

- El test oficial son los **últimos 7 días de cada mes**. Lo imitamos: validación = **últimas 168 h de cada mes**
  del train, seguidas como un solo episodio. El resto es el train para ajustar perfiles y referencias.
- `src/battery/sim.py` es una **réplica exacta** de `environment.py` (mismas observaciones, misma física, mismo
  recuento de infracciones y mismo score), pero más rápida y con un log hora a hora para las gráficas.
  `scripts/calibrate_sim.py` lo comprueba contra el oficial.

---

## 3. Qué verificó el material oficial

Antes del ZIP había varias dudas y contradicciones. `environment.py`, `ENUNCIAT.md`, `check_submission.py`,
`battery_spec.json` y el tutorial resolvieron casi todas:

| Duda | Respuesta | Fuente |
|---|---|---|
| Nombres de las claves de `obs` | `preu_actual`, `co2_actual`, `preus_properes_24h`, `co2_properes_24h`, `day_of_week`, `soc_kwh`, `soc_pct`, `noves_dades_5min`… | plantilla y environment.py |
| ¿La previsión empieza en t+1? | **No: empieza en la hora actual** (`df[t:t+24]`) y al final trae menos de 24 valores | environment.py |
| Formato de `noves_dades_5min` | `{"ultim_consum_kw", "ultima_solar_kw"}` de la hora anterior | environment.py |
| ¿El excedente se paga a 0 o a 0,04 €/kWh? | **0** | environment.py y ENUNCIAT |
| ¿La penalización es 0,20 o 1,00? | environment.py: **0,20**; ENUNCIAT: 1,00. Sigue siendo contradictorio, pero da igual con 0 infracciones | ambos |
| ¿Cómo se cuentan las infracciones? | +1 por recorte de potencia y +1 por recorte de capacidad (hasta 2 por hora) | environment.py |
| Unidades | precio en €/kWh, CO₂ en **kg**/kWh, acción en kW | ENUNCIAT |
| Librerías | más de las que creíamos: también `dataclasses`, `functools`, `heapq`, `re`, `copy` y `pickle`. Prohibido `.stack()` (¡también `np.stack`!) | ENUNCIAT y check_submission.py |
| Cómo construir la tabla horaria | demanda = −contador (recortada a 0..5.000), solar = suma de los 3 inversores, medias horarias, `dropna` | tutorial.ipynb |

Lo que sigue abierto está en `docs/reto.md`, sobre todo **si el servidor evalúa las 12 semanas seguidas o cada una
por separado**.

---

## 4. Resultados con los datos oficiales

Validación: 1.848 h, 11 semanas, porque falta noviembre de 2025 en el train.

| Agente | Score | ΔCO₂ % | ΔCoste % | Infracciones | Tiempo |
|---|---|---|---|---|---|
| `nothing` | 0,00 | 0,00 | 0,00 | 0 | 0,0 s |
| plantilla oficial (`agent.py` del kit) | 0,03 | 1,01 | 2,41 | **7** | — |
| `greedy` | 0,08 | 0,10 | 0,05 | 0 | 0,1 s |
| **`mpc` (nuestro v0)** | **5,97** | **5,62** | **6,78** | **0** | **4,0 s** |
| `oracle` (techo teórico) | 6,12 | 5,78 | 6,90 | 0 | — |

- El MPC v0 captura el **97,5 % del máximo teórico**.
- Con un 10 % de ruido en las previsiones de precio y CO₂, baja solo a 5,94: es robusto.
- Calibración: nuestro simulador y `environment.py` dan **los mismos números** con la plantilla y con el MPC.
- `dist/submission.zip` (18 KB) pasa el validador oficial y la prueba aislada, y con `eval.py --agent dist` saca 5,97.

### Hallazgos importantes para la estrategia y para el jurado

1. **La solar es minúscula:** 26 kW de media y 144 kW como máximo, frente a ~1.100 kW de consumo.
   La red (demanda − solar) baja de 500 kW solo el 0,5 % de las horas y nunca hay excedente.
   → **Prever la demanda y la solar casi no cambia las decisiones.** El problema es puro arbitraje temporal de
   `w_t = 0,7·co2/ref + 0,3·precio/ref`, y precio y CO₂ a 24 h vienen exactos.
2. **El margen es pequeño:** la batería son 2 MWh frente a 27 MWh de consumo diario (7 %), y el óptimo con
   información perfecta es 6,12. En el leaderboard las diferencias entre buenos equipos serán de décimas.
   → **La presentación y el análisis serán decisivos** (el enunciado ya dice que el jurado decide).
3. **Calidad de los datos:** falta noviembre de 2025, el train acaba el 16/08/2026 y hay 15 horas con consumo 0.

Por eso se reorientó el encargo de P2: calidad de datos, ver más allá de 24 h y análisis para el jurado, en lugar
de un gran modelo de demanda. Está todo en `docs/prompts-arranque.md`.

---

## 5. Mapa de ficheros (qué hace cada uno y de quién es)

### Raíz
| Fichero | Dueño | Qué es |
|---|---|---|
| `CLAUDE.md` | integrador | Contexto compartido que leen todos los Claudes: el reto, los hallazgos, el reparto, los contratos, las reglas del código empaquetado, los comandos, el flujo de git y lo que Claude no debe hacer |
| `README.md` | integrador | Presentación del repo para humanos: método, resultado, estructura y enlaces |
| `eval.py` | integrador | Único comando de evaluación. Opciones: `--agent {mpc,dist,greedy,nothing,oracle,all}`, `--fc-noise`, `--quick`, `--log`, `--save-hourly` y `--strict`. Proyecta el tiempo a 2.016 h |
| `requirements.txt` / `requirements-dev.txt` | integrador | Librerías del agente / de desarrollo (pytest, matplotlib, jupyter) |
| `.gitignore` | integrador | Ignora `oficial/`, `data/`, `dist/`, los ZIP y las cachés. **Los datos oficiales no se suben** |
| `.gitattributes` | integrador | `results/experiments.csv merge=union` |

### `src/battery/` (paquete del agente)
| Fichero | Dueño | Empaquetado | Qué es |
|---|---|---|---|
| `params.py` | integrador | sí | Constantes verificadas: batería, score, horizonte y presupuesto de tiempo |
| `obs.py` | integrador | sí | `Obs`, la observación interna (NamedTuple) con unidades documentadas |
| `adapter.py` | integrador | sí | Formato oficial ⇄ `Obs`. `make_official_obs` construye la observación igual que `environment.py` |
| `safety.py` | P1 | sí | Rango válido de la acción, `clip_action` con margen de 1e-4 y física de la carga |
| `optimizer.py` | P1 | sí | LP disperso (variables c, d, compra, venta y carga) con su estructura en caché, y `score_weights` |
| `policy.py` | P1 | sí | `MPCPolicy` (valor terminal, respaldo greedy, presupuesto de tiempo) y **`BatteryAgent`** |
| `forecaster.py` | P2 | sí | Previsión online: perfil semanal de la demanda y solar de los últimos 3 días, corrección por persistencia y perfiles de `models/forecaster.json` como punto de partida |
| `data.py` | P2 | no | `build_hourly` (como el tutorial), `load`, `validation_split` y `train_split`. Genera `data/processed/hourly.csv` solo |
| `synthetic.py` | P2 | no | Datos sintéticos para que todo funcione sin el ZIP oficial (CI) |
| `baselines.py` | P1 | no | `NothingAgent`, `GreedyAgent`, `OracleAgent` |
| `sim.py` | P3 | no | Réplica exacta de `environment.py`, `score`, log hora a hora (`LOG_COLUMNS`) y `to_env_frame` |

### `scripts/`
| Fichero | Dueño | Qué es |
|---|---|---|
| `build_submission.py` | integrador | Concatena los módulos en `dist/agent.py`, comprueba imports y llamadas vetadas, crea `dist/submission.zip` (≤ 25 MB), lo prueba aislado y pasa el validador oficial |
| `train_forecaster.py` | P2 | Genera `models/forecaster.json` (perfiles) y `models/objective_refs.json` (93,2 kg/h y 156,3 €/h), **solo con el train** |
| `calibrate_sim.py` | P3 | Compara `sim.py` con `environment.py` usando la plantilla oficial y nuestro MPC |

### `tests/` (12 tests; también los pasa la CI)
| Fichero | Dueño | Qué comprueba |
|---|---|---|
| `test_safety.py` | P1 | 20.000 acciones aleatorias sin ninguna infracción. NaN, inf y texto devuelven 0 |
| `test_agent.py` | P1 | Una semana completa: 0 infracciones, score > 0, sin usar el respaldo y tiempo proyectado < 40 s |
| `test_forecaster.py` | P2 | Contrato: longitud, ≥ 0, sin NaN y velocidad |
| `test_adapter.py` | integrador | Ida y vuelta del formato oficial, observación al estilo `check_submission.py` (timestamp en texto) y final de los datos |
| `test_sim.py` | P3 | `nothing` saca 0, contabilidad de energía, recuento de infracciones como el oficial y **coincidencia con `environment.py`** (si existe `oficial/`) |
| `test_bundle.py` | integrador | `build_submission.py` funciona y la prueba aislada sale bien |

### `docs/`
| Fichero | Dueño | Qué es |
|---|---|---|
| `reto.md` | integrador | Especificación verificada, dudas abiertas, lo que dicen los datos y las fórmulas |
| `equipo.md` | integrador | Quién es quién (por rellenar), preparación de GitHub y de cada portátil, día a día con git y puntos de sincronización |
| `prompts-arranque.md` | integrador | El primer mensaje para el Claude de P1, P2 y P3 |
| `decisiones.md` | P3 | Registro de decisiones con evidencia, para el jurado (ya con 5 entradas) |
| `envios.md` | integrador | Registro de envíos oficiales |
| `contexto-chat.md` | — | El contexto del otro chat (evento, horario, normas) |
| `retos-datathon-fme-2026.md` | — | El resumen de los tres retos (movido desde la raíz) |
| `registro-montaje.md` | — | Este documento |

### Otras carpetas
- `models/`: artefactos que van en el ZIP. Ya contiene `forecaster.json` y `objective_refs.json` entrenados con el
  train oficial. Son agregados (medias por hora), no datos crudos.
- `analysis/` y `presentation/`: zona de P3, con un README que explica qué datos usar y qué contar.
- `results/experiments.csv`: registro común, ya con la primera evaluación (nothing / greedy / mpc / oracle).
- `.github/`: plantilla de PR y CI (`ci.yml`: tests y `eval.py --quick --strict` con datos sintéticos).
- `oficial/` (**no está en git**): el ZIP oficial descomprimido. Cada persona lo pone en su portátil.

---

## 6. Cómo se ha comprobado que todo funciona

Todas estas comprobaciones se ejecutaron en la sesión, con los datos oficiales, justo antes de subir:

```text
python -m pytest -q                 → 12 passed
python scripts/calibrate_sim.py     → plantilla OK (0,03 = 0,03), mpc OK (5,97 = 5,97)
python scripts/build_submission.py  → prueba aislada OK (mismas acciones), check_submission.py oficial: VÁLIDA
python eval.py --agent all          → tabla de la sección 4
python eval.py --agent dist         → 5,97 (el agent.py empaquetado = el de src/)
```

Durante el desarrollo se encontraron y corrigieron estos fallos:
- El empaquetador daba un falso positivo cuando dos módulos importaban `typing.NamedTuple` en líneas distintas.
- Un test mal planteado: con la batería llena, pedir carga **sí** es una infracción.
- Un reemplazo automático "25" → "24" cambió los años de unas fechas en un test. Se reescribió el test.
- `eval.py --agent dist` no encontraba los artefactos fuera del ZIP. Ahora también se copian a `dist/`.

---

## 7. Subida a GitHub

- Todo está en la rama **`claude/clever-euler-koiz2q`** de `aitorboligecubas/Datathon-26`.
  En la primera subida no se tocó `main`. **Después se subió también a `main` a petición expresa** (sección 10).
  Las ramas `p1/p2/p3` las crea cada persona desde `main`.
- `main` y `claude/clever-euler-koiz2q` apuntan al mismo commit: el equipo puede clonar y empezar ya.
- **No se ha subido nada de los datos oficiales.** Solo están los dos JSON de `models/` con medias agregadas, que el
  agente necesita dentro del ZIP.

---

## 8. Lo que tenéis que hacer ahora (en orden)

1. **Hacer el repo privado** mientras dure el evento: Settings → General → Danger Zone → Change visibility.
2. ~~Fusionar esta rama en `main`~~ (hecho).
3. **Invitar al equipo** (Settings → Collaborators) y rellenar la tabla "Quién es quién" de `docs/equipo.md`.
4. Opcional: proteger `main` (exigir PR y el check `tests`) y dejar activados los "merge commits".
5. Cada persona: clonar, crear su rama, descomprimir el ZIP oficial en `oficial/`,
   `pytest` y `eval.py --agent all`, arrancar `claude` y pegar su prompt de `docs/prompts-arranque.md`.
6. **Primer envío oficial ya:** `python scripts/build_submission.py` → subir `dist/submission.zip` a la web,
   fijar el PIN del equipo y apuntarlo en `docs/envios.md`. Sirve para comprobar que el servidor lo acepta y para
   saber si evalúa como nuestra validación.

## 9. Ideas de mejora ya identificadas (para los prompts de cada rol)

- **P1:**
  - separar cuánto se pierde por la previsión y cuánto por el horizonte (MPC con previsión perfecta);
  - afinar el valor terminal;
  - probar horizontes de más de 24 h con un patrón de precio y CO₂;
  - vaciar la batería al final del episodio;
  - decidir qué hacer en los cambios de semana.
- **P2:**
  - calidad de los datos (noviembre, ceros, cambios de hora);
  - prever precio y CO₂ más allá de 24 h si P1 demuestra que compensa;
  - análisis de los patrones de CO₂ y precio.
- **P3:**
  - aclarar si el servidor evalúa por semanas;
  - gráficas (semana tipo, ahorro acumulado, "capturamos el 97,5 % del máximo teórico", análisis por mes,
    robustez);
  - registro de decisiones y pitch.

---

## 10. Actualización: lo que aportaron las slides oficiales (`UPC Sostenible.pdf`)

Después de la primera subida llegaron las 9 slides de la presentación del reto. Aportan cuatro cosas:

| Dato de las slides | Qué hemos hecho |
|---|---|
| **El test tiene ~1.700 h**, no 2.016 (faltan datos, igual que noviembre en el train) | El agente ya no cuenta hasta 2.016 para saber cuándo acaba el episodio. Usa una señal exacta del entorno: `environment.py` recorta `preus_properes_24h` al final de los datos, así que si llegan menos de 24 valores, el episodio acaba dentro del horizonte. Entonces la carga final vale 0 y el LP la gasta en las horas de más CO₂. **Validación: 5,97 → 6,08** (techo 6,12, ahora un 99,3 %). Test nuevo en `tests/test_agent.py` |
| **Dry-run en la web gratis e ilimitado (48 pasos)** antes del envío oficial | Añadido a `CLAUDE.md`, `docs/reto.md` y `docs/equipo.md`: pasarlo siempre antes de gastar uno de los 10 envíos diarios |
| **Penalización de −1,00 por infracción** (igual que el ENUNCIAT; `environment.py` usa 0,20) | Documentado como contradicción. No cambia nada: el objetivo es 0 infracciones y lo cumplimos |
| "Solar fins a 450 kW", "pics fins a 1.600 kW" | En los datos, cada inversor satura a 50 kW (≈150 kW en total) y la demanda pasa de 1.600 kW el 8,5 % de las horas. **Mandan los datos.** El filtro de columnas de `build_hourly` ahora coge exactamente `Inversor i - POTENCIA ACTIVA (kW)` (antes también cogía una columna de consigna que siempre vale 0; el resultado no cambia) |

**Para el jurado:** gastar la carga al final es correcto dentro de las reglas, porque la carga final no puntúa.
Conviene explicarlo con transparencia: en la operación real del campus habría que darle un valor.

Resultado actualizado en validación (datos oficiales):

| Agente | Score | ΔCO₂ % | ΔCoste % | Infracciones | Tiempo |
|---|---|---|---|---|---|
| `mpc` | **6,08** | 5,73 | 6,89 | 0 | 4,0 s |
| `oracle` | 6,12 | 5,78 | 6,90 | 0 | — |

Además, **todo el contenido de la rama se ha subido también a `main`**, a petición expresa. Así el equipo puede
clonar directamente y crear sus ramas `p1/p2/p3` desde `main`.

---

## 11. Actualización: roles reequilibrados

Los roles iniciales se definieron antes de conocer los datos. Con lo que sabemos ahora (la solar es minúscula,
prever el consumo apenas cambia el score y el agente ya está al 99,3 % del techo), P2 se había quedado casi sin
trabajo útil y P3 (presentación + integración + gráficas) estaba sobrecargado. Nuevo reparto:

| Rol | Rama | Enfoque | Razonamiento | Volumen |
|---|---|---|---|---|
| **P1 · Optimización y robustez** | `p1-optimizador` | Cuánto aporta cada pieza, robustez (evaluación por semanas, ruido, 0 infracciones), mejoras justificadas y estrategia cerrada a medianoche | **El más alto** (riesgo de sobreajuste con un margen tan pequeño) | Medio |
| **P2 · Datos y análisis** | `p2-datos` | Calidad de los datos, patrones de CO₂ y precio, por qué ~6 %, escenarios de 1–8 MWh para UPC Sostenible. Ahora es dueño de `analysis/` | Medio-alto | Medio-alto |
| **P3 · Relato, presentación e integración** | `p3-relato` | Guion, slides, preguntas del jurado, decisiones, PRs, envíos | Medio (comunicar y decidir) | **El más alto**, y el de **más impacto** |

Se trabaja **por fases**: los tres en paralelo hasta el sábado por la noche (sincronizaciones a las 17:00, 21:00
y 00:00; estrategia cerrada a medianoche) y todos convergen en la presentación el domingo. Detalle en
`docs/equipo.md` (secciones 0–2), `CLAUDE.md` (sección 5) y los nuevos encargos en `docs/prompts-arranque.md`.
Las ramas cambian de nombre: `p2-prevision` pasa a `p2-datos` y `p3-validacion` pasa a `p3-relato`
(todavía no se había creado ninguna).

