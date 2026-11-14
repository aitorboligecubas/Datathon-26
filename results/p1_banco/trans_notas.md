# Encargo "transiciones": qué cree el agente sobre cuánto dura un contador a 0

Candidato: `scripts/p1_lab/cand_trans.py`. Resultado en dev: `results/p1_banco/trans_dev.csv` y `trans_dev.txt`.
Todas las cifras son puntos de score de un episodio de 2.016 h. "v2" es el agente actual de `src/`; "v1", el del
primer envío (`scripts/p1_lab/antes.py`). No he mirado la suite test.

## 1. Resultado

El candidato es v2 con cinco piezas cambiadas (A, B, C, E, G; sección 4). En dev, frente a v2 y a v1:

| Familia | n | Candidato | v2 | v1 | Frente a v2 (mín) | Frente a v1 (mín) | Hasta el óptimo: candidato / v2 / v1 |
|---|---|---|---|---|---|---|---|
| nov0 | 12 | 6,2076 | 6,2029 | 6,1995 | +0,0047 (−0,0019) | +0,0081 (+0,0002) | 0,0270 / 0,0317 / 0,0351 |
| normal | 6 | 6,1527 | 6,1527 | 6,1527 | 0,0000 | 0,0000 | 0,0052 / 0,0052 / 0,0052 |
| averia | 9 | 6,1044 | 6,1041 | 6,1043 | +0,0003 (0,0000) | +0,0001 (0,0000) | 0,0213 / 0,0216 / 0,0214 |
| parcial | 3 | 6,1826 | 6,1604 | 6,1781 | +0,0222 (0,0000) | +0,0045 (0,0000) | 0,0310 / 0,0531 / 0,0355 |
| dos_ceros | 3 | 6,3172 | 6,2989 | 6,3148 | +0,0182 (+0,0130) | +0,0024 (0,0000) | 0,0435 / 0,0617 / 0,0459 |
| cero_otra | 3 | 6,0382 | 6,0376 | 6,0307 | +0,0006 (0,0000) | +0,0075 (+0,0018) | 0,0048 / 0,0054 / 0,0123 |
| TODOS | 36 | 6,1656 | 6,1605 | 6,1616 | +0,0050 | +0,0039 | 0,0218 / 0,0268 / 0,0257 |

- En la primera mitad (la que sería el ranking público): +0,0109 frente a v2 de media (nov0 +0,0105).
- Ningún episodio de dev queda por debajo de v1. Dos quedan por debajo de v2, los dos de nov0: dev-09 (−0,0019:
  la mitad por la pieza A y la mitad por la C) y dev-25 (−0,0013, por la C). La pieza A sola deja 5 de los 12 nov0
  por debajo de v2 (hasta −0,0038); en el candidato lo compensa la C. Sección 4.
- Datos estándar (`scripts/p1_lab/regresion.py`): validación 6,09046, train 5,54349 y todo 5,66689, idénticos a v2
  con 5 decimales; determinista; solo importa numpy, math, collections, pathlib y sys (este, para localizar `src/`
  desde el laboratorio); 2,0–2,3 ms por paso; 0 infracciones
  en todas las simulaciones (36 de dev y 88 propias).
- Observaciones hostiles (las 12.000 de `p1_auditoria.py`: NaN, infinitos, campos que faltan, lecturas en texto):
  0 excepciones, 0 respuestas no numéricas, 0 infracciones.
- Objetivos del encargo: no ser peor que v1 en parcial (+0,0045) ni en dos_ceros (+0,0024): cumplido. Conservar
  nov0: mejora (+0,0047). Mejorar averia: **no hay casi nada que mejorar** (+0,0003), y la sección 2 explica por qué.

Con otras semillas (suite privada, sección 3) el signo se mantiene: nov0 +0,0034 (15 episodios), parcial +0,0023 (12).
Juntando los 27 episodios de nov0 de las dos suites: +0,0039 frente a v2 (error típico 0,0012; 19 mejoran y 8
empeoran) y +0,0108 frente a v1 (26 mejoran, ninguno empeora).

Aviso sobre la lectura de partida: "v2 es peor que v1 en dos_ceros y en parcial" sale de 3 episodios por familia.
Con otras 3 + 12 semillas, v2 **gana** a v1 en las dos (+0,0067 y +0,0017). Lo que sí es sólido es el mecanismo
de cada pérdida, que es lo que arreglan las piezas A y C.

## 2. Qué pasaba exactamente (mirado hora a hora)

Herramienta: `python scripts/p1_lab/trans_diag.py <semilla> <familia> --win <t0> <t1>` (pérdida frente al óptimo
por semana y detalle horario de v2, v1 y el óptimo).

**dos_ceros (dev-11, dev-23, dev-35).** Toda la diferencia con v1 es una hora: la primera de la segunda semana a 0.
v2 llega a ella con la batería llena (la compró durante la primera semana a 0 "para la semana siguiente"), ignora la
lectura anterior porque es de otro mes, prevé consumo normal y descarga 500 kW contra un consumo nulo: 500 kWh
tirados (vertido 535 / 613 / 535 kWh frente a 35 / 113 / 35 de v1). v1 usaba esa lectura (0) como tope y no descargaba.
Cuesta 0,017 / 0,022 / 0,009.

**parcial (dev-08).** La semana de enero empieza a 0 y el consumo vuelve a las 21:00 del quinto día, en pleno pico.
v2 no compra **nada** en 117 horas: su precio de reserva sale de los valles de los 35 días anteriores (septiembre a
diciembre) y queda por debajo de todos los valles de enero (0,28 / 0,28 / 0,36 / 0,36 / 0,54 en las unidades de la
herramienta). Cuando vuelve el consumo tiene la batería vacía y pierde 0,084 esa semana. v1 pierde 0,031: 0,015 por
comprar de madrugada a 0,37 para un pico de la mañana que no llega (el óptimo compra a 0,28 a mediodía) y 0,016
por la hora en que vuelve el consumo, que nadie puede aprovechar. dev-20 y dev-32 dan lo mismo en v1 y v2.

**averia (9 episodios, hasta 0,058 del óptimo).** Todo lo que queda es información que el agente no tiene:
- la primera hora de la avería, si le pilla descargando (dev-18 y dev-22: 450 y 500 kWh tirados, 0,037 y 0,039);
- lo que compró antes de la avería para un pico que ya no podrá cubrir (dev-06: 1.054 kWh a 0,47 pocas horas antes
  de una avería de 60 h; el óptimo compra a 0,23; 0,026);
- la hora en que vuelve el consumo: la lectura que tiene sigue siendo 0 (dev-10: 0,012);
- y la semana de Navidad, que no es de este encargo (dev-17, 29, 30, 34).
Apostar a descargar a ciegas durante una avería no sale: con los pesos de dev-10 haría falta más de un 60 % de
probabilidad de que el contador haya vuelto justo esa hora.

**nov0.** Dos cosas distintas. (a) En 3 de 12 episodios (dev-09, 25, 26, la misma ventana de precios de noviembre)
se tiran 500 kWh en la primera hora de noviembre: el 31/10 a las 22–23 h el agente compra a 0,62 para vender a
las 00:00 del 24/11 a 0,74. Lo hacen igual v1 y v2 y lo dejo como está (sección 5, "primera hora de cada semana").
(b) El precio al que compra durante la semana: la reserva de v2 acierta a veces (dev-12 y dev-21, a 0,000–0,003 del
óptimo) y otras no se alcanza nunca y acaba comprando el último día (dev-02, 13, 14, 01: peor que v1).

**Llegar con la batería llena a una semana a 0** es la mayor parte de lo que separa a cualquier agente del óptimo
(0,09–0,16 en la semana anterior, de los que se recuperan 0,02–0,07 en la semana a 0). Es inevitable: el óptimo
sabe de antemano que la semana viene sin datos y llega vacío.

## 3. Cuánto se puede ganar como mucho con mejores creencias

`scripts/p1_lab/trans_informado.py` es un agente que hace trampa a propósito: en cuanto ve el primer 0 **sabe
cuántas horas va a durar** el tramo. No sabe cuándo empezará la avería ni los precios más allá de 24 h. Con él se
mide el techo de este encargo. Suite privada (`scripts/p1_lab/trans_suite.py`, semillas 3000–3035 del banco y tres
familias densas propias con las semillas 4000–4011: `averia_x`, 6 averías de 1 a 60 h por episodio; `cae_x`, 4
semanas en las que el contador cae a media semana y no vuelve; `parcial_x`, 4 semanas que empiezan a 0 y recuperan
el consumo entre la hora 24 y la 120). Diferencia media con v2:

| Familia | n | v1 | Candidato | Sabe la duración | Además sabe la hora de vuelta | Óptimo |
|---|---|---|---|---|---|---|
| nov0 | 15 | −0,0095 | +0,0034 | +0,0031 | +0,0027 | +0,0233 |
| parcial | 12 | −0,0017 | +0,0023 | +0,0080 | +0,0104 | +0,0272 |
| dos_ceros | 3 | −0,0067 | +0,0001 | +0,0030 | +0,0013 | +0,0661 |
| cero_otra | 3 | −0,0057 | −0,0007 | −0,0007 | +0,0008 | +0,0349 |
| averia | 3 | 0,0000 | 0,0000 | +0,0025 | +0,0123 | +0,0567 |
| averia_x | 12 | 0,0000 | +0,0026 | +0,0134 | +0,0267 | +0,1329 |
| cae_x | 12 | −0,0011 | +0,0080 | +0,0333 | +0,0344 | +0,1784 |
| parcial_x | 12 | −0,0014 | +0,0048 | +0,0263 | +0,0375 | +0,1747 |
| normal (16 semillas) | 16 | 0,0000 | 0,0000 | | | |

Lectura:
- En **nov0 ya no queda nada** por el lado de la duración: el candidato iguala al que la conoce (+0,0034 frente a
  +0,0031). Lo que falta hasta el óptimo (0,02) es llegar vacío a la semana a 0 y el precio de compra.
- En las averías, saber la duración vale +0,013 por episodio con 6 averías (0,002 por avería) y saber además la
  hora exacta de vuelta, otro tanto. El resto, hasta +0,13, es saber que la avería va a empezar.
- El candidato se queda con una parte: +0,0026 de +0,0134 en averia_x y +0,0080 de +0,0333 en cae_x (pieza E).
  Lo demás exigiría creer, desde la primera hora de una caída, que va a durar días; y si esa creencia falla en una
  avería corta, el consumo vuelve con la batería vacía, que cuesta más (hasta 0,05) que comprar un poco caro (0,015).
- Peores casos del candidato: frente a v1, 5 episodios de 88 (4 de parcial_x, hasta −0,047, y 1 de averia_x,
  −0,003); frente a v2, 16 de 88 (6 de nov0, hasta −0,011). La compra en una semana a 0 es una lotería episodio a
  episodio (±0,01–0,02) que solo sale a favor de media.

## 4. Las cinco piezas

Cada una tiene un interruptor en `TransPolicy`. "Sola" = v2 con esa única pieza; para E y G en la suite privada,
y para G en dev, la cifra es la diferencia entre el candidato con la pieza y sin ella. Dev sin la familia normal
(30 episodios); suite privada de 36 más las familias densas.

| Pieza | Qué cambia | En dev | En la suite privada |
|---|---|---|---|
| A. `CARRY_ZERO` | La racha a 0 no se corta al cambiar de semana | dos_ceros +0,0170; nov0 −0,0007 [−0,0038, +0,0021]; resto 0 | dos_ceros +0,0017; nov0 +0,0003; cero_otra −0,0015; parcial −0,0003 |
| B. `FIRST_READING` | En t = 0 la lectura es de la propia hora | cero_otra 0,0000 | (sin medir sola) |
| C. `POOL_DAYS = 7` | La reserva se calcula con los 7 últimos días | nov0 +0,0053 [−0,0013, +0,0123]; parcial +0,0222; dos_ceros +0,0016; cero_otra +0,0007 | nov0 +0,0027 [−0,0102, +0,0203]; parcial +0,0012; cero_otra +0,0008; dos_ceros −0,0016 |
| E. `LINDY` | En una avería corta, el consumo vuelve "probablemente" | averia +0,0000 (un episodio +0,0004) | averia_x +0,0025 (de 0,0000 a +0,0025); cae_x +0,0090 (de −0,0011 a +0,0079); parcial +0,0013 |
| G. `RESET_ERR` | El previsor olvida el error de la semana anterior | averia +0,0003; cero_otra +0,0003; nov0 +0,0001; normal 0,0000 | nov0 +0,0003; normal +0,0000 (3 de 16 mejoran hasta +0,0003, ninguno empeora); parcial_x −0,0009 |

**A. La racha a 0 sigue al cambiar de semana.** v2 ignora siempre la lectura anterior en la primera hora de una
semana. Ahora, si esa lectura era 0, el agente sigue creyendo que el contador está caído hasta que vea consumo:
esa hora no descarga y actúa como en una semana sin datos; a la hora siguiente ya tiene una lectura de la semana
nueva. Es un seguro, y tiene prima: si la semana nueva es normal, se pierde la descarga de esa primera hora.
- Si la semana nueva también viene a 0: ahorra el vertido, +0,012 a +0,022 en los tres dos_ceros de dev (en la
  suite privada solo uno de tres llegaba a tirar energía: +0,008).
- Si la semana nueva es normal: de media cuesta ~0,0005 (nov0: −0,0007 en dev y +0,0003 en la privada; cae_x:
  −0,0003 por suceso); el peor caso visto es −0,0044. En nov0 la prima se compensa en parte porque la semana
  siguiente es Navidad y descargar 500 kW a ciegas contra un consumo de 440 también tira energía.
- Compensa si después de una semana que acaba a 0 la siguiente también viene a 0 más de 1 vez de cada 20. En el
  train, octubre tiene contador hasta el día 24 y noviembre no tiene ninguno: no se puede descartar que la semana
  de octubre del test acabe ya a 0.

**B. La primera lectura del episodio es de la propia hora.** `environment.py` da `row["load_kw"]` en t = 0, no la
hora anterior. Si es 0, la semana empieza sin datos desde la hora 0 en vez de enterarse una hora tarde. Sin efecto
medible (0,0000 en el único episodio de dev en el que aplica); es una corrección, no una mejora.

**C. La reserva se calcula con los 7 últimos días, no con 35.** El nivel de los valles cambia de un mes a otro casi
tanto como de un día a otro: desviación del logaritmo de 0,21 entre meses y 0,20 entre días del mismo mes (valle
medio mensual de 4,0 a 8,0). Con 35 días de cinco meses, la reserva puede quedar por debajo de todos los valles de
la semana y el agente no compra nunca. Estudio sin simulador, con precio y CO₂ del train y 2.508 casos
(`scripts/p1_lab/trans_exp_compra.py`, salida en `trans_exp_compra.txt`):

| Regla | Ahorro frente a comprar el día 1 | Peor caso | Días con la batería vacía | No llega a comprar en la semana |
|---|---|---|---|---|
| v2: 35 días | 0,0079 | 0,062 | 2,76 | 17 % |
| 14 días | 0,0088 | 0,055 | 2,75 | 11 % |
| **7 días (candidato)** | **0,0091** | **0,049** | **2,42** | **7 %** |
| Óptimo (el mínimo de la semana) | 0,0134 | 0 | 3,24 | 0 % |

El 7 no sale de dev: sale de esta tabla (la mejora es monótona al acortar) y es el mínimo que admite el propio
código, que exige 7 valles para calcular la reserva. En el simulador arregla dev-08 (de 0,086 a 0,020 del óptimo:
compra los dos primeros días a 0,28–0,31) y sube nov0 en las dos suites.

**E. En una avería corta, el consumo vuelve "probablemente", no "seguro".** v2 planifica como si el consumo
volviese seguro en la hora siguiente, y por eso compra de madrugada, con poco margen, para un pico de la mañana que
no podrá cubrir si la avería sigue. Ahora, tras z horas a 0, la probabilidad de poder descargar dentro de k horas
es k / (z + k): una avería tiene las mismas opciones de durar otro tanto que de acabar antes, y la hora en que
vuelve el consumo se pierde siempre. El LP recibe la descarga esperada (como mucho 500 kW × esa probabilidad), sin
tocar el optimizador y sin parámetros. Solo cambia decisiones de carga.
- La asimetría es el mecanismo: lo que deja de ganar si la avería era corta es un margen estrecho (peor caso
  −0,0033: avería de 6 h que acaba a las 05:00 y deja el pico de la mañana a medio cubrir); lo que evita si la
  avería sigue es comprar al doble de precio (mejor caso +0,057: caída de 71 h que empieza a la 01:00; sin E compra
  1.897 kWh a 0,67–0,69 esa madrugada; con E, 1.063, y el resto a 0,49 y a 0,26).
- En el banco apenas se nota (averia +0,0000) porque hay pocas averías y casi ninguna pilla al agente comprando.
  En las familias densas, +0,0004 por avería y +0,002 por caída a media semana.

**G. El previsor olvida el error de la semana anterior.** v2 dejó de usar la lectura anterior en la primera hora
de una semana, pero el previsor seguía sumando su corrección por persistencia, que es el error de esa misma
lectura. Tras la semana de Navidad (consumo al 45–80 %) la previsión de la primera hora de enero queda en ~220 kW
cuando el consumo real es 1.104, y el agente descarga 220 kW en vez de 471 (dev-34, 25/01 a las 00:00). Es lo
único en lo que v1 ganaba a v2 en la familia averia (dev-29 y dev-34, +0,0008 cada uno). En los datos estándar no
cambia nada. Contrapartida: después de Navidad ese error hacía de freno; si la semana de enero empezase a 0, sin
freno se tiran 500 kWh en vez de 220 (de ahí el −0,0009 de parcial_x, que pone enero a 0 en todos los episodios).

## 5. Lo que he probado y no funciona

| Idea | Resultado | Por qué se descarta |
|---|---|---|
| D. Media paciencia: contar con la mitad de los días que quedan para comprar (`PATIENCE = "half"`) | nov0 −0,0007 en dev y −0,0006 en la privada; cero_otra −0,0022 y dos_ceros −0,0011 en dev; parcial +0,0015 y parcial_x +0,0079 por episodio (+0,002 por suceso) | Es un seguro contra que el consumo vuelva a media semana. Solo compensa si eso pasa más de 1 vez de cada 3, y la prima la paga nov0. Queda el interruptor |
| Un solo día de paciencia (`PATIENCE = "one"`) | nov0 +0,0008 frente a +0,0031 con paciencia total; parcial igual que con media | Pierde casi toda la ganancia de nov0 sin proteger más |
| F. Reescalar la reserva al nivel de la semana en curso (la historia cuenta como un día más) | Sin simulador: casi el mismo ahorro (0,0087 frente a 0,0091) y menos días vacía (2,42 → 2,20). En el simulador: parcial −0,0008, parcial_x −0,0012, dos_ceros −0,0018 | Con el nivel bien estimado, la regla sigue esperando un día por debajo de la media; en una semana plana no llega. Código retirado |
| Descontar el fin de semana en la reserva (los valles de sábado y domingo son un 18 % más bajos) | Sin simulador: 0,0089 frente a 0,0091 | El muestreo de 7 días ya incluye un fin de semana, y el cociente cambia mucho de un mes a otro (0,56 a 1,04) |
| No descargar nunca en la primera hora de cada semana | Cuesta 0,0047 por episodio normal (30 episodios, 360 inicios de semana: el plan quiere descargar en el 22 %) | Lo que se ahorraría con una semana a 0 no lo paga (`trans_exp_inicio.txt`) |
| Descargar en la primera hora solo si compensa en valor esperado, con probabilidad de semana a 0 de 1/12 (1 mes de 12 sin contador en el train) | Se abstiene en 33 de 81 casos; cuesta 0,0006 por episodio normal y ahorra ~0,001 si hay una semana a 0 | Neutra: con un riesgo de 1/12, descargar a ciegas es casi siempre lo correcto. Tampoco evita los tres vertidos de nov0 (ahí descargar a las 00:00 vale unos 0,0024 y el riesgo, unos 0,0020) |
| Pasar a "semana sin datos" antes de las 24 h de avería, o no pasar nunca | No probado en el simulador | A las 24 h la batería ya suele estar llena (compra en el primer valle), así que el cambio casi no decide nada |
| Tratar un consumo muy bajo pero no nulo como contador caído | No adoptado | En el train solo hay tres lecturas por debajo de 585 kW que no sean 0 exacto (466 y 516 kW junto a la avería de agosto y 582 kW antes de un hueco), y el tope de descarga ya las cubre. En Navidad un consumo de 240–500 kW es real: un umbral lo confundiría. El banco pone ceros exactos y no puede medirlo |
| Usar las filas que faltan como aviso (el 17/06 faltan dos horas justo antes de 14 h a 0) | No adoptado | Dos casos en el train (en el otro, el 04/08, después no hay ceros) y el banco no tiene semanas con huecos |

## 6. Riesgos y parámetros

- **A es una apuesta con prima.** Si el test trae noviembre a 0 y diciembre normal, cuesta ~0,0005 de media
  (de −0,004 a +0,002) y el doble en la mitad en la que caiga. Quien no la quiera pone `CARRY_ZERO = False` y
  pierde solo la protección de dos_ceros.
- **C cambia a qué precio se compra, no cuánto dura el cero.** Se solapa con el trabajo de compra en nov0
  (`cand_compra.py`): si se integra otra reserva, C sobra, y hay que volver a mirar dev-08, que es donde falla la
  de 35 días.
- **El candidato sigue esperando con la batería vacía** en una semana que empieza a 0 (2,4 días de media). Si el
  consumo vuelve a media semana en pleno pico, pierde hasta 0,05–0,07 frente a v1 en ese suceso (4 de 12 episodios
  de parcial_x), aunque de media gana (+0,0062). La pieza D lo reduce a la mitad y cuesta 0,0007 en nov0.
- **E supone que las averías no tienen escala** (lo que llevan durando es la mejor guía de lo que les queda). Con
  averías siempre de 1–3 horas perdería márgenes pequeños; en el train hay dos averías: 1 h y 14 h.
- **G toca dos atributos del previsor de P2** (`err_load`, `err_pv`) desde la política. Para integrarlo bien haría
  falta un método en `Forecaster`.
- Parámetros nuevos: ninguno con valor ajustado. `POOL_DAYS = 7` sustituye a `VALLEY_DAYS = 35`. La regla
  k / (z + k) no tiene constantes.
- Las familias parcial, dos_ceros y cero_otra tienen 3 episodios en dev: sus medias se mueven ±0,02 con un solo
  episodio.

## 7. Para integrar en `src/battery/policy.py`

1. `VALLEY_DAYS = 35` → `7` (C).
2. `track_block`: sustituir por el de `TransPolicy` (A y B) y añadir el atributo `keep_reading`.
3. `act_obs`: borrar la lectura solo `if new_block and not self.keep_reading`; en esa misma rama, poner a cero el
   error del previsor (G).
4. `plan_action`: rama `elif obs.load_prev_kw == 0.0: load, pv = self.outage_view(H, load, pv)` y el método
   `outage_view` (E).
5. Dos tests de `tests/test_agent.py` dejan de pasar y hay que reescribirlos, porque fijan el comportamiento que
   cambia la pieza A:
   - `test_stale_reading_at_week_start_is_ignored`: su primer caso exige descargar en la primera hora de una semana
     cuando la anterior acabó a 0.
   - `test_no_data_week_buys_late_and_never_dumps`: su última comprobación (no ser peor que la lógica antigua con
     tolerancia de 0,001) falla en su episodio de 3 semanas, 4,2720 frente a 4,2768. Sin A da 4,2862: la diferencia
     es la descarga de las 00:00 del 25/12, que A deja pasar.
   Los otros 7 tests de ese fichero pasan con el candidato tal cual.

## 8. Cómo reproducir

```bash
python scripts/p1_banco.py --suite dev --agent scripts/p1_lab/cand_trans.py --ref results/p1_banco/dev_actual.csv --out results/p1_banco/trans_dev.csv --jobs 2
python scripts/p1_lab/regresion.py scripts/p1_lab/cand_trans.py
python scripts/p1_banco.py --suite dev --agent scripts/p1_lab/cand_trans.py:solo_A --ref results/p1_banco/dev_actual.csv   # solo_B, solo_C, solo_E, solo_G, con_D
python scripts/p1_lab/trans_suite.py scripts/p1_lab/cand_trans.py --tag cand                                              # suite privada (36)
python scripts/p1_lab/trans_suite.py scripts/p1_lab/cand_trans.py --tag cand --fam averia_x,cae_x,parcial_x --n 12 --base 4000
python scripts/p1_lab/trans_suite.py informado --tag informado                                                            # cota superior
python scripts/p1_lab/trans_diag.py 1008 parcial --agents v2,v1,scripts/p1_lab/cand_trans.py --win 672 800
python scripts/p1_lab/trans_exp_inicio.py 3000 30      # primera hora de cada semana
python scripts/p1_lab/trans_exp_compra.py              # cuándo comprar en una semana a 0
```

Ficheros: `trans_dev.csv` y `trans_dev.txt` (candidato en dev), `trans_dev_solo_{A,B,C,E}.csv` (cada pieza sola),
`trans_dev_conD*.{csv,txt}` (la variante con media paciencia y sus ablaciones), `trans_suite_privada.csv` (todos
los agentes en la suite privada y en las familias densas), `trans_regresion.txt`, `trans_exp_inicio.{csv,txt}` y
`trans_exp_compra.txt`.

Pasadas de dev gastadas: 3 completas (una de una versión intermedia, la del candidato sin G y la final), 7 parciales
de 30 episodios y una de 3, para las ablaciones. En total, el equivalente a 8,9 pasadas: algo por encima del tope
orientativo de 8. De dónde sale cada decisión: los 7 días (C), del estudio sin simulador; la regla k / (z + k) (E),
del razonamiento y de las familias densas; quitar F, de la suite privada; paciencia total en vez de media (D), de
dev y de la suite privada, que dan el mismo coste en nov0; G la encontré mirando dev-34 hora a hora y la comprobé
en la suite privada y en 16 episodios normales antes de la pasada final.
