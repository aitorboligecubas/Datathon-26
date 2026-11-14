# CLAUDE.md — Reto UPC Sostenible · Datathon FME 2026

> **Qué es este fichero.** Es la guía compartida del equipo. Claude Code la lee al arrancar en el portátil
> de cada persona, así que los tres Claudes (y los tres humanos) parten de la misma historia: qué problema
> resolvemos, qué hemos descubierto, cómo funciona nuestra solución y cómo trabajamos juntos sin pisarnos.
> Está escrita para leerse de arriba abajo: primero el contexto, después los detalles técnicos.
>
> Responde siempre en español. **Entrega: domingo 15/11 a las 12:00.** Congelación del código: domingo a las 9:30.
>
> **Novedad del sábado a las 16:33: hay un HARD MODE con ranking propio.** Está explicado en la sección 4 bis.
> El modo estándar sigue abierto, pero ahí todos los buenos equipos están empatados en el máximo.

---

## 1. La historia: una batería para el Campus Nord

El Campus Nord de la UPC consume mucha electricidad: unos **1.100 kW de media** (aulas, laboratorios,
servidores, climatización), que son unos **27 MWh al día**. Tiene placas solares, pero producen muy poco
comparado con lo que se consume. Casi toda la energía se compra a la red eléctrica.

Esa energía no cuesta lo mismo a todas horas, ni en euros ni en CO₂:
- El **precio** (tarifa PVPC) cambia cada hora.
- El **CO₂** también: cuando hay mucho sol y viento en España, la electricidad de la red es limpia. Cuando entran
  las centrales de gas (ciclo combinado), normalmente por la tarde y por la noche, es más sucia.

UPC Sostenible plantea instalar una **batería de 2.000 kWh**. La idea es sencilla: **llenarla cuando la
electricidad es limpia y barata, y usarla cuando es sucia y cara.** Así el campus compra menos energía en las
peores horas.

**Nuestro trabajo** es programar el "cerebro" de esa batería: un programa (`BatteryAgent`) al que, **cada hora**,
el simulador oficial le cuenta la situación y le pregunta: *¿cargo, descargo o espero, y cuánto?*

---

## 2. Las reglas del juego (explicadas)

### Qué sabe el agente cada hora
Cada hora recibe un diccionario `obs` con:
- **la hora, el día de la semana y la fecha**;
- **cuánta energía queda en la batería** (en kWh y en %);
- **el precio y el CO₂ de esta hora**;
- **el precio y el CO₂ de las próximas 24 horas**, exactos (es como tener la previsión del tiempo perfecta para mañana);
- **cuánto consumió el campus y cuánto produjo la solar en la hora anterior**.

Lo que no sabe es el consumo ni la solar de esta hora ni de las siguientes: esos tiene que preverlos.

### Qué responde
Un número en kW:
- **positivo**: cargar, hasta +500;
- **negativo**: descargar para alimentar el campus, hasta −500;
- **0**: no hacer nada.

### La física de la batería
- **Capacidad:** 2.000 kWh. **Potencia máxima:** 500 kW en cada sentido. **Empieza al 50 %** (1.000 kWh).
- **Pierde un 10 % en cada ida y vuelta.** Si metes 1 kWh, solo recuperas 0,9 kWh: se pierde un 5 % al cargar
  y otro 5 % al descargar (η = √0,9 ≈ 0,9487 en cada sentido).
- **Balance:** compra a la red = consumo − solar + batería. Si sale negativo (sobra energía), se vierte a la red
  **sin cobrar nada**.

### Cómo nos puntúan
Nos comparan con el campus **sin batería**:

```text
Score = 0,70 · (% de CO₂ ahorrado) + 0,30 · (% de euros ahorrados) − penalización por infracción
```

- El **CO₂ pesa más que el dinero** (70/30).
- **Infracción:** pedir algo imposible, como cargar con la batería llena, descargar con la batería vacía o
  pasar de 500 kW. Se penaliza cada vez: −0,20 según el simulador oficial y −1,00 según el enunciado y las
  slides. Por eso nuestro objetivo es **cero infracciones, siempre**.
- **El test** son los **últimos 7 días de cada mes** de un año (sep 2025 a ago 2026): 2.016 horas según el
  enunciado y la web, de las que el **conjunto público son 1.008**. Nos dan para entrenar las 3 primeras semanas
  de cada mes. Por las cifras que publica la web, una de las seis semanas públicas apenas aporta consumo.
- **El jurado decide de forma decisiva**: el leaderboard cuenta, pero también la presentación, el razonamiento
  y la justificación de la estrategia.

### Cómo se entrega
- Un `submission.zip` de 25 MB como máximo, con `agent.py` y los ficheros de modelos en la raíz.
- Toda la simulación tiene que tardar menos de **60 segundos**.
- **10 envíos oficiales por turno** (turno 1: sábado hasta las 21:00; los fallidos no cuentan). **El jurado solo
  evalúa, en el ranking privado, las 2 entregas que seleccionemos** en la web (por defecto, las 2 mejores del
  público). Registro en `docs/envios.md`: dos envíos, **6,43 puntos** con 0 infracciones. Antes, la web ofrece una **prueba rápida (dry-run)
  gratis e ilimitada** de 48 pasos.
- El leaderboard es 50 % público y 50 % privado: **no hay que obsesionarse con el público**.

Todo esto está verificado con el material oficial. Detalle, fuentes y dudas abiertas: `docs/reto.md`.

---

## 3. Lo que hemos descubierto (y por qué cambia el enfoque)

Al analizar los datos reales salieron tres cosas que lo cambian todo:

**① La solar casi no cuenta.** Produce de media 26 kW (como mucho, ~150 kW) frente a ~1.100 kW de consumo.
El campus compra a la red el 100 % de las horas y nunca le sobra energía. Así que el problema **no** es
"guardar el excedente solar", sino **mover energía en el tiempo**: comprar de más en las horas buenas para
comprar de menos en las malas.

**② Mover energía solo compensa si la diferencia es grande: la regla del 11 %.** Como se pierde un 10 % por el
camino, por cada kWh que compramos de más en una hora "buena", ahorramos solo 0,9 kWh en una "mala".
Por ejemplo, con el CO₂:

```text
03:00 de la madrugada → red limpia:  0,05 kg CO₂/kWh  → compramos 1 kWh de más (+0,050 kg)
20:00 de la tarde     → red sucia:   0,15 kg CO₂/kWh  → compramos 0,9 kWh de menos (−0,135 kg)
Resultado: −0,085 kg por cada kWh movido. Compensa.
```

Si la hora mala fuese solo un poco peor (menos de un 11 %), perderíamos. Para combinar CO₂ y precio damos a cada
hora un **"peso"**, que es lo "mala" que es esa hora según la fórmula del score:

```text
peso_hora = 0,7 · CO₂_hora / CO₂_medio + 0,3 · precio_hora / precio_medio
```

**③ El margen es pequeño, así que el jurado pesa mucho.** La batería (2 MWh) es solo el 7 % del consumo diario.
Aunque supiésemos el futuro perfecto, el score máximo en nuestra validación sería **6,12**. Nuestro agente ya saca
**6,09**, el 99,6 % de ese máximo. En el leaderboard las diferencias entre buenos equipos serán de décimas.
**Lo que nos diferenciará es explicar bien el razonamiento, con números y gráficas.**

---

## 4. Cómo funciona nuestro agente (en lenguaje llano)

Pensad en un **GPS**: planifica la ruta completa, pero solo te dice el siguiente giro. Al minuto siguiente
vuelve a calcular con la nueva información. Nuestro agente hace lo mismo con la batería. **Una hora en su vida:**

1. **Llega la observación** de las 14:00. Un traductor (`adapter`) la pasa a nuestro formato interno.
2. **Aprende de lo que acaba de pasar.** Con el consumo y la solar reales de las 13:00, ajusta su previsión de
   las próximas 24 h (`forecaster`).
3. **Hace un plan para las próximas 24 h.** Con el precio y el CO₂ (que conoce exactos) y su previsión de consumo,
   un optimizador matemático (`optimizer`) calcula qué hacer cada hora para que la suma de los pesos de lo
   comprado sea lo más baja posible, respetando la física de la batería. Esto es un **problema de programación
   lineal (LP)**, que el solver HiGHS de `scipy` resuelve en milisegundos.
4. **Ejecuta solo la primera hora del plan**, después de pasarla por un control de seguridad (`safety`) que la
   recorta para que nunca sea una infracción.
5. **A las 15:00 vuelve a empezar** con información nueva. Esta técnica se llama **MPC** (Model Predictive Control).

Dos detalles importantes:
- **Al final del test, gasta lo que queda.** La carga final no puntúa. El simulador nos manda menos de 24 horas
  de previsión cuando se acaban los datos: es la señal para vaciar la batería en las peores horas.
  Hay que contarlo con transparencia al jurado: en el campus real no lo haríamos así.
- **Nunca descarga más de lo que el campus compró la hora anterior.** Normalmente no cambia nada (el campus
  consume más de 500 kW), pero protege de las averías del contador: en los datos hay 14 horas seguidas marcando 0,
  y descargar contra un consumo nulo es tirar la energía.
- **No cuenta pasos.** El final se detecta solo por la previsión recortada, así que el agente funciona igual dure
  lo que dure el test.
- **Sabe reconocer una semana sin datos de contador.** El test son 12 semanas sueltas puestas una detrás de otra.
  Si el contador marca 0 desde la primera hora de una semana (en el train, noviembre no tiene datos de contador),
  no hay consumo que cubrir hasta que acabe el mes: el agente no descarga y compra la carga para la semana
  siguiente en una hora barata, con un precio de reserva, en vez de en la primera que aparece. En un episodio
  simulado con noviembre a cero esto vale 0,06 puntos; en semanas normales no cambia ninguna decisión.
- **Ignora la lectura "de la hora anterior" en la primera hora de cada semana**, porque es de un mes antes.
- **Si algo falla o vamos justos de tiempo**, el agente usa una regla simple de respaldo. **Nunca** lanza un error.

Cuánto aporta cada pieza y cómo aguanta el agente (por semanas, con ruido, fuera de la validación):
`results/p1_ablaciones.md`, que se regenera con `python scripts/p1_ablaciones.py`.
Auditoría completa (calibración, episodios tipo test, semana sin datos, lectura del leaderboard, 12.000
observaciones hostiles, latencia): `results/p1_auditoria.md`, con `python scripts/p1_auditoria.py`.

- **Sabe tratar lecturas vacías.** Si el contador no da ni un 0 (lectura vacía) desde la primera hora de una
  semana, no descarga y deja la batería llena.

Para tener contexto, comparamos siempre con otras estrategias (`python eval.py --agent all`):

| Estrategia | Qué hace | Score en validación |
|---|---|---|
| `nothing` | No usa la batería (es la referencia) | 0,00 |
| plantilla oficial | Reglas fijas por horas del kit oficial | 0,03 (con 7 infracciones) |
| `greedy` | Reglas sencillas | 0,08 |
| **`mpc`** | **Nuestro agente** | **6,09** |
| `oracle` | El mismo planificador, pero con **bola de cristal**: conoce todo el futuro. Es el techo teórico | 6,12 |

**Dónde estamos en el modo estándar (sábado por la tarde).** Dos envíos, los dos con **6,43** y 0 infracciones.
El segundo llevaba la lógica de "semana sin contador" y sacó exactamente lo mismo que el primero: en el test
público no hay ninguna semana así. La organización ha confirmado que en el público los equipos están en el
máximo (los primeros tienen 6,44; nosotros, 6,4314) y que en el **privado nadie ha llegado al máximo**: ahí
puede contar que nuestro agente sepa tratar un contador a cero. Detalle en `docs/envios.md`.

---

## 4 bis. El HARD MODE (desde el sábado a las 16:33)

La organización ha abierto un segundo ranking, independiente, con un campus "ampliado":

| Qué cambia | Modo estándar | Hard mode |
|---|---|---|
| Batería | 2.000 kWh, ±500 kW | **6.000 kWh, ±1.500 kW** |
| Solar | casi no cuenta | **12 veces mayor**: a mediodía sobra energía, y lo que sobra se regala a la red |
| Precio y CO₂ conocidos | 24 horas | **solo 3 horas** (la actual y las 2 siguientes): el resto hay que preverlo |
| Lectura de la hora anterior | consumo y solar | además, la **meteo** (irradiancia, temperaturas y viento) |

Dos trampas nuevas, que la organización avisa:
- **Descargar a ciegas es tirar energía.** La batería puede dar 1.500 kW, pero el campus consume entre 600 y
  1.300 kW (y menos cuando hay sol). Lo que se descarga de más se vierte a la red sin cobrar ni ahorrar CO₂.
- **Sin previsión no hay plan.** Con solo 3 horas no se sabe cuándo llegan el valle y el pico de mañana.

**Nuestro agente del hard mode es el mismo GPS**, con tres piezas nuevas (`src/battery/hard*.py`):
1. **Previsión de precio y CO₂** (`hard_market.py`). Un perfil por mes, tipo de día y hora aprendido en el
   train, y una regresión que predice cuánto se desviará cada hora de ese perfil. Usa 13 pistas: las 3 horas
   conocidas, las últimas 6 y 24 horas, ayer y anteayer a la misma hora y el nivel del día. Cada semana del test
   arranca con la "memoria" de los 7 días del train que la preceden. Los festivos nacionales cuentan como domingo.
   El perfil se interpola con el del mes vecino según el día (el test son los días 25–31 y el train los días 1–24)
   y los de sábado y domingo se suavizan con los meses vecinos, porque cada mes solo tiene 3 o 4 de cada.
2. **Previsión de solar y consumo** (`hard_solar.py`).
   - El consumo: el perfil de la semana, corregido con una regresión (por hora del día y antelación) sobre cuánto
     se desviaba el consumo la hora anterior y ayer. De 23 a 5 h el contador del train está congelado, así que el
     consumo de la noche se conoce exacto.
   - La solar: "cielo despejado" de la fecha por la claridad de hoy (la última hora y la media del día). El cielo
     despejado va en hora solar y se interpola entre meses, porque el test son los días 25–31 y el train los
     días 1–24.
   - Los festivos del campus (la Mercè, Navidad, Sant Joan) cuentan como domingo.
3. **El plan cuenta con la incertidumbre** (versión 12). El consumo neto de cada hora no se conoce: solo su
   previsión y cuánto suele fallar (la solar, unos 140 kW de día). Descargar de más es tirar energía y cargar de
   menos es perder excedente gratis. En vez de un margen fijo, el LP lleva 11 cuantiles del error medido: el primer
   kW que se descarga se aprovecha casi seguro y el último casi nunca. Así decide solo cuánto apurar: mucho cuando
   lo guardado vale poco (la batería se va a rellenar con excedente solar) y poco cuando vale casi como esta hora.
4. **Memoria al empezar cada semana** (versión 9). Cada semana del test empieza justo donde acaba el train de su
   mes, así que el previsor de consumo y solar arranca con las últimas 48 h del train. Se comprueba en la segunda
   hora (de noche el contador está congelado) y, si no casa, se olvida.

El final del test ya no se ve en la previsión (solo trae 3 horas): se sabe por calendario (31/08/2026). Si el
servidor reiniciara la batería cada semana, el agente lo detecta y cierra cada semana vacía.

| Agente (validación reservada, hard mode) | Score en casa | Score en la web |
|---|---|---|
| No usar la batería | 0,00 | |
| Planificar solo con las 3 horas conocidas | 15,5 | |
| Versión 2 (primer envío) | 20,37 | 23,35 |
| Versión 6 (previsor de precio y CO₂ con memoria) | 20,66 | 23,70 |
| Versión 10 (previsor ampliado de consumo y solar, semilla y margen 1,0) | 20,79 | **24,15** |
| Versión 12 (la 10 con el plan que cuenta con la incertidumbre) | 20,92 | 24,11 |
| **Versión 14 (la 12 con el perfil de precio y CO₂ interpolado entre meses y los fines de semana suavizados)** | **21,07** | sin enviar |
| La versión 12 con el precio y el CO₂ reales a 24 h | 21,65 | |
| Óptimo con todo el futuro conocido (techo) | 22,40 | |

**Dónde estamos (domingo de madrugada): segundos de 41 equipos con la v10 (24,15); el líder tiene 24,25.**

**Cómo leer la web.** La nota de casa y la de la web no son comparables en valor (el conjunto público tiene una
referencia más baja). Y las diferencias pequeñas de la web no ordenan las versiones: según las preguntas frecuentes
y el código oficial, el público es el 50 % de cada semana del test, calculado con una máscara de horas sobre una
única simulación. En nuestro banco, la diferencia entre la v12 y la v10 va de −0,20 a +0,46 según qué horas sean
públicas, con +0,13 en el episodio completo. Lo que una versión pierde en una mitad lo gana en la otra.
Por eso **se seleccionan para el jurado las dos mejores por nota del episodio completo (v14 y v12), marcándolas a
mano**, y no se persiguen décimas del público con variantes. El análisis completo está en `docs/envios.md`.

Antes de cada envío del modo difícil se pasa el **ataque de robustez** (`scripts/p1_lab/hard_ataque_*.py`):
observaciones deformadas, averías del contador, calendario del test, cambio de hora, el `agent.py` empaquetado
frente al código y el simulador oficial. Lo que se exige: 0 infracciones y 0 excepciones.

```bash
python scripts/p1_hard.py --split dev       # comparativa del hard mode en los días 8-14 de cada mes (para diseñar)
python scripts/p1_hard.py                   # en las últimas 168 h de cada mes (RESERVADA: solo para verificar)
python scripts/p1_hard.py --split dev --save-hourly   # además, el detalle hora a hora en results/hourly/ (para gráficas)
python scripts/p1_hard.py --fit             # regenera models/hard_market.json y models/hard_solar.json
python scripts/build_submission.py --hard   # ZIP del hard mode en dist/hard/ (el estándar no cambia)
```

Dueños: `src/battery/hard.py`, `hard_market.py`, `hard_solar.py` y `scripts/p1_hard.py` son de **P1**; mejorar
las previsiones es trabajo de **P2** con P1 (contratos en la cabecera de cada fichero). Los ficheros
`models/hard_*.json` solo entran en el ZIP del hard mode. Cupo de envíos del hard mode: 10 el sábado hasta las
21:00, 10 de sábado 21:00 a domingo 8:00 y 10 el domingo desde las 8:00, con validación rápida gratuita.

---

## 5. Cómo nos organizamos: 3 personas, 3 Claudes, 1 repo

**El riesgo:** tres Claudes editando a la vez el mismo código acaban pisándose: conflictos de git, cambios
que se rompen entre sí y nadie sabe qué versión es buena.

**Las cuatro ideas que lo evitan:**

1. **Cada fichero tiene un único dueño.** Si dos personas nunca tocan el mismo fichero, no hay conflictos.
2. **Las piezas encajan por "contratos"**, como los enchufes: cada módulo promete qué recibe y qué devuelve (sección 6).
   Mientras se respete el contrato, cada uno puede mejorar su pieza por dentro sin romper las de los demás.
3. **Una sola vara de medir:** `python eval.py`. Nadie dice "me mejora" sin ese número.
4. **Una persona integra**: revisa las pull requests y las fusiona en `main`.

### Los roles (y por qué son estos)

Los datos cambiaron el reparto inicial. Como la solar casi no cuenta y el agente ya captura el 99,6 % del máximo,
**queda poco que ganar en el leaderboard y mucho que ganar ante el jurado**. Por eso los roles se centran en
**solidez, pruebas y relato**:

- **P1 · Optimización y robustez**, rama `p1-optimizador`. **Es el rol con más carga de razonamiento.**
  - Que la solución sea sólida y esté justificada: cuántas décimas aporta cada pieza, robustez (evaluación por
    semanas, previsiones con ruido, 0 infracciones) y mejoras solo si se pueden justificar.
  - Con un margen tan pequeño, una mejora puede ser casualidad (sobreajuste): hay que desconfiar y explicar el porqué.
- **P2 · Datos y análisis**, rama `p2-datos`. Los números que convencen:
  - calidad de los datos;
  - cuándo es sucia y cara la red (CO₂ y precio por hora y mes);
  - por qué el ahorro máximo es de ~6 %;
  - la pregunta de negocio para UPC Sostenible: ¿qué ahorraría una batería de 1, 2, 4 u 8 MWh?

  Produce las gráficas y cifras de la presentación y mantiene la previsión.
- **P3 · Relato, presentación e integración**, rama `p3-relato`. **Es el rol con más volumen de trabajo y más impacto.**
  - Guion, slides, ensayo, preguntas difíciles y registro de decisiones.
  - Como integrador: revisa y fusiona las pull requests, mantiene `main` en verde, genera el ZIP y hace los envíos.
  - El simulador ya está calibrado; solo comprueba que sigue cuadrando.
  - Si sois 4, la cuarta persona se queda con la integración.
  - **Ahora mismo P3 está pendiente: el integrador provisional es Aitor (P1).** Su Claude puede ayudarle con
    las tareas de integración y editar los ficheros del integrador cuando él lo pida. Detalle en `docs/equipo.md`.

**¿A la vez o uno detrás de otro? Por fases.** Hasta el sábado por la noche, los tres en paralelo, con
sincronizaciones a las 17:00, 21:00 y 00:00. P1 cierra la estrategia a medianoche. El domingo, todos convergen en
la presentación. P3 no espera: empieza el relato con los números actuales y los actualiza a medida que P1 y P2
entregan. Calendario detallado: `docs/equipo.md`, sección 2.

### Qué ficheros son de quién

| Rol | Ficheros que **solo** edita esta persona | Ficheros nuevos |
|---|---|---|
| **P1** | `src/battery/policy.py`, `optimizer.py`, `safety.py`, `baselines.py`, `hard.py`, `hard_market.py`, `hard_solar.py`, `tests/test_safety.py`, `tests/test_agent.py` | `scripts/p1_*.py` |
| **P2** | `src/battery/forecaster.py`, `data.py`, `synthetic.py`, `scripts/train_forecaster.py`, `models/`, `analysis/`, `tests/test_forecaster.py` | `analysis/`, `scripts/p2_*.py` |
| **P3 + integrador** | `src/battery/sim.py`, `scripts/calibrate_sim.py`, `presentation/`, `docs/decisiones.md`, `tests/test_sim.py` y, como integrador: `CLAUDE.md`, `src/battery/params.py`, `obs.py`, `adapter.py`, `eval.py`, `scripts/build_submission.py`, `tests/test_adapter.py`, `tests/test_bundle.py`, `docs/reto.md`, `docs/envios.md`, `docs/equipo.md`, `.github/`, `requirements*.txt`, `README.md` | `presentation/` |

**Si necesitas cambiar un fichero que no es tuyo, no lo toques.** Escribe en tu pull request (sección "Peticiones a
otros roles") qué necesitas y por qué, y avisa a su dueño. Leer e importar el código de otros sí está permitido:
por ejemplo, P2 usa el `OracleAgent` de P1 para sus escenarios. Todos pueden añadir líneas a
`results/experiments.csv` mediante `eval.py --log`.

Nombres de cada persona y pasos de preparación: `docs/equipo.md`. El primer mensaje para cada Claude:
`docs/prompts-arranque.md`.

---

## 6. Cómo encajan las piezas (los contratos)

El recorrido de una hora, con quién es dueño de cada paso:

```text
 obs oficial (dict)
     │
     ▼  adapter.from_official ............ [Integrador] único sitio que conoce el formato oficial
 Obs (nuestro formato)
     │
     ▼  forecaster.update / forecast ..... [P2] consumo y solar previstos, 24 h
     │
     ▼  optimizer.plan ................... [P1] plan óptimo de 24 h (LP)
     │
     ▼  safety.clip_action ............... [P1] garantiza 0 infracciones
     │
 BatteryAgent.act → kW ................... [P1] lo que llama el evaluador
```

Y alrededor, sin ir en la entrega: `data` (P2) carga los datos, `sim` (P3) simula como el oficial, `eval.py`
(integrador) lo mide todo y `analysis/` (P2) saca las gráficas para la presentación (P3).

Las firmas exactas, que **no se cambian sin acordarlo antes**:

```text
adapter.from_official(obs_dict) -> Obs
Obs(hour, weekday, soc_kwh, price[<=24], co2[<=24], load_prev_kw, pv_prev_kw, timestamp)
    price en €/kWh, co2 en kg CO2/kWh, [0] = hora actual; menos de 24 valores = se acaban los datos

Forecaster(prior: dict | None)
    .update(obs)                                    # una vez por hora, antes de forecast
    .forecast(obs, h) -> (load_kw[h], pv_kw[h])     # np.ndarray, kW, >= 0, [0] = hora actual, < 2 ms

optimizer.plan(soc, load, pv, price, co2, w_co2, w_cost, terminal_value, p) -> acciones_kw[H]
safety.clip_action(a_kw, soc_kwh) -> float válido
policy.BatteryAgent().act(obs_dict) -> float kW

data.load() -> DataFrame[timestamp, load_kw, pv_kw, price_eur_kwh, co2_kg_kwh]   # una fila por hora
data.validation_split(df) / train_split(df)          # validación = últimas 168 h de cada mes

sim.simulate(agent, df) -> SimResult(log, totals)    # idéntico a environment.py
sim.score(totals, baseline_totals(df)) -> {score, d_co2_pct, d_cost_pct, infractions}
    log hora a hora: columnas en sim.LOG_COLUMNS

models/forecaster.json, models/objective_refs.json (+ .pkl si hace falta) -> van en la raíz del ZIP
```

**Cómo validamos sin hacer trampas:** el test son las últimas semanas de cada mes, así que nuestra validación
son las **últimas 168 h de cada mes del train**, seguidas, como si fueran un test. Lo que se aprende
(perfiles, referencias) sale solo del resto del train.

---

## 7. La entrega: un solo `agent.py`

**El problema:** el servidor solo carga `agent.py` y su escáner de seguridad no permite trucos para importar
otros ficheros. Pero si los tres editásemos un único `agent.py`, sería el caos.

**La solución:** cada uno trabaja en sus módulos de `src/battery/`, como capítulos de un libro, y
`scripts/build_submission.py` los **encuaderna** en un único `dist/agent.py` justo antes de entregar.
Además comprueba que no usamos nada prohibido, crea `dist/submission.zip`, lo ejecuta aislado del repo
(tiene que decidir exactamente lo mismo que el código original) y le pasa el validador oficial.

Por eso, el código de los módulos que se empaquetan (`params`, `obs`, `adapter`, `safety`, `forecaster`,
`optimizer` y `policy`) tiene que cumplir estas reglas. `build_submission.py` las comprueba y falla si no se cumplen:

- **Solo estas librerías:** `numpy`, `pandas`, `scipy`, `sklearn`, `joblib`, `xgboost`, `lightgbm`, `math`, `random`,
  `datetime`, `collections`, `itertools`, `json`, `pathlib`, `typing`, `dataclasses`, `functools`, `heapq`, `bisect`,
  `re`, `copy` y `pickle`. Nada de `os`, `sys`, `subprocess`, `importlib`, `inspect`, etc.
- **Ninguna llamada a `.stack(...)`**, ni siquiera `np.stack` (usad `np.vstack`). Tampoco `eval`, `exec`,
  `compile`, `globals`, `locals`, `vars` ni `__import__`.
- **Imports entre módulos, relativos** (`from .optimizer import plan`). El empaquetador los quita.
- **Nombres únicos:** dos módulos no pueden definir el mismo nombre. Cada librería se importa igual en todos.
- **Compatible con Python 3.9:** `Optional[...]`, no `X | None`.
- **Sin `print` ni escritura de ficheros.** Los modelos se leen con `Path(__file__).parent`.
- **El agente nunca lanza una excepción.** Ante cualquier error, devuelve una acción segura.
- **Tiempo:** `eval.py` proyecta el tiempo a 2.016 h y tiene que quedar por debajo de 40 s (el límite oficial es 60 s).

Los ficheros que no se empaquetan (`sim.py`, `data.py`, `baselines.py`, `synthetic.py`, `eval.py`, `scripts/`
y `analysis/`) pueden usar lo que quieran.

---

## 8. El día a día

### Preparar el entorno (en la nube o en el portátil)
Trabajamos con **sesiones de Claude en la nube** (claude.ai/code, conectadas al repo) y también en portátiles
(Aitor en Mac, el resto en Windows). Todo está pensado para funcionar igual en los tres sitios:
- **Los datos oficiales están en el repo, comprimidos en `oficial.zip`.** `python scripts/preparar_oficial.py`
  los descomprime en `oficial/` (en Python, así que funciona en Mac, Windows y Linux). Además, `eval.py`,
  `calibrate_sim.py`, `build_submission.py` y los tests lo hacen solos si falta. `oficial/` es solo la copia
  descomprimida y git la ignora.
- Dentro están `oficial/docs/ENUNCIAT.md`, `oficial/docs/GUIA_VARIABLES.md`, `oficial/starter_kit/environment.py`
  (el simulador oficial) y el tutorial.
- Librerías: `pip install -r requirements.txt pytest matplotlib`. En Windows, el entorno virtual se activa con
  `.venv\Scripts\activate` y en Mac con `source .venv/bin/activate`.
- **Una sesión en la nube empieza de cero cada vez:** clona el repo, no tiene nada instalado y usa una rama propia
  (`claude/...`). Por eso cada prompt de arranque empieza con un PASO 0 que fija la rama del rol, instala, descomprime
  y comprueba. En una sesión en la nube, haz commit y push a menudo: el contenedor se borra tras un rato de inactividad.
- Si `eval.py` dice "Datos sintéticos" en lugar de "Datos oficiales", algo ha fallado al preparar `oficial/`: esos
  datos sirven para probar el circuito, **no para tomar decisiones**.

### Comandos

```bash
pip install -r requirements.txt pytest matplotlib       # instalar (requirements-dev.txt añade jupyter)
python scripts/preparar_oficial.py          # descomprimir oficial.zip en oficial/ (también se hace solo)
python -m pytest -q                         # ¿funciona todo? (también lo comprueba GitHub en cada PR)
python eval.py                              # ¿cuánto saca nuestro agente en validación?
python eval.py --agent all                  # comparativa nothing / greedy / mpc / oracle
python eval.py --log "qué he cambiado"      # medir y dejarlo apuntado en results/experiments.csv
python eval.py --fc-noise 0.1               # ¿y si las previsiones de precio/CO2 fallaran un 10 %?
python eval.py --save-hourly                # guardar el detalle hora a hora (para gráficas)
python scripts/calibrate_sim.py             # ¿nuestro simulador sigue dando lo mismo que el oficial?
python scripts/p1_ablaciones.py             # ¿cuánto aporta cada pieza y cómo aguanta? (P1, 2-3 min)
python scripts/p1_auditoria.py              # auditoría completa del agente (P1, unos 10 min)
python scripts/train_forecaster.py          # regenerar los modelos de models/ (P2)
python scripts/build_submission.py          # crear dist/submission.zip y comprobarlo
python eval.py --agent dist                 # medir el agent.py empaquetado
```

### Trabajar con git
1. Trabaja siempre en **tu rama**. **Nunca hagas push a `main`.**
2. Sincronízate a menudo, al empezar y después de cada fusión: `git fetch origin && git merge origin/main`.
3. **Pull requests pequeñas y frecuentes**, como mínimo una por cada punto de sincronización del equipo. Antes de abrir una:
   - los tests en verde (`python -m pytest -q`);
   - `python eval.py --log "..."`, con la tabla pegada en la PR y comparada con `main`;
   - si has tocado módulos que se empaquetan, `python scripts/build_submission.py` en verde;
   - la plantilla de la PR rellena.

   El integrador revisa y fusiona con "Create a merge commit".
4. **Si una idea no mejora, también se apunta** en `docs/decisiones.md`: al jurado le interesa lo que descartamos y por qué.
5. **Los cambios grandes de estrategia los decide el equipo.** Claude propone; tu humano decide.

---

## 9. Lo que Claude no debe hacer

- Editar ficheros de otro rol, hacer push a `main` o fusionar pull requests (eso lo hace el integrador).
- Subir la carpeta descomprimida `oficial/` ni `data/` (los datos ya están en `oficial.zip`), ni ficheros grandes generados.
- Usar librerías prohibidas en el código que se empaqueta.
- Cambiar los contratos de la sección 6 sin acordarlo antes.
- Afirmar que algo mejora sin un número de `eval.py`.

---

## 10. Glosario

| Término | Qué significa aquí |
|---|---|
| **SOC** | *State of charge*: la energía que hay en la batería (0–2.000 kWh) |
| **PVPC** | La tarifa eléctrica regulada española, con un precio distinto cada hora |
| **Peso de una hora** | Lo "mala" que es una hora para comprar: `0,7·CO₂/medio + 0,3·precio/medio` |
| **Regla del 11 %** | Mover energía de la hora A a la B solo compensa si B es al menos un 11 % peor (por el 10 % que se pierde) |
| **LP** | Programación lineal: el método matemático que calcula el plan óptimo de 24 h |
| **MPC** | Control predictivo: planificar 24 h, ejecutar 1 h y volver a planificar (como un GPS) |
| **Oracle** | Nuestro planificador con información perfecta de todo el futuro. Es el techo teórico, imposible de superar |
| **Contrato** | Lo que un módulo promete recibir y devolver, para que las piezas encajen |
| **Infracción** | Pedir una acción físicamente imposible. Penaliza y siempre la evitamos |
| **Dry-run** | La prueba rápida de la web (48 pasos), gratis e ilimitada, antes de un envío oficial |
| **Integrador** | La persona que revisa las PRs, mantiene `main` y hace los envíos |

Más documentación:
- `docs/registro-montaje.md`: cómo y por qué se montó el repo.
- `docs/reto.md`: la especificación verificada.
- `docs/equipo.md`: preparación y calendario.
- `docs/prompts-arranque.md`: el primer mensaje para cada Claude.
- `docs/decisiones.md`: el registro de decisiones para el jurado.
- `docs/contexto-chat.md`: el contexto del evento.
