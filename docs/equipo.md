# Cómo trabajamos: 3 personas, 3 Claudes, un repo (Opción B)

Owner: integrador (P3; **provisionalmente Aitor**, ver abajo).

## Quién es quién (rellenad los nombres)

| Rol | Persona | GitHub | Rama | Perfil ideal |
|---|---|---|---|---|
| **P1 · Optimización y robustez** | Aitor Bolige | @aitorboligecubas | `p1-optimizador` | Quien tenga más base matemática (optimización, razonar con rigor) |
| **P2 · Datos y análisis** | Ivan Torres | @ivan-torres-ros | `p2-datos` | Quien se mueva mejor con pandas y gráficas, y sepa sacar conclusiones de los datos |
| **P3 · Relato, presentación e integración** | _pendiente_ | _@usuario_ | `p3-relato` | Quien comunique mejor y sea más ordenado |
| **Integrador provisional** (hasta que haya P3) | Aitor Bolige | @aitorboligecubas | — | Dueño del repo, con permisos para fusionar |

Si sois 4, la cuarta persona se queda con la integración (pull requests, `main` y envíos) y P3 se dedica solo
a la presentación.

### Mientras no haya P3

- **Integración → Aitor (provisional).** Fusiona las pull requests en `main` (también las de Ivan), mantiene `main`
  en verde, genera el ZIP, pasa el dry-run, hace los envíos oficiales (`docs/envios.md`) y edita los ficheros del
  integrador cuando haga falta. **Prioridad hoy: dry-run y primer envío oficial**, para fijar el PIN del equipo.
- **Presentación → espera hasta la sincronización de las 17:00.** Si para entonces sigue sin haber P3:
  - **opción A:** Ivan prepara las gráficas con su frase de "qué demuestra" (ya es tarea suya) y Aitor monta el guion;
  - **opción B:** una sesión de Claude hace el borrador del guion y de las preguntas difíciles del jurado
    (encargo de P3 en `docs/prompts-arranque.md`), y Aitor e Ivan lo revisan.
- Cuando llegue P3, recupera la integración y Aitor vuelve a dedicarse solo a P1.

## 0. Por qué estos roles (y cuál es el más difícil)

Los datos cambiaron el reparto inicial:
- La solar casi no cuenta, así que prever el consumo apenas cambia las decisiones.
- El agente ya captura el **99,3 % del máximo teórico** (6,08 sobre 6,12).
- **Queda poco que ganar en el leaderboard y mucho que ganar ante el jurado.**

| Rol | Dificultad de razonamiento | Volumen de trabajo | Impacto en el resultado |
|---|---|---|---|
| **P1** | **La más alta.** Con un margen tan pequeño, una idea puede mejorar la validación por casualidad y empeorar el test (sobreajuste). Cada cambio tiene que justificarse, no solo puntuar más | Medio | Pocos puntos, pero da la solidez técnica que pregunta el jurado |
| **P2** | Media-alta: hacer las preguntas correctas a los datos | Medio-alto | Aporta las pruebas y los argumentos de negocio para el jurado |
| **P3** | Media, de otro tipo: comunicar, priorizar y decidir | **El más alto** (presentación + integración) | **El más alto: el jurado decide** |

## 1. Qué hace cada rol

### P1 · Optimización y robustez — "que la solución sea sólida y esté justificada"
- **Desglose de cada pieza:** cuántas décimas aporta el LP, el valor de la carga al final del horizonte y vaciar la
  batería al final. Para el jurado: "esta pieza aporta X".
- **Robustez:**
  - ¿qué pasa si el servidor evalúa cada semana por separado (con la carga reiniciada al 50 %)?
  - ¿y con previsiones de precio y CO₂ con ruido?
  - cero infracciones, siempre.
- **Cerrar la distancia hasta el techo** solo con cambios que se puedan justificar, no con ajustes a medida de la validación.
- **Estrategia cerrada el sábado a medianoche.**

### P2 · Datos y análisis — "los números que convencen"
- **Calidad de los datos:** falta noviembre de 2025, hay horas con consumo 0 y los cambios de hora.
  Medir si corregirlos cambia algo.
- **Cuándo es mala la red:** CO₂ y precio por hora y por mes. ¿Van juntos, o hay conflicto entre el 70 % del CO₂
  y el 30 % del precio?
- **Por qué el ahorro máximo es de ~6 %:** la batería es el 7 % del consumo diario, se pierde un 10 % en cada
  ida y vuelta, y las diferencias entre horas son las que son.
- **La pregunta de negocio para UPC Sostenible:** ¿y si la batería fuese de 1, 4 u 8 MWh? ¿Cuánto CO₂ y
  cuántos € al año? ¿Compensa invertir?
- Es dueño de `analysis/`: produce las gráficas y las cifras que usará la presentación.

### P3 · Relato, presentación e integración — "que el jurado lo entienda y lo compre"
- **Presentación:**
  - guion y slides (problema → idea → método → resultados → límites → recomendación a UPC Sostenible);
  - ensayo;
  - respuestas preparadas para las preguntas difíciles.
- **Registro de decisiones** (`docs/decisiones.md`): cada decisión con su número, incluidas las descartadas.
- **Integración:** revisar y fusionar las pull requests, mantener `main` en verde, generar el ZIP, pasar el dry-run
  y hacer los envíos oficiales (`docs/envios.md`).
- **Simulador:** ya está calibrado con el oficial. Solo hay que comprobar que sigue cuadrando
  (`python scripts/calibrate_sim.py`).

## 2. ¿A la vez o uno detrás de otro? Por fases

**Hasta el sábado por la noche, los tres trabajan en paralelo; el domingo por la mañana todos convergen en la
presentación.** P3 no espera a los demás: empieza el relato con los números actuales y los va actualizando a medida
que P1 y P2 entregan.

| Fase | Cuándo | P1 · Optimización | P2 · Datos | P3 · Relato + integración |
|---|---|---|---|---|
| **0 · Arranque** (juntos) | Sáb hasta ~13:30 | Preparar el portátil | Preparar el portátil | Repo privado, invitar al equipo, dry-run y **primer envío oficial** |
| **1 · Explorar** (en paralelo) | Sáb ~13:30–17:00 | Desglose de cada pieza y escenario "por semanas" | Calidad de datos y patrones de CO₂ y precio | Esqueleto del guion y de las slides con los números de ahora |
| **Sincronización** (15 min) | **Sáb 17:00** | Enseña el desglose | Enseña los patrones | Fusiona las PRs, hace un envío y decide qué historia contamos |
| **2 · Converger** (en paralelo) | Sáb 17:00–00:00 | Mejoras justificadas y robustez. **Estrategia cerrada a las 00:00** | Escenarios de tamaño de batería y gráficas finales | Slides con el material de P1 y P2 |
| **Sincronización** (15 min) | **Sáb 21:00** (cena) | | | Fusiona las PRs y hace un envío. Primer repaso del pitch |
| **Sincronización** | **Dom 0:00** | Última PR de estrategia | Últimas cifras | Último merge grande y envío. A dormir |
| **3 · Cerrar** (en serie) | Dom 9:00–9:30 | Solo arreglos de errores | Repasa las cifras de las slides | **9:30: congelación del código** y envío final |
| | Dom 9:30–11:30 | Prepara las respuestas técnicas | Prepara las respuestas sobre los datos | Termina las slides y ensaya con los tres |
| **Entrega** | **Dom 12:00** | | | Fin de las entregas |
| **Demo** | Dom 14:00 | Responde a las preguntas técnicas | Responde a las de datos y negocio | **Presenta** |

## 3. Preparar GitHub (una vez, lo hace quien tenga el repo)

1. **Hacer el repo privado durante el evento.**
   Settings → General → Danger Zone → Change visibility → Private.
   Ahora mismo es público: cualquiera ve la estrategia, y los datos oficiales no deben subirse.
2. **Invitar al equipo:** Settings → Collaborators → Add people, con los usuarios de GitHub de la tabla.
3. ~~Fusionar la estructura inicial en `main`~~: ya está hecho.
4. **Proteger `main`** (recomendado):
   - Settings → Branches → Add branch ruleset (o "Add rule") sobre `main`.
   - Activar "Require a pull request before merging" y "Require status checks to pass", con el check `tests` de la CI.
5. **Modo de fusión:** Settings → General → Pull Requests → dejar "Allow merge commits" activado.
   Así las ramas personales se sincronizan sin conflictos.

## 4. Preparar cada portátil (cada persona, unos 10 min)

```bash
git clone https://github.com/aitorboligecubas/Datathon-26.git
cd Datathon-26
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
git checkout -b p1-optimizador                          # o p2-datos / p3-relato
```

Descomprimid el ZIP oficial del reto en la raíz del repo y renombrad la carpeta a `oficial/`
(git la ignora y no se sube):

```bash
unzip paquet_participants_datathon_upc_2.zip -x "__MACOSX/*" && mv paquet_participants_datathon_upc oficial
python -m pytest -q                        # todo en verde
python scripts/calibrate_sim.py            # nuestro simulador = el oficial
python eval.py --agent all                 # mpc 6,08 / oracle 6,12 con datos oficiales
```

Arrancad Claude Code dentro de la carpeta (`claude`), que lee `CLAUDE.md` automáticamente, y pegad como primer
mensaje el prompt de vuestro rol de `docs/prompts-arranque.md`.

## 5. El día a día con git

```text
           p1-optimizador ──●──●──PR──┐         ┌──●──●──PR──┐
main ──────────────────────────────────●(merge)──●────────────●(merge)── ...
           p2-datos       ──●──●──●──PR──────────┘
```

- **Sincronizarse con `main`**: después de cada merge, y siempre antes de abrir una PR.

  ```bash
  git fetch origin && git merge origin/main
  ```

- **Abrir una PR**, con commits pequeños y un tema por PR:

  ```bash
  git push -u origin p1-optimizador
  ```

  Luego, en GitHub, abrid la PR de vuestra rama → `main` y rellenad la plantilla. Hay que pegar la tabla de `eval.py`.
- **Quién fusiona**: solo el integrador, con la CI en verde y si la tabla de `eval.py` no empeora (o si el empeoramiento
  está justificado).
- **Si necesitas un cambio en un fichero de otro rol**: apúntalo en tu PR, en "Peticiones a otros roles", y díselo a
  esa persona. Tu Claude no lo toca.
- **`results/experiments.csv`** es el registro común de experimentos. Lo escribe `eval.py --log` y git junta las líneas
  de todos sin conflictos (`.gitattributes`, `merge=union`).

## 6. Envíos oficiales

- Hay 10 al día. **Antes de cada uno, pasad el dry-run de la web (gratis, ilimitado, 48 pasos).**
- Apuntad cada envío en `docs/envios.md` con el commit, el score local y el del leaderboard.
- El leaderboard público es solo el 50 %, así que no os ajustéis a él.
