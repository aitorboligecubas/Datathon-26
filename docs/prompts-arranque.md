# Prompts de arranque para cada Claude

Cada persona copia el bloque de su rol y lo pega como **primer mensaje** de su sesión de Claude Code: en la nube
(claude.ai/code, con el repo `aitorboligecubas/Datathon-26`) o en su portátil (Mac o Windows). Claude ya habrá
leído `CLAUDE.md` al arrancar.

Cada prompt empieza con un **PASO 0** que lo deja todo listo sin hacer nada a mano:
- da permiso para trabajar en la rama del rol (si no, una sesión en la nube usaría su propia rama `claude/...`);
- instala las librerías y descomprime los datos oficiales;
- comprueba que se ven los datos oficiales y la puntuación esperada (mpc 6,09 / oracle 6,12).

Por qué estos roles y el plan por fases: `docs/equipo.md`.

---

## P1 · Optimización y robustez (rama `p1-optimizador`)

```text
PASO 0 — antes de nada (no te lo saltes):
a) Rama: trabaja en la rama p1-optimizador. Si no existe, créala desde main
   (git fetch origin && git checkout -b p1-optimizador origin/main); si existe, cámbiate a ella y sincroniza
   (git merge origin/main). Haz commit y push SOLO a p1-optimizador (tienes mi permiso para esa rama, aunque la sesión
   te proponga otra). Cuando yo te lo pida, abre la pull request de p1-optimizador hacia main.
b) Prepara el entorno: pip install -r requirements.txt pytest matplotlib, y python scripts/preparar_oficial.py
   (descomprime oficial.zip, que está en el repo, en oficial/).
c) Comprueba que todo cuadra: python -m pytest -q, python scripts/calibrate_sim.py y
   python eval.py --agent all. eval.py tiene que decir "Datos oficiales" (NO "sintéticos") y dar
   mpc 6,09 y oracle 6,12 con 0 infracciones, y calibrate_sim tiene que decir OK en las dos líneas.
   Si algo no cuadra, PARA y dímelo antes de seguir.
Después, resúmeme en 3 líneas qué has entendido de tu rol, y empieza.

Eres el Claude de P1 (optimización y robustez) del equipo, en el reto de la batería de la Datathon FME 2026.
Lee CLAUDE.md, docs/equipo.md (sección 1, P1), docs/reto.md y src/battery/{policy,optimizer,safety,baselines}.py.
Trabajas en la rama p1-optimizador. Solo puedes editar los ficheros de P1 que indica CLAUDE.md;
tus scripts nuevos van en scripts/p1_*.py.

Situación: el MPC saca 6,09 en validación frente a 6,12 del techo teórico (oracle), con 0 infracciones.
Queda muy poco margen en puntos. Tu valor está en que la solución sea SÓLIDA y JUSTIFICADA:
este es el rol con más carga de razonamiento. Con un margen tan pequeño, una mejora puede ser casualidad
(sobreajuste a la validación). Desconfía de las mejoras pequeñas y explica siempre el porqué.

Por orden (fase 1, hasta las 17:00 del sábado):
1. Desglose de cada pieza (scripts/p1_ablaciones.py, usando battery.sim directamente):
   ¿cuántas décimas aporta cada una?
   - LP frente a greedy;
   - valor de la carga al final del horizonte (con y sin);
   - vaciar la batería al final del episodio (con y sin);
   - previsión de consumo real frente a la nuestra (un MPC que conoce el consumo y la solar reales).
   Saca una tabla que P3 pueda poner en una slide.
2. Robustez:
   - simula el caso en que el servidor evalúa cada semana por separado (carga reiniciada al 50 %, previsión
     recortada al final de cada semana) y compara;
   - previsiones con ruido (--fc-noise 0.05 / 0.1 / 0.2);
   - comprueba que sigue habiendo 0 infracciones en todos los casos.
Fase 2 (17:00–00:00):
3. Solo mejoras que se puedan justificar (por ejemplo, horizonte > 24 h con el patrón de precio/CO2 de
   hace 24 h o 168 h, o un mejor valor final). Mídelas también con ruido y por semanas, no solo en la validación.
4. Estrategia cerrada a medianoche. Pasa a P3 un resumen de 5 líneas de "qué hace el agente y por qué".
Antes de cada PR: tests, eval.py --log y build_submission.py en verde, y la tabla pegada en la PR.
Si necesitas algo de otro rol (por ejemplo, un agente nuevo en eval.py), pídelo en la PR; no lo toques.

Mientras no haya P3, tu humano (Aitor) es también el INTEGRADOR PROVISIONAL (docs/equipo.md). Cuando te lo pida,
ayúdale con la integración:
- revisar las PRs de Ivan;
- comprobar que main está en verde (pytest, calibrate_sim, build_submission);
- generar dist/submission.zip para el dry-run y los envíos (docs/envios.md) y pasármelo (en la nube,
  como fichero adjunto): la subida a la web la hago yo;
- editar los ficheros del integrador.
El merge de las PRs lo hace él en GitHub. Primera tarea de integración: dry-run y primer envío oficial.
```

---

## P2 · Datos y análisis (rama `p2-datos`)

```text
PASO 0 — antes de nada (no te lo saltes):
a) Rama: trabaja en la rama p2-datos. Si no existe, créala desde main
   (git fetch origin && git checkout -b p2-datos origin/main); si existe, cámbiate a ella y sincroniza
   (git merge origin/main). Haz commit y push SOLO a p2-datos (tienes mi permiso para esa rama, aunque la sesión
   te proponga otra). Cuando yo te lo pida, abre la pull request de p2-datos hacia main.
b) Prepara el entorno: pip install -r requirements.txt pytest matplotlib, y python scripts/preparar_oficial.py
   (descomprime oficial.zip, que está en el repo, en oficial/).
c) Comprueba que todo cuadra: python -m pytest -q, python scripts/calibrate_sim.py y
   python eval.py --agent all. eval.py tiene que decir "Datos oficiales" (NO "sintéticos") y dar
   mpc 6,09 y oracle 6,12 con 0 infracciones, y calibrate_sim tiene que decir OK en las dos líneas.
   Si algo no cuadra, PARA y dímelo antes de seguir.
Después, resúmeme en 3 líneas qué has entendido de tu rol, y empieza.

Eres el Claude de P2 (datos y análisis) del equipo, en el reto de la batería de la Datathon FME 2026.
Lee CLAUDE.md, docs/equipo.md (sección 1, P2), docs/reto.md, oficial/docs/GUIA_VARIABLES.md,
src/battery/data.py y src/battery/forecaster.py.
Trabajas en la rama p2-datos. Solo puedes editar los ficheros de P2 que indica CLAUDE.md
(incluido analysis/); tus scripts nuevos van en analysis/ o en scripts/p2_*.py.
Los datos oficiales están en oficial/data/train/ (se descomprimen de oficial.zip en el PASO 0).

Situación: la solar es minúscula (26 kW de media frente a ~1.100 kW de consumo), así que prever el consumo
apenas cambia las decisiones. Tu valor está en la CALIDAD de los datos y en las PRUEBAS que convencen al
jurado: tú produces las cifras y las gráficas de la presentación.

Por orden (fase 1, hasta las 17:00 del sábado):
1. Calidad de los datos (data.build_hourly ya replica tutorial.ipynb):
   - falta noviembre de 2025;
   - hay horas con consumo 0;
   - cambios de hora;
   - valores anómalos.
   Propón correcciones y mide si cambian el score (eval.py --log).
2. Patrones (analysis/): CO2 y precio por hora del día y por mes. ¿Cuándo es sucia la red? ¿Coinciden las horas
   sucias con las caras, o hay conflicto entre el 70 % del CO2 y el 30 % del precio? Gráficas claras,
   pensadas para una slide.
Fase 2 (17:00–00:00):
3. Por qué el ahorro máximo es de ~6 %: la batería es el 7 % del consumo diario, se pierde un 10 % en cada
   ida y vuelta, y las diferencias entre horas son limitadas. Cuantifícalo.
4. Pregunta de negocio para UPC Sostenible: con el oracle (baselines.OracleAgent y BatteryParams) calcula el
   ahorro de CO2 (toneladas/año) y de € con baterías de 1, 2, 4 y 8 MWh. ¿Dónde está el punto de rendimientos
   decrecientes? Es una recomendación concreta para el cliente.
5. Mantén la previsión (contrato Forecaster.update/forecast, < 2 ms). Si P1 demuestra que ver más allá de 24 h
   compensa, añade un método de previsión de precio/CO2 para t+24..t+48 sin romper el contrato.
6. python scripts/train_forecaster.py si cambias los datos (regenera models/).
Pasa a P3 cada gráfica con una frase de "qué demuestra".
Antes de cada PR: tests y eval.py --log en verde, y la tabla pegada en la PR.
```

---

## P3 · Relato, presentación e integración (rama `p3-relato`) — *rol pendiente de asignar; mientras tanto integra Aitor*

```text
PASO 0 — antes de nada (no te lo saltes):
a) Rama: trabaja en la rama p3-relato. Si no existe, créala desde main
   (git fetch origin && git checkout -b p3-relato origin/main); si existe, cámbiate a ella y sincroniza
   (git merge origin/main). Haz commit y push SOLO a p3-relato (tienes mi permiso para esa rama, aunque la sesión
   te proponga otra). Cuando yo te lo pida, abre la pull request de p3-relato hacia main.
b) Prepara el entorno: pip install -r requirements.txt pytest matplotlib, y python scripts/preparar_oficial.py
   (descomprime oficial.zip, que está en el repo, en oficial/).
c) Comprueba que todo cuadra: python -m pytest -q, python scripts/calibrate_sim.py y
   python eval.py --agent all. eval.py tiene que decir "Datos oficiales" (NO "sintéticos") y dar
   mpc 6,09 y oracle 6,12 con 0 infracciones, y calibrate_sim tiene que decir OK en las dos líneas.
   Si algo no cuadra, PARA y dímelo antes de seguir.
Después, resúmeme en 3 líneas qué has entendido de tu rol, y empieza.

Eres el Claude de P3 (relato, presentación e integración) del equipo, en el reto de la batería de la
Datathon FME 2026. Lee CLAUDE.md, docs/equipo.md (secciones 1, 2 y 6), docs/reto.md, docs/decisiones.md
y docs/registro-montaje.md.
Trabajas en la rama p3-relato. Puedes editar los ficheros de P3 y los del integrador que indica CLAUDE.md.

Situación: el jurado decide de forma decisiva y el margen en el leaderboard es de décimas, así que
la presentación es lo que más pesa. Es el rol con más volumen de trabajo. No esperes a los demás:
empieza con los números actuales y ve actualizándolos cuando P1 y P2 entreguen.

Fase 0 (ya):
1. Integración: comprueba que main está en verde (pytest, calibrate_sim, build_submission).
   Ayúdame con el dry-run en la web y el primer envío oficial, y apúntalo en docs/envios.md.
Fase 1 (hasta las 17:00 del sábado):
2. Guion del pitch en presentation/guion.md (unos 5 minutos):
   - problema (campus, CO2 y precio que cambian cada hora);
   - idea (llenar en horas limpias y baratas, regla del 11 %);
   - método (MPC como un GPS, LP);
   - resultados (6,09 frente a un techo de 6,12, 0 infracciones, 4 s);
   - transparencia (vaciar al final no se haría en la realidad);
   - recomendación para UPC Sostenible (tamaño de la batería, de P2);
   - qué haríamos con más tiempo.
3. Preguntas difíciles del jurado y respuestas en presentation/preguntas.md:
   - ¿por qué no ML o RL?
   - ¿y si las previsiones fallan?
   - ¿sobreajuste?
   - ¿por qué solo un 6 %?
   - ¿qué pasa con la carga final?
Fase 2 (17:00–00:00):
4. Slides con las gráficas de P2 y la tabla de desglose de P1. Cada slide, una idea.
5. Mantén docs/decisiones.md al día con lo que entra en cada PR.
6. Integración: revisa y fusiona las PRs (merge commit) en cada sincronización (17:00, 21:00, 00:00),
   genera el ZIP y haz un envío después de cada merge importante.
Fase 3 (domingo): congelación a las 9:30, envío final y ensayo del pitch con los tres.
```
