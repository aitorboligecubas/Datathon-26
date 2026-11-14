# Informe de P2 para Aitor (P1 e integrador)

Sábado 14/11, primera tarde. Escrito por el Claude de Ivan (P2) después de leer todo lo de P1 en `main`
(`policy.py`, `scripts/p1_ablaciones.py`, `results/p1_ablaciones.md`, `presentation/resumen-agente.md`,
`docs/decisiones.md`) y el borrador del guion (`presentation/guion.md`, rama `p1-optimizador`).

**Estado medido ahora en `main` (validación oficial, 1.848 h):** mpc **6,090** · oracle 6,115 · 0 infracciones ·
3,8 s · 16 tests en verde.

## Lo más urgente, en una pantalla

1. **Todavía no hay ningún envío oficial** (`docs/envios.md` está vacío). Es el mayor riesgo del equipo ahora mismo.
2. **Antes del primer envío, arregla `adapter.py`** (5 minutos, parche abajo). Si el servidor entrega las previsiones
   como array de numpy o Series de pandas, el agente devuelve 0 todas las horas y el score es 0, sin ningún aviso.
3. **La estrategia está bien cerrada.** He comprobado por mi lado que no queda nada que ganar: fuera de la avería de
   junio, agente y óptimo se diferencian en 0,0002 puntos.
4. **El guion tiene cinco cifras que conviene corregir** (lista abajo).
5. **Nadie está haciendo las slides.** Las 11 gráficas están listas y ordenadas por bloque del guion en
   `analysis/resumen_graficas.md`.

---

## 1. Qué ha hecho P2

### Código (ya en `main`, PR #2)

| Fichero | Qué cambia | Qué implica para P1 |
|---|---|---|
| `src/battery/forecaster.py` | Si el contador marcó exactamente 0 kW la hora anterior, `forecast()` devuelve 0 de consumo y de solar para la hora actual, y `update()` no aprende de ese 0 | El LP no descarga esa hora (el vertido vale 0). Es la primera capa; tu `cap_discharge` es la segunda. El contrato no cambia |
| `src/battery/data.py` | `read_meter()` (contador a 5 min con banderas de calidad) y `build_hourly(variant=...)`. `BATTERY_DATOS=limpio` o `real` selecciona la variante | **Por defecto no cambia nada**: `data.load()` sigue dando la tabla oficial, idéntica a la de antes. Las variantes son solo para análisis |
| `tests/test_forecaster.py` | Test de la regla de avería | — |

`models/` no se ha tocado: reentrenar con datos limpios da el mismo score (6,08 → 6,08), así que se quedan los de `main`.

### Análisis (en `analysis/`)

| Informe | Conclusión principal |
|---|---|
| `calidad_datos.md` | El consumo nocturno del dataset es un valor repetido (el real es un 19 % menor). Toda la distancia al óptimo es una avería del contador |
| `patrones.md` | La red es limpia y barata a mediodía y sucia y cara a las 21 h. CO₂ y precio coinciden salvo de madrugada |
| `techo.md` | El techo del 6 % lo pone el tamaño de la batería: `9,9 % × 1,34 − 11,0 % × 0,66 = 6,12` |
| `escenarios.md` | 2 MWh evitan 43 t de CO₂ y 92.000 € al año. Rendimientos decrecientes a partir de 4 MWh con 1.000 kW |
| `resumen_graficas.md` | Las 11 gráficas, ordenadas por bloque del guion, con la cifra que hay que decir en cada una |

Nuevo desde la PR #2 (pendiente de fusionar, rama `p2-datos`): `resumen_graficas.md`, este informe y dos gráficas
que el guion pedía y no existían: `figs/resultados_estrategias.png` (bloque 4) y `figs/resultados_semana_tipo.png`
(bloque 3).

---

## 2. Lo que P1 tiene que tener en cuenta

### 2.1 Riesgo antes del primer envío: `adapter.py` (fichero del integrador)

`from_official` hace `raw.get("preus_properes_24h") or [price_now]`. Con una lista funciona. Con un array de numpy
o una Series de pandas, `or` lanza `ValueError`; `MPCPolicy.act` lo captura y devuelve 0. El agente no haría nada
en todo el test, con 0 infracciones y **score 0**, y en local no se vería nunca porque `environment.py` pasa listas.

Parche que he probado en una copia (no he tocado el fichero, que es tuyo):

```python
def _to_series(x: Any, fallback: float) -> np.ndarray:
    """Lista, tupla, array de numpy o Series de pandas -> array 1-D; vacío o None -> [fallback]."""
    if x is None:
        return np.asarray([fallback], dtype=float)
    arr = np.asarray(x, dtype=float).ravel()
    return arr if arr.size else np.asarray([fallback], dtype=float)
```

y en `from_official`:

```python
    price = _to_series(raw.get("preus_properes_24h"), price_now)
    co2 = _to_series(raw.get("co2_properes_24h"), co2_now)
```

Resultado de la prueba: lista, tupla, array y Series dan la misma acción; lista vacía y `None` usan el valor
actual; la validación oficial sigue en **6,090 con 0 infracciones**. Falta añadir un caso a `tests/test_adapter.py`
con `np.array` y `pd.Series`, y pasar `build_submission.py` (el nombre `_to_series` no existe en otros módulos).

### 2.2 La distancia al techo: una corrección a `resumen-agente.md` y al guion

`resumen-agente.md` reparte los 0,03 puntos que faltan en "0,01 por no ver más allá de 24 h" y "0,02 por la avería".
Mi desglose por meses, con el agente actual, dice otra cosa:

| | Junio | Los otros 10 meses juntos | Total |
|---|---|---|---|
| Oracle − mpc (puntos) | 0,0245 | 0,0002 | 0,0247 |

**Todo lo que falta está en junio, el mes de la avería.** Ver más allá de 24 h vale 0,0002 puntos, no 0,01. Tu
variante "MPC con consumo y solar reales" (6,11) no llega a 6,12 porque en las horas de avería el plan de 24 h
sigue sin poder recolocar la descarga perdida, no porque le falte horizonte en general.

Es mejor argumento que el actual: "fuera de 14 horas de avería del contador, nuestro agente y el óptimo coinciden".
Y refuerza la decisión de no prever precio ni CO₂ a 48 h.

### 2.3 Las dos protecciones contra la avería son redundantes, y está bien

- **Capa de P2 (`forecaster`):** contador a 0 → previsión 0 para la hora actual → el LP no descarga.
- **Capa de P1 (`cap_discharge`):** nunca descargar más de lo que el campus compró la hora anterior.

Con las dos, el vertido en validación es de **0 kWh** (antes, 666 kWh). Lo que queda por perder (0,0245) es
inevitable: la primera hora de la avería no se puede prever, y durante las 14 horas no hay consumo que cubrir en
las horas caras.

Tu tope actúa además en algo que mi regla no cubre: consumos anómalos bajos pero no nulos. En validación hay 16
horas con menos de 500 kW de compra en la hora anterior, y casi todas son la avería. No he encontrado ningún caso
en que el tope quite una descarga que convenía.

### 2.4 El consumo nocturno del test tampoco es real

De 22:10 a 06:00 el contador no se lee y el dataset repite la lectura de las 22:05. El test se construye igual,
así que:
- **No afecta a las decisiones:** incluso con el consumo real (785 kW de noche), el campus compra más de 500 kW.
- **Sí afecta a los porcentajes:** el dataset infla el consumo un 5,5 %, y con él la referencia sin batería.
  Con las mismas semanas, el score pasa de 6,04 (datos limpios) a 6,46 (consumo real).
- **Para el jurado:** el ahorro en kg y en € es el mismo; el porcentaje real es mayor que el que puntúa.

### 2.5 Qué esperar del leaderboard

- **El score del test no será 6,09.** Depende de las semanas: en validación, agosto aporta 1,08 puntos y diciembre
  0,23. Tu prueba por semanas da 6,47. Cualquier valor entre 5,5 y 6,5 es coherente.
- **Las averías del contador en el test no se pueden prever.** En el train hay dos (17–18 de junio, 14 h; 6 de
  agosto, 1 h). Si cae una en una semana de test, costará unas centésimas a todos los equipos.
- **Los dos cambios de hora (26 de octubre y 29 de marzo) caen en semanas de test.** El agente usa la hora que le da
  el entorno y no cuenta pasos (tu arreglo de `episode_ends_soon`), así que un día de 23 o 25 horas no le afecta.
- **Señales de alarma tras el primer envío:**
  - score 0 con 0 infracciones → el agente no actúa: mira el `adapter` (2.1);
  - score cerca de 0,1 → el LP falla y entra la regla de respaldo en todas las horas (versión de scipy del servidor);
  - infracciones > 0 → no debería pasar; avísame con el detalle.

### 2.6 Detalles menores de `policy.py` (no urgentes, no cambian el score)

- `n_steps`, `self.t` y el import de `N_STEPS` ya no se usan para decidir nada desde que quitaste el contador de
  pasos. Se pueden dejar: no merece un cambio en código empaquetado a estas alturas.
- `terminal_quantile=0.25` no aporta nada (tu ablación: 0,00 con cualquier valor). Si el jurado pregunta por
  "parámetros ajustados", es el único número elegido a mano del agente y conviene tener la respuesta preparada:
  "lo probamos de 0 a 1 y el resultado no cambia".
- Los pesos del LP usan medias del train y el oracle, las del episodio. No importa: con datos limpios el agente
  iguala al oracle (6,04 frente a 6,04), así que ese desajuste vale 0.

---

## 3. Correcciones al guion (`presentation/guion.md`)

| Bloque | Dice | Propuesta | Por qué |
|---|---|---|---|
| 1 | "27 MWh cada día, 805 t de CO₂ y 1,4 M€ al año" | Mantenerlo diciendo "según el contador", o usar las cifras reales: **24,7 MWh al día, unas 750 t y 1,30 M€** | Las del guion incluyen el consumo nocturno inflado. Si después contamos que el contador sobrestima la noche, el jurado puede ver la contradicción |
| 2 | "Todos los días del año lo es" | "Todos los días de los datos" | Son 282 días de train, no un año entero |
| 4 | "Sabemos cuánto aporta cada pieza… dos piezas no aportan nada" | Añadir la gráfica `resultados_estrategias.png` en la slide | Es justo la slide de barras que pide el bloque |
| 5 | "Esas tres centésimas que faltan tienen nombre: una avería" | Correcto. Se puede reforzar: "en los otros 10 meses, agente y óptimo coinciden" | Ver 2.2 |
| 6 | "2 megavatios hora son el 7 % del consumo diario" | "casi el 8 %" (7,6 % con el consumo del dataset; 8,1 % con el real) | `techo.md` dice 7,6 % |
| Tabla final | "99,6 % … `results/p1_ablaciones.md`" | Sin cambios | Coincide con mis cifras |

Además, en `presentation/resumen-agente.md`, sección "Por qué la damos por cerrada": cambiar el reparto "0,01 +
0,02" por "0,025, todo en la avería de junio" (ver 2.2).

---

## 4. Qué tiene que hacer Aitor ahora, por orden

1. **Arreglar `adapter.py`** con el parche de 2.1 y añadir el test con `np.array` y `pd.Series`.
2. **`python scripts/build_submission.py`** → **dry-run en la web** (gratis, 48 pasos). Comprobar que el ahorro del
   dry-run es positivo y que no hay infracciones.
3. **Primer envío oficial** y fijar el PIN del equipo. Apuntarlo en `docs/envios.md` con el commit, el score local
   (6,09) y el del leaderboard. Si sale una de las señales de alarma de 2.5, parar y revisar antes de gastar otro envío.
4. **Fusionar la próxima PR de `p2-datos`** (resumen de gráficas, este informe y las dos gráficas nuevas). No toca
   código empaquetado.
5. **Añadir a `docs/decisiones.md` las decisiones de P2** (filas listas abajo). La PR #2 las pedía y la tabla aún no
   las tiene.
6. **Corregir el guion** con la tabla de la sección 3 y poner la puntuación del leaderboard en el bloque 4.
7. **Decidir en la sincronización de las 17:00 quién monta las slides.** P3 sigue pendiente. El material está: guion
   en borrador y 11 gráficas con su frase. Si queréis, el Claude de Ivan puede montar el esqueleto de las slides.
8. **No tocar más la estrategia.** Los envíos que queden sirven para confirmar el resultado, no para ajustar al
   leaderboard público (cuenta el 50 %).

### Filas para `docs/decisiones.md`

```text
| Sáb 14/11 | Mantener la validación con los datos oficiales (como el tutorial), aunque tengan errores de medida | validar con datos limpios o con el consumo nocturno real | el test se construye igual que el tutorial. Con datos limpios: mpc 6,04 / oracle 6,04; con consumo nocturno real: 6,46 / 6,46 | P2 |
| Sáb 14/11 | El consumo nocturno del dataset no es una medida: de 22:10 a 06:00 el contador no se lee y repite el último valor. Lo contamos al jurado y a UPC Sostenible | ignorarlo | consumo real de noche 785 kW frente a 971 kW (−19 %), reconstruido con la energía que el contador entrega a las 06:05. No cambia las decisiones del agente | P2 |
| Sáb 14/11 | Si el contador marcó 0 la hora anterior (avería), la previsión no espera consumo esa hora | prever con el perfil | validación 6,078 → 6,090. Toda la distancia al oracle está en junio (0,0245 de 0,0247) | P2 |
| Sáb 14/11 | No reentrenar los modelos con datos limpios | reentrenar | mismo score: 6,08 → 6,08 | P2 |
| Sáb 14/11 | El 70/30 del reto resuelve bien el conflicto entre CO₂ y precio (madrugada barata pero sucia) | optimizar solo CO₂ o solo coste | oracle: solo CO₂ 6,13 % / 4,56 %; 70/30 5,78 % / 6,90 %; solo coste 3,06 % / 8,35 % | P2 |
| Sáb 14/11 | Recomendación a UPC Sostenible: 4 MWh con 1.000 kW, ampliando la potencia a la vez que la capacidad | más capacidad con la misma potencia | por MWh añadido: 21,7 t CO₂/año hasta 4 MWh; 17,9 de 4 a 8; 11,4 de 8 a 16. Con 500 kW fijos, de 2 a 4 MWh solo 30 t más | P2 |
```

---

## 5. Preguntas del jurado sobre método que se responden con datos de P2

| Pregunta | Respuesta corta | Fuente |
|---|---|---|
| ¿Por qué no un modelo de previsión del consumo? | Porque no cambia nada: previsión plana, 0,00 de diferencia. El campus siempre consume más de lo que la batería puede dar | `p1_ablaciones.md`, `calidad_datos.md` |
| ¿Por qué no llegáis al 100 % del óptimo? | Por una avería del contador de 14 horas. En los otros 10 meses coincidimos con el óptimo | sección 2.2 |
| ¿Por qué solo un 6 %? | La batería es el 7,6 % del consumo diario y pierde un 10 %. Con el doble de batería, el doble de ahorro | `techo.md` |
| ¿Habéis sobreajustado a la validación? | El agente no tiene parámetros entrenados. En el train saca 5,54 de 5,54 | `p1_ablaciones.md` |
| ¿Qué pasa si los datos están mal? | Los hemos auditado: sabemos qué registros son averías y cuáles son valores repetidos, y hemos medido que corregirlos no cambia las decisiones | `calidad_datos.md` |
| ¿Por qué vaciáis la batería al final? | Porque la carga final no puntúa (+0,11). En el campus real no lo haríamos, y lo decimos | `p1_ablaciones.md` |
