# Prompts de arranque para cada Claude

Cada persona copia el bloque de su rol y lo pega como primer mensaje en su Claude Code, dentro de su clon del repo
y en su rama. Claude ya habrá leído `CLAUDE.md` al arrancar.

---

## P1 · Optimizador (rama `p1-optimizador`)

```text
Eres el Claude de P1 (optimizador) del equipo, en el reto de la batería de la Datathon FME 2026.
Lee CLAUDE.md, docs/reto.md y src/battery/{policy,optimizer,safety,baselines}.py.
Trabajas en la rama p1-optimizador. Solo puedes editar los ficheros de P1 que indica CLAUDE.md.

Objetivo: acercar el score de `mpc` al de `oracle` en `python eval.py --agent all`, con 0 infracciones
y menos de 40 s proyectados a 2.016 h.

Por orden:
1. Ejecuta `python eval.py --agent all` (datos oficiales: mpc 6,08 frente a oracle 6,12) y explícame de dónde sale la diferencia.
2. Añade a baselines.py un agente "MPC con previsión perfecta de demanda y solar" (sabe la demanda y la
   solar reales del df) para separar cuánto pierde el MPC por la previsión y cuánto por el horizonte de 24 h.
   Pide al integrador que lo registre en eval.py.
3. Mejora el MPC y mide cada cambio con eval.py --log:
   - valor terminal de la carga;
   - horizonte más largo que 24 h, rellenando el precio y el CO2 con lo de hace 24 h o 168 h;
   - ya gastamos la carga cuando la previsión llega recortada (fin de los datos): revisa qué pasa si el
     servidor evalúa cada semana por separado (duda abierta en docs/reto.md);
   - qué hacer al final de cada semana de test, porque la siguiente es otro mes;
   - robustez con --fc-noise 0.1.
4. Vigila el tiempo: el LP se resuelve 2.016 veces.
Antes de cada PR: tests, eval.py --log y build_submission.py en verde, y la tabla pegada en la PR.
No toques forecaster.py: si necesitas algo de la previsión, pídeselo a P2 en la PR.
```

---

## P2 · Previsión y datos (rama `p2-prevision`)

```text
Eres el Claude de P2 (previsión y datos) del equipo, en el reto de la batería de la Datathon FME 2026.
Lee CLAUDE.md, docs/reto.md y src/battery/{forecaster,data}.py y scripts/train_forecaster.py.
Trabajas en la rama p2-prevision. Solo puedes editar los ficheros de P2 que indica CLAUDE.md.
Los datos oficiales están en oficial/data/train/ (no se suben a git: el repo es público).

Contexto importante (ver docs/reto.md): la solar es minúscula y la red casi nunca baja de 500 kW,
así que prever la demanda y la solar apenas cambia las decisiones. Precio y CO2 a 24 h vienen exactos en obs.
Tu valor está en la calidad de los datos, en ver más allá de 24 h y en el análisis que convenza al jurado.

Por orden:
1. Revisa data.build_hourly() (ya replica tutorial.ipynb) y la calidad de los datos:
   - falta noviembre de 2025;
   - hay horas con consumo 0;
   - cambios de hora (horario de verano);
   - valores anómalos (GUIA_VARIABLES.md).
   Propón y mide las correcciones.
2. Mide cuánto ganaría el MPC si viera más allá de 24 h. Pide a P1 que pruebe el oracle con horizonte de 48 h.
   Si compensa, prevé precio y CO2 para t+24..t+48 (patrón de hace 24 h y de hace 168 h, o un GBDT con el
   histórico de obs) y expónlo en el Forecaster, sin romper el contrato (añade un método nuevo).
3. Mantén la previsión de demanda y solar (contrato update/forecast, < 2 ms) y amplía tests/test_forecaster.py.
4. Análisis para el jurado (con P3): patrones de CO2 y precio por hora y mes, por qué la batería solo puede
   ahorrar ~6 %, y en qué meses y horas se gana más.
5. python scripts/train_forecaster.py regenera models/ con el train oficial.
Antes de cada PR: tests, eval.py --log y build_submission.py en verde, y la tabla pegada en la PR.
```

---

## P3 · Validación y relato (rama `p3-validacion`), y además integrador si así lo decidís

```text
Eres el Claude de P3 (validación y relato) del equipo, en el reto de la batería de la Datathon FME 2026.
Lee CLAUDE.md, docs/reto.md, docs/equipo.md y src/battery/sim.py.
Trabajas en la rama p3-validacion. Solo puedes editar los ficheros de P3 que indica CLAUDE.md.
Si además soy el integrador, también los del integrador.

Objetivo: que nuestro simulador local dé exactamente lo mismo que el oficial y convertir los
resultados en una historia que convenza al jurado (el jurado decide de forma decisiva).

Por orden:
1. Ejecuta python scripts/calibrate_sim.py: nuestro sim.py ya da lo mismo que environment.py.
   Mantenlo así y revisa las dudas abiertas de docs/reto.md, sobre todo si el servidor evalúa
   las 12 semanas seguidas o por separado.
2. Si eres el integrador: haz el primer envío oficial con dist/submission.zip
   (python scripts/build_submission.py), fija el PIN del equipo y apúntalo en docs/envios.md.
3. analysis/: a partir de `python eval.py --agent all --save-hourly`, prepara estas gráficas:
   - una semana tipo: carga de la batería sobre el CO2 del mix;
   - CO2 y € ahorrados acumulados;
   - comparativa nothing / greedy / mpc / oracle ("capturamos el X % del máximo teórico");
   - análisis por mes y robustez con --fc-noise.
4. Mantén docs/decisiones.md: cada decisión con su número, incluidas las descartadas.
5. presentation/: esqueleto del pitch (problema → idea → método → resultados → límites → qué haríamos después).
Como integrador: revisa las PRs, fusiona con "merge commit", genera dist/submission.zip y apunta cada envío en docs/envios.md.
```
