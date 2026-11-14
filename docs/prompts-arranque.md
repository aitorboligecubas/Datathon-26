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
1. Ejecuta `python eval.py --agent all` y explícame la diferencia entre mpc y oracle.
2. Añade a baselines.py un agente "MPC con previsión perfecta de demanda y solar" (sabe la demanda y la
   solar reales del df) para separar cuánto pierde el MPC por la previsión y cuánto por el horizonte de 24 h.
   Pide al integrador que lo registre en eval.py.
3. Mejora el MPC y mide cada cambio con eval.py --log:
   - valor terminal de la carga;
   - horizonte más largo que 24 h, rellenando el precio y el CO2 con lo de hace 24 h o 168 h;
   - vaciar la batería al final del episodio si la carga final no puntúa (VERIFICAR);
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
Los datos oficiales están en starter_kit/ (no se suben a git: el repo es público).

Objetivo: prever la demanda y la solar de las próximas 25 h lo mejor posible, respetando el contrato
Forecaster.update(obs) / forecast(obs, h) y tardando menos de 2 ms por llamada.

Por orden:
1. Lee starter_kit/tutorial.ipynb y environment.py.
   - Implementa data.build_hourly(): contador a 15 min, inversor a 5 min (3 inversores), precio_pvpc y co2_red,
     todo pasado a una tabla horaria con columnas timestamp, load_kw, pv_kw, price_eur_kwh y co2_kg_kwh.
   - Guárdala en data/processed/hourly.csv.
   - Comprueba que las unidades coinciden con las de obs: CO2 en kg/kWh y precio en €/kWh.
2. Averigua el formato exacto de obs["noves_dades_5min"] en environment.py (tipo, columnas, unidades)
   y pásaselo al integrador para que ajuste adapter.recent_load_pv.
3. Amplía tests/test_forecaster.py y escribe un script que mida el error (MAE por antelación, 1..24 h) en validación.
4. Mejora la previsión y mide cada cambio:
   - la solar según el mes, porque obs trae el timestamp;
   - festivos y vacaciones del campus (entradas_salidas.csv);
   - la meteo, si viene en noves_dades_5min;
   - un GBDT (lightgbm/sklearn) guardado como .pkl con joblib en models/.
5. python scripts/train_forecaster.py, que regenera models/ con datos reales.
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
1. Lee starter_kit/environment.py y compáralo línea a línea con src/battery/sim.py y adapter.py.
   Resuelve la lista VERIFICAR de docs/reto.md:
   - penalización 0,20 o 1,00;
   - excedente a 0 o a 0,04 €/kWh;
   - si la previsión empieza en t+1;
   - formato de noves_dades_5min;
   - qué pasa con una acción inválida;
   - si se puntúa la carga final.
2. Ejecuta la plantilla oficial (starter_kit/agent.py) en los dos simuladores con los mismos datos.
   El score tiene que coincidir. Si no coincide, corrige sim.py (y adapter.py/params.py si eres el integrador).
3. analysis/: a partir de `python eval.py --agent all --save-hourly`, prepara estas gráficas:
   - una semana tipo: carga de la batería sobre el CO2 del mix;
   - CO2 y € ahorrados acumulados;
   - comparativa nothing / greedy / mpc / oracle ("capturamos el X % del máximo teórico");
   - análisis por mes y robustez con --fc-noise.
4. Mantén docs/decisiones.md: cada decisión con su número, incluidas las descartadas.
5. presentation/: esqueleto del pitch (problema → idea → método → resultados → límites → qué haríamos después).
Como integrador: revisa las PRs, fusiona con "merge commit", genera dist/submission.zip y apunta cada envío en docs/envios.md.
```
