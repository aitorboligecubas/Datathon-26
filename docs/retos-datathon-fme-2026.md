# Datathon FME 2026 — Los tres retos

*14–15 de noviembre de 2026 · FME-UPC, Barcelona · Entrega: domingo 12:00*

---

## Reto 1 — UPC Sostenible: controlar la batería del campus

**Qué hay que hacer:** programar un `BatteryAgent` en Python que, **hora a hora**, decida cuánto carga o descarga la batería del campus (2.000 kWh) durante 12 semanas, es decir, 2.016 horas. El campus tiene placas solares y una batería.

**Cómo funciona la energía:** red = demanda − solar + batería.
- Si el resultado es mayor que 0, el campus compra luz a la red: paga el precio PVPC y emite CO₂ según el mix eléctrico de ese momento.
- Si es menor que 0, sobra sol y se vende a 0,04 €/kWh. Lo inteligente es usar ese excedente para cargar la batería.

**Qué recibe el agente en cada hora:** hora, día de la semana, carga actual, precio y CO₂ de esa hora, **las previsiones de precio y CO₂ de las 24 horas siguientes** y el consumo y la producción solar de la hora anterior.

**Cómo puntúa:**
- `Score = 0,70·ΔCO₂% + 0,30·ΔCoste% − 0,20·infracciones`
- Lo que más pesa es reducir CO₂: hay que evitar comprar luz cuando funcionan las centrales de ciclo combinado.
- Pedir más carga de la que cabe o descargar más de lo que queda cuenta como infracción. Se evita fácilmente limitando el valor antes de devolverlo.
- Hay leaderboard, pero **el jurado decide de forma decisiva** con la presentación, el razonamiento y la justificación de la estrategia.

**Reglas:** 10 envíos al día, 60 s de ejecución en total y un .zip de 25 MB como máximo. Solo se permiten numpy, pandas, scipy, sklearn, xgboost y lightgbm, sin red. Os dan datos de entrenamiento (13 MB) y un notebook tutorial.

**Valoración:** es el más "datathon clásico", y se puede ganar con matemáticas. Como tenéis las previsiones a 24 h, una **optimización con horizonte deslizante** (programación lineal con `scipy.optimize.linprog`) os da casi el óptimo. El problema son los 60 s para 2.016 pasos: hay que medirlo.

---

## Reto 2 — Qualcomm: copiloto de matemáticas en una Arduino UNO Q

**Qué hay que hacer:** un copiloto de matemáticas que funcione **entero dentro de la placa Arduino UNO Q**: sin internet, con 4 GB de RAM y un modelo pequeño (Qwen3.5 0.8B con llama.cpp). Usa el dataset **M3Kang**, con miles de problemas del Cangur de matemáticas en varios idiomas, también en catalán.

**Hay que elegir uno de dos caminos:**
- **Enseñar:** una experiencia que guíe al alumno **sin darle la respuesta**, con pistas, práctica adaptativa, análisis de errores, botones y LEDs físicos o trabajo colaborativo.
- **Razonar:** acertar la letra (A–E) en un test oculto. El `predict.py` se ejecuta igualmente en todos los equipos.

**Lo difícil:** la placa es lentísima. Lee unos 11 tokens/s y escribe unos 5 tokens/s. El baseline acierta un **22,5%**, que es peor que contestar siempre "D" (25%). Con 2 ejemplos de RAG tarda unos 30 s por problema, y el límite es de 60 s.

**Qué hay que entregar:** un repo de GitHub y una entrada en Arduino Project Hub con la arquitectura, cómo replicarlo y **un análisis de errores por tema, idioma y dificultad**. Además, una demo en vivo de 3 minutos con la placa y el Wi-Fi apagado.

**Valoración:** es el más espectacular para un pitch: IA en el dispositivo, privacidad, educación y hardware que se toca. Encaja con los patrones que ganan hoy, como el tutor socrático que no da la respuesta o el hardware físico. Pero **necesitáis la placa** y montar el entorno lleva más o menos 2 horas, por la compilación de llama.cpp y el OCR del dataset. Además, el modelo es casi aleatorio, así que hay poco margen en "Razonar". La parte de "Enseñar" es donde más se puede diferenciar.

---

## Reto 3 — RawTree: recomendador en tiempo real

**Qué hay que hacer:** un **recomendador en vivo** para el carrusel de una tienda. Llegan unos 3 compradores por segundo y a cada uno hay que devolverle **10 productos ordenados en menos de 3 segundos**. Un simulador oculto decide si hacen clic o compran.

**Datos (todo en RawTree, que funciona con SQL):**
- Un catálogo de unos 5.000 productos.
- 60 días de historial: unos 2 millones de impresiones de carrusel y unos 12 millones de eventos.
- En vivo: peticiones, eventos, y cambios de catálogo, de precios y de stock.

**Cómo puntúa:**
- **Stream (70 puntos):**
  - Conversión: 50.
  - Cold start: 10. Cuenta con usuarios nuevos y productos añadidos durante el evento.
  - Fiabilidad: 10. Una respuesta tarde o con un producto agotado se sustituye por el top de ventas.
- **Jurado (30 puntos):** método 10, aprendizaje del stream 10, uso de RawTree 5 y comunicación 5.
- **Calendario:** se puede practicar con leaderboard desde el sábado a las 10:00 hasta el domingo a las 10:00, pero **solo cuenta la ronda final, del domingo de 10:00 a 12:00**, con el leaderboard oculto.

**Valoración:** es el más ingenieril. Lo que más pesa es que **el sistema no se caiga** durante esas dos horas finales. Una base sólida como "populares por categoría + vistos recientemente + filtro de stock" ya supera al baseline. A partir de ahí se mejora con co-visitación y aprendizaje en vivo. Es el que más se parece al caso Pista de ETHGlobal Lisboa: datos en streaming, un agente que actúa y SQL en tiempo real.

---

## Comparación rápida

| | Batería UPC | Qualcomm Arduino | RawTree |
|---|---|---|---|
| Tipo | Optimización y series temporales | IA en el dispositivo y edtech | Recomendador en tiempo real |
| Lo que decide | Leaderboard y **jurado decisivo** | Originalidad, demo y medición | 70% métrica en vivo y 30% jurado |
| Riesgo principal | Límite de 60 s | Hardware lento y montaje | Que el sistema se caiga el domingo |
| Perfil ideal | Matemáticas, optimización | Hardware, producto, pitch | Backend, SQL, ML |
| Wow en la demo | Medio (gráficas de CO₂) | **Alto** (placa sin Wi-Fi) | Medio (contador en vivo) |

**Si sois un equipo de la FME** (matemáticas/estadística), el **reto de la batería** es donde vuestra ventaja pesa más: es optimización pura con previsiones y una métrica clara.

---

## Enlaces

- Reto 1 (UPC Sostenible): https://repteupc.datathon.cat
- Reto 2 (Qualcomm): https://github.com/mpous/datathon-UPC-maths-qualcomm-arduino-unoq
- Reto 3 (RawTree): https://datathon.rawtree.dev
