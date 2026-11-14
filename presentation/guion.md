# Guion del pitch — Reto UPC Sostenible

Borrador de P1 con el material de P1 (`presentation/resumen-agente.md`, `results/p1_ablaciones.md`) y de P2
(`analysis/`). Todas las cifras son de la validación con datos oficiales, salvo donde se indica.

- **Duración:** pensado para **5 minutos** (unas 650 palabras habladas). La organización no ha publicado el tiempo
  de las demos: si son 3 minutos, se quitan los bloques marcados con ✂.
- **Quién habla:** por decidir. Propuesta: Aitor los bloques 1, 3 y 4; Ivan los bloques 2, 5 y 6.
- **Pendiente antes de ensayar:** poner la puntuación del leaderboard en el bloque 4 (todavía no hay envío oficial).
- **Gráficas:** las 11 de P2, ordenadas por bloque y con la cifra que hay que decir, en `analysis/resumen_graficas.md`.

---

## La idea en una frase

> No hemos entrenado un modelo para adivinar: hemos resuelto, hora a hora, el problema exacto que puntúa el reto.
> Y hemos medido cuánto falta para lo imposible: el 0,4 %.

---

## 1. El problema (30 s)

**Slide:** foto del campus + tres cifras: 27 MWh al día · 805 t de CO₂ al año · 1,38 M€ al año.

> El Campus Nord compra a la red casi toda su electricidad: según su contador, 27 megavatios hora cada día,
> 805 toneladas de CO₂ y 1,4 millones de euros al año. Las placas solares cubren apenas un 2 %.
>
> UPC Sostenible quiere instalar una batería de 2 megavatios hora. Nuestra tarea: decidir cada hora si carga,
> descarga o espera, para emitir menos y pagar menos.

## 2. Lo que dicen los datos (50 s)

**Slide:** `analysis/figs/patrones_por_hora.png` (CO₂ y precio por hora del día).

> Antes de programar nada, miramos los datos. La red no es igual a todas horas: a mediodía, con el sol de toda
> España, es limpia y barata. A las nueve de la noche es el doble de sucia y el triple de cara.
>
> Así que la batería no sirve para guardar nuestro sol, que casi no hay. Sirve para **mover energía en el tiempo**:
> comprar de más a mediodía para comprar de menos al anochecer.
>
> Pero la batería pierde un 10 % en cada ida y vuelta. Mover energía solo compensa si la hora mala es al menos
> un 11 % peor que la buena. Lo es todos los días de los datos.

✂ **Si hay tiempo (15 s):** `analysis/figs/patrones_conflicto.png`.

> Hay una trampa: de madrugada la luz es barata pero sucia. Quien solo mire el precio cargaría de noche.
> El 70/30 del reto obliga a cargar a mediodía.

## 3. Nuestro agente (60 s)

**Slide:** esquema del GPS: "planifico 24 h → ejecuto 1 h → vuelvo a planificar" + `analysis/figs/resultados_semana_tipo.png`
(una semana de julio: cuándo carga y cuándo descarga).

> Nuestro agente funciona como un GPS. Cada hora calcula el plan óptimo para las próximas 24 horas, ejecuta solo
> el primer paso y, una hora después, recalcula.
>
> Ese plan no sale de reglas a mano ni de un modelo entrenado. Es un problema de programación lineal que minimiza
> exactamente la fórmula del reto: 70 % CO₂, 30 % coste, con la física real de la batería. **No tiene ningún
> parámetro ajustado.**
>
> Podemos hacerlo porque el precio y el CO₂ de las próximas 24 horas nos los dan. Lo único que no sabemos es el
> consumo, y comprobamos que no importa: con una previsión plana el resultado es idéntico.
>
> Y toda decisión pasa por un control de seguridad: cero infracciones, siempre.

## 4. Resultados (50 s)

**Slide:** `analysis/figs/resultados_estrategias.png` (plantilla oficial 0,03 · reglas simples 0,08 ·
**nuestro agente 6,09** · máximo teórico 6,12).

> Para saber si es bueno, calculamos lo imposible: el plan perfecto de alguien que conociera todo el futuro.
> Ese máximo es 6,12. Nuestro agente saca **6,09: el 99,6 %**. La plantilla oficial, 0,03.
>
> En el leaderboard: **[PENDIENTE: puntuación y posición]**.
>
> Y no es suerte de una semana concreta. En los datos que no usamos para validar, captura el 99,97 %.
> Si las previsiones fallaran un 20 %, sacaría 6,01. Tarda 4 segundos de los 60 permitidos.

✂ **Si hay tiempo (20 s):** tabla de `results/p1_ablaciones.md`, sección 1.

> Sabemos cuánto aporta cada pieza. Planificar: 6 puntos. Vaciar la batería al final: una décima. Y dos piezas
> que probamos no aportan nada, y lo decimos.

## 5. Lo que encontramos por el camino (45 s)

**Slide:** `analysis/figs/calidad_perfil_noche.png` + la avería del 17–18 de junio.

> Esas tres centésimas que faltan tienen nombre: una avería. El 17 de junio el contador perdió la comunicación y
> marcó cero durante 14 horas. El agente descargaba la batería contra un consumo que "no existía". Añadimos una
> protección: nunca descarga más de lo que el campus consumió la hora anterior. En los otros diez meses, nuestro
> agente y el óptimo coinciden.
>
> Y un hallazgo para UPC Sostenible: de diez de la noche a seis de la mañana el contador no se lee, y el dataset
> repite el último valor. El consumo nocturno real es un 19 % menor de lo que dicen los datos: el campus gasta
> en realidad unos 25 megavatios hora al día, no 27.

**Transparencia (decirlo siempre):**

> Una cosa que hacemos por las reglas del reto y no haríamos en el campus: vaciar la batería al final, porque la
> carga que sobra no puntúa.

## 6. Recomendación para UPC Sostenible (45 s)

**Slide:** `analysis/figs/escenarios_ahorro.png` + "4 MWh · 1.000 kW".

> ¿Por qué solo un 6 %? Porque el techo lo pone el tamaño de la batería, no el algoritmo: 2 megavatios hora son
> casi el 8 % del consumo diario.
>
> Esta batería evita **43 toneladas de CO₂ y 92.000 euros al año**. Con el doble, 4 megavatios hora y
> 1.000 kilovatios, el ahorro se duplica. A partir de ahí cada megavatio hora añadido rinde cada vez menos,
> porque ya no queda consumo que cubrir en las horas malas.
>
> Nuestra recomendación: **4 megavatios hora, y ampliar la potencia a la vez que la capacidad.**

## 7. Cierre (20 s)

**Slide:** la frase.

> Un agente sin parámetros, que se puede explicar entero, al 99,6 % del máximo posible. Y un dato para decidir
> la inversión: el tamaño que de verdad compensa. Gracias.

---

## Versión de 3 minutos

Quitar los dos bloques ✂ y, además:
- bloque 2: solo los dos primeros párrafos;
- bloque 4: quitar el párrafo de robustez;
- bloque 5: solo el hallazgo nocturno y la frase de transparencia.

## Reparto de las preguntas del jurado

| Tema | Responde |
|---|---|
| Método, optimización, robustez, por qué no ML o RL | Aitor |
| Datos, calidad, patrones, tamaño de la batería | Ivan |

## Cifras del guion y de dónde salen

| Cifra | Fuente |
|---|---|
| 27 MWh/día, 805 t y 1,38 M€ al año, 43 t y 92.000 € con 2 MWh, recomendación de 4 MWh | `analysis/escenarios.md` (train limpio, anualizado) |
| Doble de sucia y triple de cara a las 21 h; conflicto de madrugada | `analysis/patrones.md` |
| 6,09 / 6,12 / 99,6 %; 99,97 % en el train; 6,01 con ruido del 20 %; 4 s | `results/p1_ablaciones.md` |
| Plantilla oficial 0,03 (con 7 infracciones) | `python scripts/calibrate_sim.py` |
| Avería de 14 h; en los otros 10 meses el agente iguala al óptimo; consumo nocturno un 19 % menor | `analysis/calidad_datos.md` |
| Batería = casi el 8 % del consumo diario (7,6 %); consumo real de 24,7 MWh al día | `analysis/techo.md`, `analysis/informe_p2_para_p1.md` |
| La solar equivale a un 2 % de lo que se compra a la red (2,4 %) | tabla horaria oficial (`battery.data.load`) |
