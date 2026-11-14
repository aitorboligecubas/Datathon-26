# Encargo "compra": cuándo comprar la carga en una semana sin datos

Notas de P1 (agente del encargo "compra"), sábado 14/11. Todo lo que se cita se puede volver a generar
con los comandos del final. Las diferencias se dan en puntos de score de un episodio de 12 semanas;
"mitad 1" es el score de las primeras 1.008 horas.

## En cuatro frases

1. **El banco estándar no conserva el día de la semana de los datos, y para decidir cuándo comprar eso lo
   cambia todo.** Cada semana se toma del train empezando en un día cualquiera y se le ponen las fechas del
   test. En el test real la semana de noviembre va de lunes 24 a domingo 30: el fin de semana, que es un
   18 % más barato, está al final. En el banco está en un sitio al azar.
2. **Con el calendario real, el agente actual (v2) ya compra donde compra el óptimo.** En los 12 episodios
   nov0 del banco alineado, la compra cuesta 0,0002 de los 0,0209 que le separan del óptimo: en 7 compra
   exactamente en las mismas horas y en otros 3 la única diferencia es la carga de la primera hora, antes
   de saber que la semana viene a cero. v2 gana a v1 en los 12: +0,039 de score y +0,086 en la mitad 1
   (el banco estándar decía +0,003 y "peor en 5 de 12").
3. **No hay mejora que ofrecer en nov0.** El candidato que el banco estándar premia (reserva que aprende el
   nivel de la semana, sin día de la semana: +0,0057 en nov0) pierde −0,0043 con el calendario real (son
   tres semanas de noviembre; con las 28 semanas del train que empiezan en lunes, empata con v2). El
   candidato que se entrega (con día de la semana) iguala a v2 en nov0 (−0,0000) y solo gana en las familias
   hipotéticas (parcial +0,0069, cero_otra +0,0029).
4. **Cualquier cambio que toque cuándo se compra hay que juzgarlo con el banco alineado**
   (`scripts/p1_lab/compra_banco_alineado.py`). Ejemplo medido: el candidato "trans" de otro agente gana
   +0,0046 en nov0 en el banco estándar y pierde −0,0092 en el alineado, peor que v2 en los 12 episodios.

Recomendación: **adoptar una parte**.
- Para noviembre a cero no hay nada que adoptar: v2 ya está en el óptimo de la compra y el candidato lo
  iguala. No se promete ni una milésima en el caso que importa.
- El banco alineado sí: es con lo que hay que juzgar cualquier cambio en la compra (otros agentes ya lo
  están usando).
- La reserva del candidato es opcional. Es la forma segura de tocar la reserva si se quiere dejar de perder
  contra v1 en parcial (alineado: v2 −0,0051 frente a v1; el candidato +0,0017) o cubrir otra semana a cero,
  porque no cuesta nada en nov0. Acortar la historia de valles (pieza C de "trans") arregla menos y cuesta
  −0,0077 en nov0.

## 1. Qué se pierde en una semana sin datos, y dónde

`scripts/p1_lab/compra_descomposicion.py` parte la distancia al óptimo de cada episodio nov0 en cuatro
trozos, comparando al agente con "el óptimo a partir de aquí" (el LP con todo el futuro conocido, desde la
carga que el agente lleva en ese momento). Agente actual (v2), 12 episodios nov0 de dev:

| Banco | Total | Llegada | Hora 1 | Compra | Resto |
|---|---|---|---|---|---|
| Estándar (día de la semana al azar) | 0,0317 | 0,0122 | 0,0055 | **0,0062** | 0,0077 |
| Alineado (calendario real) | 0,0209 | 0,0080 | 0,0055 | **0,0002** | 0,0072 |

- **Llegada**: llegar a la semana sin datos con la batería cargada (se compró la tarde anterior para la
  madrugada siguiente). Solo se evita sabiendo de antemano que la semana viene a cero.
- **Hora 1**: la primera hora de la semana, cuando el agente aún no sabe que viene a cero. En la semana del
  17 de noviembre carga 500 kWh a las 00:00 del lunes a un peso de 1,27 (para el pico de la mañana) y esa
  energía se podría haber comprado el sábado a 0,50: 0,019 puntos en 3 episodios.
- **Compra**: cuándo y cuánto se compra durante la semana. Es lo que pedía el encargo.
- **Resto**: lo que se pierde después. Es la semana de Navidad con poco consumo: con noviembre normal en
  los mismos episodios la pérdida de esa semana es la misma (0,0059 frente a 0,0052). Llegar con la batería
  llena no añade nada.

Con el calendario real, v2 compra el domingo (semana del 10 de noviembre: es el día más barato) o el
sábado (semana del 17: sábado 0,50, domingo 0,53), que es lo que hace el óptimo. Detalle hora a hora en
`compra_descomposicion_alineado_actual.txt`.

## 2. El día de la semana

Medido en el train (`python scripts/p1_lab/compra_estudio.py`, salida en `compra_estudio.txt`): el valle
diario (media de las 4 horas más baratas) de sábados y domingos es un 18 % más bajo que el de los laborables
(−0,203 en logaritmo, con efectos fijos de mes; de −0,57 en julio a +0,04 en abril; noviembre −0,19).

Por qué v2 acierta en noviembre: su reserva sale de los valles de los 35 últimos días vistos, que en el test
son de septiembre y octubre. Septiembre es barato (valle medio 0,56 frente a 0,71 de noviembre), así que la
reserva queda por debajo de casi todos los valles de noviembre, el agente no compra entre semana y llega al
fin de semana. Es paciencia por un motivo que no tiene que ver con el fin de semana: sale bien porque la
semana acaba en domingo.

La misma simulación de la compra (hora a hora, sin LP, obligando a llenar la batería) en las 209 ventanas de
7 días del train, con el día de la semana real. Exceso sobre comprar sabiendo toda la semana, en puntos:

| La semana empieza en | v1 (primer valle) | v2 | Candidato | Candidato sin día de la semana | Ventanas |
|---|---|---|---|---|---|
| lunes | 0,0137 | 0,0034 | 0,0026 | 0,0035 | 31 |
| martes | 0,0111 | 0,0064 | 0,0021 | 0,0025 | 29 |
| miércoles | 0,0111 | 0,0056 | 0,0015 | 0,0014 | 31 |
| jueves | 0,0112 | 0,0078 | 0,0028 | 0,0027 | 29 |
| viernes | 0,0069 | 0,0051 | 0,0036 | 0,0062 | 29 |
| sábado | 0,0040 | 0,0068 | 0,0044 | 0,0072 | 30 |
| domingo | 0,0063 | 0,0040 | 0,0025 | 0,0037 | 30 |

Cada mes con las ventanas del train que empiezan el mismo día que su semana del test (3 por mes):

| Semana del test | Empieza en | v1 | v2 | Candidato | Sin día |
|---|---|---|---|---|---|
| 24/11/2025 | lunes | 0,0123 | **0,0011** | **0,0009** | 0,0021 |
| 25/10/2025 | sábado | 0,0008 | 0,0228 | 0,0040 | 0,0156 |
| 25/12/2025 | jueves | 0,0145 | 0,0332 | 0,0055 | 0,0054 |
| 25/01/2026 | domingo | 0,0193 | 0,0115 | 0,0050 | 0,0107 |
| media de los 12 meses | | 0,0084 | 0,0075 | 0,0027 | 0,0040 |

En noviembre v2 y el candidato empatan. Donde v2 falla es en las semanas que no acaban en fin de semana
(octubre, diciembre, enero), que solo importarían si la semana a cero fuese otra.

¿Y en una semana de lunes a domingo cualquiera, no solo las tres de noviembre? Diferencia con v2, ventana a
ventana (positivo = mejor que v2), con su error típico:

| Ventanas | Candidato | Sin día de la semana |
|---|---|---|
| Empiezan en lunes, de octubre a agosto (28) | +0,0002 ± 0,0005 (mejor en 11, peor en 9) | −0,0006 ± 0,0008 |
| Empiezan en lunes, las tres de noviembre | +0,0002 ± 0,0002 | −0,0010 ± 0,0021 |
| Todas, empiecen el día que empiecen (209, solapadas) | +0,0028 ± 0,0007 | +0,0017 ± 0,0007 |

Con el calendario de noviembre no hay diferencia que se pueda medir. La hay, y a favor del candidato, si la
semana a cero empezara otro día.

Y lo que explica el espejismo: con todas las ventanas de noviembre y el día de la semana puesto al azar,
como en el banco estándar, v2 sale a 0,0082 y el candidato sin día de la semana a 0,0025. La diferencia,
0,0057, es justo lo que el banco estándar da como mejora.

## 3. El candidato (`scripts/p1_lab/cand_compra.py`)

Solo cambia el precio de reserva de la semana sin datos (`no_data_view`). En una semana con consumo el
agente es idéntico a v2 (validación, train e histórico completo: +0,00000).

Modelo de los valles diarios:

    log(valle del día) = nivel de la semana + [−0,20 si es sábado o domingo] + ruido,  ruido ~ N(0, 0,17²)
    nivel de la semana ~ N(nivel de la semana vista antes, 0,20²), y se corrige con cada día que pasa

La reserva es la de la parada óptima con ese nivel incierto (programación dinámica de 6 etapas como mucho,
201 nodos; unos 0,4 ms por hora, solo en la semana sin datos): se compra hoy solo si la hora cuesta menos
que lo que se espera conseguir esperando. Tres detalles: (a) un laborable tiene que ser muy bueno para no esperar al fin de semana; (b) cuando ya se
ve la hora de mañana en la que hoy está el mínimo, el valle de mañana se estima comparando la hora más
barata visible de mañana con la de hoy; (c) antes del último día se descuenta que la carga puede valer poco
en la semana siguiente (eso solo se ve el último día, y ahí decide el LP normal, como en v2).

| Parámetro | Valor | De dónde sale (train, sin mirar el banco) |
|---|---|---|
| `WEEKEND_SHIFT` | −0,20 | log(valle de fin de semana / laborable) con efectos fijos de mes: −0,203 |
| `SIGMA_VALLEY` | 0,17 | desviación de log(valle) dentro de una ventana de 7 días: 0,168 |
| `TAU_LEVEL` | 0,20 | error del nivel de una semana predicho con la anterior: 0,157; con la media de las 5 anteriores: 0,206 |
| `TAU_USE` | 0,34 | desviación de log(valor de uso de un día del mes siguiente / de la semana): 0,336 |

Sensibilidad (simulación del train, cambiando un parámetro cada vez): con σ de 0,12 a 0,25, τ del nivel
de 0,10 a 0,40, el efecto del fin de semana de −0,10 a −0,30 y τ del valor de uso de 0,20 a 0,50, el exceso
en todas las ventanas se queda entre 0,0028 y 0,0030 (v2: 0,0056), el de las semanas con el calendario del
test entre 0,0025 y 0,0035, y el de noviembre en lunes entre 0,0005 y 0,0010. No hay nada que ajustar.

Comprobaciones: `scripts/p1_lab/regresion.py` (idéntico a v2 en los datos estándar, determinista,
2,1 a 2,4 ms por paso, solo `numpy`, `math`, `collections`) y `scripts/p1_lab/compra_pruebas.py` (las cuentas
de la parada óptima, 6.000 observaciones hostiles y una semana sin datos con pesos rotos sin excepciones ni
infracciones, la regla nueva se usa en 143 de las 144 horas en que toca, 0 respaldos).

## 4. Resultados

Diferencia con v2, episodio a episodio (media, y mínimo y máximo entre corchetes). Suite dev, 36 episodios.

| Familia (n) | Banco estándar: score | mitad 1 | Banco alineado: score | mitad 1 |
|---|---|---|---|---|
| nov0 (12) | +0,0012 [−0,0007, +0,0116] | +0,0025 | **−0,0000 [−0,0003, +0,0000]** | −0,0001 |
| normal (6) | 0,0000 | 0,0000 | 0,0000 | 0,0000 |
| averia (9) | 0,0000 | 0,0000 | 0,0000 | 0,0000 |
| parcial (3) | +0,0222 [0,0000, +0,0665] | +0,0494 | +0,0069 [0,0000, +0,0140] | +0,0158 |
| cero_otra (3) | −0,0040 [−0,0202, +0,0057] | −0,0092 | +0,0029 [−0,0047, +0,0120] | +0,0068 |
| dos_ceros (3) | −0,0032 [−0,0068, 0,0000] | −0,0057 | −0,0005 [−0,0012, 0,0000] | −0,0010 |

Frente a v1, en nov0 (lo que pedía el encargo):

| | Banco estándar: media | peor que v1 | Banco alineado: media | peor que v1 |
|---|---|---|---|---|
| v2 | +0,0034 (mitad 1 +0,0073) | 5 de 12 | **+0,0386 (mitad 1 +0,0857)** | **0 de 12** |
| Candidato | +0,0046 (+0,0098) | 4 de 12 | +0,0386 (+0,0856) | 0 de 12 |
| Sin día de la semana | +0,0091 (+0,0201) | 0 de 12 | +0,0343 (+0,0757) | 0 de 12 |

Mini-episodios con el agente real (dos semanas anteriores, la semana a cero y la siguiente; 10 meses por 6
sorteos; pérdida frente al óptimo en puntos de un episodio de 12 semanas):

| | v1 | v2 | Candidato | Sin día de la semana |
|---|---|---|---|---|
| Calendario real, todos los meses | 0,0404 | 0,0274 | 0,0266 | 0,0272 |
| Calendario real, semana a cero en noviembre | 0,0588 | 0,0118 | 0,0115 | 0,0168 |
| Día de la semana al azar, todos los meses | 0,0355 | 0,0275 | 0,0275 | 0,0270 |

Candidato frente a v2 con el calendario real: +0,0007 de media, error típico 0,0008, mejor en 16 y peor en
16 de 60. No es una diferencia.

Cada pieza del candidato, banco alineado, diferencia con v2 en el score:

| Variante | nov0 | cero_otra | parcial | dos_ceros |
|---|---|---|---|---|
| Candidato | −0,0000 | +0,0029 | +0,0069 | −0,0005 |
| sin mirar las horas de mañana (`sin_peek`) | −0,0001 | +0,0023 | +0,0047 | −0,0009 |
| estimando el valle de mañana desde las 06 h (`peek_siempre`) | −0,0016 | +0,0036 | +0,0078 | −0,0002 |
| sin el valor de uso de la semana siguiente (`sin_valor_uso`) | −0,0000 | +0,0024 | +0,0069 | −0,0005 |
| sin día de la semana (`sin_dia_semana`) | **−0,0043** | +0,0037 | +0,0022 | +0,0004 |

## 5. Lo que se probó y no funcionó

| Idea | Resultado | Por qué |
|---|---|---|
| Reserva que aprende el nivel, sin día de la semana | estándar nov0 +0,0057 (mitad 1 +0,0128); **alineado nov0 −0,0043 (mitad 1 −0,0100), peor que v2 en 11 de 12** | compra un laborable "barato para la semana" y se pierde el fin de semana |
| No descargar en la primera hora de cada semana | normal −0,0037; nov0 +0,0009 (mitad 1 +0,0087, mitad 2 −0,0057) | en uno de cada cuatro cambios de semana el plan descarga en la hora 0 (35 de 132), y aplazarlo cuesta en todas las semanas normales |
| No hacer nada en la primera hora de cada semana | normal −0,0068; nov0 −0,0015 | lo mismo, y además pierde las cargas baratas de madrugada |
| Apuesta en la primera hora: actuar solo si la ganancia esperada supera a la pérdida esperada, con 1/12 de probabilidad de que la semana venga sin datos (1 de los 12 meses del train no tiene contador) | normal −0,0017; nov0 +0,0004. Con 1/6: −0,0044 y +0,0022 | con una probabilidad honesta sale lo comido por lo servido; solo ganaría con una regla a medida de noviembre |
| Tras una semana sin datos, no descargar en la primera hora de la siguiente | dos_ceros +0,0170 (alineado +0,0101); nov0 −0,0007 (alineado −0,0017) | arregla dos_ceros, pero en nov0 retrasa la descarga del 25 de diciembre. Con el calendario real compensa solo si dos semanas a cero seguidas son, como poco, 1/6 de probables que noviembre a cero |
| No contar con el consumo de la semana siguiente al acabar cada semana | normal −0,0810; nov0 −0,1208 | llevar energía de una semana a la siguiente vale mucho (0,02 en un solo cambio de semana); por eso la pérdida de "llegada" no se puede evitar sin saber qué semana viene a cero |
| Ruido empírico en vez de normal, y σ estimada con las semanas vistas | simulación del train: 0,0036 frente a 0,0036 | no aporta; se deja la normal con σ fija |
| Quitar el día de más que cuenta v2 en su plazo | simulación del train: lunes 0,0043 frente a 0,0034 de v2 | en noviembre esa paciencia de más es la que lleva al domingo |
| Estimar el valle de mañana desde primera hora (`peek_siempre`) | alineado nov0 −0,0016 | en noviembre el valle es por la mañana y a esa hora aún no se ve el de mañana |

## 6. Avisos para quien integra

- **El banco estándar sirve para todo lo que no dependa del día de la semana.** Para la compra en una
  semana sin datos, no. El banco alineado usa los mismos escenarios, familias y semillas, pero cada semana
  sale solo de ventanas del train que empiezan el mismo día de la semana que su semana del test (3 por mes;
  2 en junio; en agosto no hay ninguna y se usan todas). Son pocas semanas distintas: 3 de noviembre.
- **El candidato "trans"** (`scripts/p1_lab/cand_trans.py`) toca la misma decisión. Su versión de las 15:49
  UTC (md5 `7780c0b6…`), en el banco estándar: nov0 +0,0046. En el alineado: **nov0 −0,0092 [−0,0217,
  −0,0017], mitad 1 −0,0208, peor que v2 en los 12**; dos_ceros +0,0096, parcial +0,0022, cero_otra −0,0005,
  normal 0,0000. Ese agente ya lo ha medido pieza a pieza con este banco (`alineado_dev_trans_solo_*.txt`):
  la C (reserva con 7 días en vez de 35) es la que cuesta, nov0 −0,0077 y parcial +0,0022; la A (no descargar
  tras una semana a cero) da dos_ceros +0,0101 y nov0 −0,0017, lo mismo que mide aquí `tras_cero`. La reserva
  de este candidato y la pieza C son excluyentes: las dos sustituyen la reserva de v2.
- **Predicción comprobable.** Si la hipótesis es cierta (noviembre a cero en la mitad pública), el paso de v1
  a v2 debería verse en el ranking público con un salto del orden de +0,09 (entre +0,01 y +0,13 en el banco
  alineado), no de +0,007 como decía el banco estándar. No se usa para ajustar nada; sirve para saber si la
  hipótesis se cumple.
- **Lo que no se ha podido medir.** La semana real del 24 al 30 de noviembre no está en el train. Las tres
  semanas de noviembre que empiezan en lunes son las del 3, el 10 y el 17. Que v2 acierte depende de que
  noviembre sea más caro que septiembre, que es lo normal (menos sol), pero no es seguro: si las semanas
  vistas antes fuesen más caras que la de noviembre, v2 compraría el lunes y perdería el descuento del fin
  de semana (del orden de 0,01). El candidato no depende de eso.
- **Si alguna vez se adopta el candidato**: va entero en `policy.py` (constantes, 8 funciones y 4 métodos);
  `variant` y `_Agent` son del laboratorio y no se llevan. No coincide con ningún nombre de los otros módulos.

## 7. Cómo reproducir

```bash
python scripts/p1_lab/compra_estudio.py                              # parámetros y día de la semana (10 s)
python scripts/p1_lab/compra_descomposicion.py --banco alineado      # dónde se pierde en nov0 (40 s)
python scripts/p1_lab/compra_descomposicion.py --banco estandar
python scripts/p1_lab/compra_banco_alineado.py --ventanas            # qué ventanas del train usa cada mes
python scripts/p1_lab/compra_banco_alineado.py --suite dev --out results/p1_banco/compra_alineado_dev_actual.csv
python scripts/p1_lab/compra_banco_alineado.py --suite dev --agent scripts/p1_lab/cand_compra.py \
    --ref results/p1_banco/compra_alineado_dev_actual.csv --out results/p1_banco/compra_alineado_dev.csv --no-oracle
python scripts/p1_banco.py --suite dev --agent scripts/p1_lab/cand_compra.py \
    --ref results/p1_banco/dev_actual.csv --out results/p1_banco/compra_dev.csv --jobs 2
python scripts/p1_lab/compra_mini.py --alineado actual scripts/p1_lab/antes.py scripts/p1_lab/cand_compra.py \
    scripts/p1_lab/cand_compra.py:sin_dia_semana                     # mini-episodios, todos los meses (3 min)
python scripts/p1_lab/regresion.py scripts/p1_lab/cand_compra.py
python scripts/p1_lab/compra_pruebas.py
# variantes: scripts/p1_lab/cand_compra.py:sin_dia_semana, :sin_peek, :peek_siempre, :sin_valor_uso
# descartes: scripts/p1_lab/compra_descartes.py:primera_hora_sin_descarga, :primera_hora_quieto,
#            :apuesta_1_12, :apuesta_1_6, :tras_cero, :sin_puente
```

Ficheros de resultados (todos en `results/p1_banco/`): `compra_dev.csv` y `.txt` (banco estándar, candidato),
`compra_dev_sin_dia_semana.csv`, `compra_alineado_dev_actual.csv` y `.txt` (v2), `compra_alineado_dev_antes.csv`
y `.txt` (v1), `compra_alineado_dev.csv` y `.txt` (candidato), `compra_alineado_dev_sin_dia_semana.csv`,
`compra_descomposicion_*.txt`, `compra_estudio.txt`, `compra_mini_alineado.txt` y `compra_regresion.txt`.
