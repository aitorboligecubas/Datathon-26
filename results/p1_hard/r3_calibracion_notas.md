# Ronda 3 · encargo "calibracion": ¿máscara (M) o real (R)?

Domingo 15/11, 07:45-08:00 UTC. Hecho en 15 minutos: lo que no dio tiempo está al final.

**Pregunta.** En el banco (episodio completo) v12 y v14 ganan a la v10. En la web (mitad pública) pierden.
- **M (máscara):** el banco acierta y la web enseña media simulación; en la otra mitad (privado) saldrían mejor.
- **R (real):** en el test las versiones prudentes son de verdad peores y el banco se equivoca.

**Respuesta corta.** Con los datos que hay no se puede descartar ninguna de las dos. Mi estimación: **M 60 %, R 40 %**
(con ±15 puntos de margen, porque depende de cómo sea la máscara y eso no se sabe).
- Si la máscara es por **horas sueltas**, lo de la web es normal en el banco (pasa en 1 de cada 7-9 sorteos) y no dice nada contra v12 ni v14.
- Si la máscara es por **días enteros o medias semanas**, lo de la web casi no pasa en el banco (2-7 %) y entonces lo probable es R.
- Ningún fallo de servidor (tiempo, semilla, solver) explica la diferencia: los tres están medidos y descartados.

**Recomendación: seleccionar v14 y v10** (no v14 y v12). La v14 es la apuesta si M es cierta; la v10 es el seguro si R es cierta.
Vale si el jurado se queda con la mejor de las dos seleccionadas. La selección por defecto (v10 y v12) es la peor de las tres opciones.

---

## 0. Qué se compara

Web, frente a la v10 (mitad pública; CO2 y coste en puntos porcentuales):

| Versión | CO2 | Coste | Score |
|---|---|---|---|
| v8 (margen 1,4, sin semilla) | −0,034 | −0,235 | −0,094 |
| v9 (margen 1,4) | +0,022 | −0,208 | −0,047 |
| v12 (plan con incertidumbre) | +0,010 | −0,163 | −0,042 |
| v14 (v12 + perfiles nuevos) | −0,062 | −0,147 | −0,087 |

Banco, episodio completo, frente a la v10 (CO2 pp / coste pp / score), seis ventanas:

```text
   val    v8 +0.103/-0.087/+0.046  v9 +0.108/-0.087/+0.050  v12 +0.176/+0.026/+0.131  v14 +0.442/-0.070/+0.288
   dev    v8 +0.060/-0.116/+0.007  v9 +0.077/-0.101/+0.024  v12 +0.144/+0.023/+0.108  v14 +0.269/+0.057/+0.206
   1-7    v8 +0.065/-0.144/+0.002  v9 +0.065/-0.144/+0.002  v12 +0.171/-0.017/+0.114  v14 +0.278/+0.307/+0.287
   3-9    v8 +0.049/-0.132/-0.006  v9 +0.060/-0.119/+0.006  v12 +0.152/+0.018/+0.112  v14 +0.194/+0.168/+0.186
   12-18  v8 +0.023/-0.108/-0.016  v9 +0.031/-0.104/-0.010  v12 +0.066/-0.014/+0.042  v14 +0.223/-0.164/+0.107
   15-21  v8 +0.049/-0.092/+0.006  v9 +0.069/-0.079/+0.025  v12 +0.142/-0.012/+0.096  v14 +0.176/-0.080/+0.099
   media  v8 +0.058/-0.113/+0.007  v9 +0.068/-0.106/+0.016  v12 +0.142/+0.004/+0.101  v14 +0.264/+0.036/+0.195
```

Dos cosas que ya se ven aquí:
- **El banco no dice que v8 y v9 sean mejores que la v10**: dice que empatan (+0,01 y +0,02). El margen 1,4 gana CO2 y pierde coste, también en el banco. Que en la web salgan por debajo es media moneda al aire.
- La pregunta de verdad es solo sobre **v12 (+0,10 en el banco, de +0,04 a +0,13)** y **v14 (+0,20, de +0,10 a +0,29)**.

Nuevas ventanas simuladas: 3-9, 12-18 y 15-21 (`results/hourly/calibra_*.pkl`). Las ventanas tienen 11 meses (no hay noviembre) y alguna semana incompleta.

## 1. ¿Con qué frecuencia una máscara reproduce la web?

3.000 máscaras por familia y ventana (18.000 por familia). Cada máscara coge la mitad de las horas de cada semana.
La nota se calcula como en el código oficial (`evaluate_results(mask=...)`).

- **P(4 < v10):** v8, v9, v12 y v14 quedan todas por debajo de la v10.
- **P(magn.):** además, el CO2 de las cuatro a menos de 0,10 pp de la v10 y el coste entre −0,05 y −0,40 pp.
- **sigma:** cuánto baila la diferencia pública frente a la v10, solo por qué horas caen en la máscara.
- **p(D2):** fracción de máscaras del banco tan lejos del centro como la web, mirando los 8 números a la vez (CO2 y coste de las cuatro). Cerca de 1 = la web es un sorteo normal; cerca de 0 = la web no sale de ese tipo de máscara.

```text
                                           familia     n  P(4<v10)  P(magn.)  P(v12 y v14<v10)  P(v14<=web)  sigma v8  sigma v9  sigma v12  sigma v14  D2 web  p(D2)
             horas sueltas (cada semana las suyas) 18000     0.110     0.005             0.149        0.334     0.105     0.093      0.167      0.650   4.479  0.802
              horas sueltas (mismo patrón semanal) 18000     0.137     0.005             0.170        0.332     0.125     0.114      0.192      0.661   4.054  0.839
                            bloques de 6 h al azar 18000     0.095     0.005             0.122        0.318     0.100     0.085      0.144      0.600   4.781  0.764
                           bloques de 12 h al azar 18000     0.068     0.010             0.086        0.284     0.068     0.066      0.113      0.486  16.251  0.046
              días enteros (cada semana los suyos) 18000     0.024     0.004             0.026        0.269     0.043     0.040      0.061      0.439  23.197  0.003
               días enteros (mismo patrón semanal) 18000     0.024     0.000             0.031        0.272     0.047     0.042      0.063      0.472  35.560  0.000
        media semana seguida (cada semana la suya) 18000     0.033     0.007             0.036        0.185     0.052     0.047      0.073      0.322  14.787  0.086
     media semana seguida (mismo corte; 168 casos)  1008     0.071     0.007             0.074        0.178     0.058     0.055      0.092      0.316  18.270  0.042
             bloques alternos de 1-12 h (56 casos)   336     0.244     0.000             0.256        0.366     0.311     0.305      0.413      0.967   2.169  0.949
                   horas pares / impares (2 casos)    12     0.333     0.000             0.333        0.417     0.138     0.130      0.268      0.847  39.873  0.000
12 horas del día fijas (las mismas todos los días) 18000     0.189     0.002             0.215        0.351     0.228     0.217      0.290      0.768   3.010  0.928
```

(En "horas pares / impares" solo hay 12 casos: su D2 no vale; el resto de la fila sí.)

Cuántas desviaciones separan la web de lo que espera el banco, versión a versión:

```text
horas sueltas (cada semana las suyas)      z web: v6-0.9 v7-0.7 v8-1.0 v9-0.7 v12-0.9 v14-0.4     P(las 6 < v10) 0.057
bloques de 12 h al azar                    z web: v6-1.4 v7-1.7 v8-1.5 v9-1.0 v12-1.3 v14-0.6     P(las 6 < v10) 0.049
días enteros (cada semana los suyos)       z web: v6-1.9 v7-2.0 v8-2.4 v9-1.6 v12-2.3 v14-0.6     P(las 6 < v10) 0.018
media semana seguida (cada semana la suya) z web: v6-2.0 v7-1.6 v8-2.0 v9-1.3 v12-1.9 v14-0.9     P(las 6 < v10) 0.025
12 horas del día fijas                     z web: v6-0.5 v7-0.7 v8-0.4 v9-0.3 v12-0.5 v14-0.4     P(las 6 < v10) 0.104
```

Lectura:
- **Máscara por horas (sueltas, bloques de hasta 6 h, horas del día):** las cuatro por debajo de la v10 pasa el 10-24 % de las veces. La web queda a menos de 1 desviación en todo y p(D2) es 0,76-0,95. **Es un sorteo normal: no contradice al banco.**
- **Máscara por días enteros:** pasa el 2,4 % de las veces y p(D2) ≤ 0,003. **Con esa máscara el banco estaría equivocado.**
- **Media semana seguida:** 3-7 %, p(D2) 0,04-0,09. Dudoso, más cerca de R.
- **Las magnitudes exactas** (CO2 igual y coste −0,15 a −0,24 en las cuatro) salen en el 0,5-1 % de las máscaras en cualquier familia. Es una caja muy estrecha de 8 números: sirve p(D2), no esta cifra.
- **El público de la v14 no mide nada:** su diferencia con la v10 baila ±0,65 puntos (por horas) o ±0,32-0,47 (por días o medias semanas), y la ventaja esperada es +0,20. Sacar −0,09 o peor pasa 1 de cada 3 veces aunque la v14 sea mejor.
- **No son cuatro casualidades, es una.** El margen 1,4 y el plan con incertidumbre fallan o aciertan juntos en el público: correlación +0,67 a +0,85 entre v9 y v12, y +0,9 entre v8 y v9.

## 2. ¿Qué tienen en común las máscaras que reproducen la web?

Aportación de cada hora del día a la diferencia del episodio completo (media de las seis ventanas; la suma es la diferencia total). Acción media en kW (+ carga):

```text
   hora | v9-v10: CO2  coste | v12-v10: CO2  coste | v14-v10: CO2  coste  total | acción v10  acción v14  dif
      0 |      +0.020 +0.007 |       +0.014 +0.005 |       +0.057 +0.021 +0.078 |        -9         -16      -6
      1 |      +0.031 +0.011 |       +0.057 +0.019 |       -0.022 -0.006 -0.028 |      +109        +111      +3
      2 |      +0.038 +0.012 |       +0.069 +0.023 |       +0.090 +0.032 +0.121 |      +196        +174     -22
      3 |      +0.024 +0.008 |       +0.046 +0.015 |       +0.101 +0.028 +0.130 |      +222        +206     -16
      4 |      +0.039 +0.012 |       +0.055 +0.016 |       +0.092 +0.027 +0.119 |      +189        +164     -25
      5 |      +0.022 +0.007 |       +0.040 +0.012 |       +0.067 +0.020 +0.086 |       -75         -94     -18
      6 |      -0.016 -0.005 |       -0.052 -0.015 |       -0.039 -0.008 -0.047 |      -464        -461      +2
      7 |      -0.026 -0.008 |       -0.028 -0.008 |       -0.010 +0.001 -0.010 |      -608        -613      -5
      8 |      -0.030 -0.012 |       -0.029 -0.009 |       -0.107 -0.033 -0.141 |      -492        -473     +19
      9 |      -0.009 -0.002 |       -0.020 -0.007 |       -0.061 -0.021 -0.081 |       -26         -12     +14
     10 |      -0.046 -0.028 |       -0.048 -0.032 |       -0.070 -0.048 -0.118 |       -23         +10     +32
     11 |      -0.027 -0.019 |       -0.037 -0.024 |       -0.041 -0.025 -0.066 |      +282        +311     +29
     12 |      -0.025 -0.018 |       -0.053 -0.027 |       -0.059 -0.022 -0.080 |      +479        +515     +36
     13 |      -0.005 -0.008 |       +0.006 +0.003 |       -0.011 +0.005 -0.006 |      +728        +734      +6
     14 |      +0.018 +0.008 |       +0.020 +0.008 |       -0.022 -0.012 -0.033 |     +1379       +1390     +11
     15 |      +0.012 +0.005 |       +0.008 +0.004 |       +0.031 +0.015 +0.046 |     +1178       +1156     -22
     16 |      +0.021 +0.007 |       +0.006 +0.003 |       +0.016 +0.005 +0.021 |      +831        +825      -6
     17 |      +0.059 +0.024 |       +0.049 +0.018 |       +0.099 +0.032 +0.132 |      +388        +356     -33
     18 |      -0.005 -0.004 |       +0.002 -0.000 |       +0.075 +0.033 +0.108 |      -407        -429     -22
     19 |      -0.018 -0.010 |       -0.005 -0.001 |       -0.031 -0.017 -0.048 |      -631        -623      +8
     20 |      -0.021 -0.012 |       -0.005 -0.002 |       -0.069 -0.038 -0.107 |      -859        -839     +20
     21 |      -0.027 -0.016 |       +0.001 +0.001 |       +0.058 +0.019 +0.077 |      -867        -879     -12
     22 |      -0.011 -0.004 |       -0.029 -0.012 |       -0.091 -0.043 -0.133 |      -415        -391     +24
     23 |      +0.029 +0.013 |       +0.033 +0.012 |       +0.133 +0.043 +0.176 |      -293        -322     -29
   suma |      +0.048 -0.032 |       +0.099 +0.001 |       +0.185 +0.011 +0.195

   horas pares:   v12-v10 -0.091   v14-v10 -0.212        horas impares:  v12-v10 +0.191   v14-v10 +0.407
   primera mitad de la semana: v12-v10 +0.061   v14-v10 +0.094   segunda mitad: v12-v10 +0.039   v14-v10 +0.101
   por día de la semana (L..D):  v12-v10 +0.009 +0.017 +0.010 +0.007 +0.006 +0.016 +0.035   v14-v10 +0.061 -0.017 +0.024 -0.097 +0.091 -0.053 +0.186
```

Máscaras de "12 horas del día fijas" que reproducen la web: con qué frecuencia entra cada hora (0,50 = indiferente):

```text
   hora:     0    1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16   17   18   19   20   21   22   23
   frec.: 0.44 0.43 0.31 0.36 0.34 0.37 0.62 0.59 0.64 0.57 0.70 0.62 0.69 0.51 0.46 0.44 0.48 0.31 0.47 0.56 0.57 0.52 0.66 0.35
```

Qué tienen en común y por qué:
- **La v10 gana en las horas de descarga** (6-12 h y 19-22 h): descarga más y compra menos en esas horas.
- **Las prudentes lo recuperan después** (23-5 h y 14-17 h): les queda energía para la noche y compran menos al recargar.
- **Por eso el resultado depende de la máscara.** La ganancia y la pérdida de una misma decisión caen en horas distintas. Una máscara con más horas de punta que de valle hace perder a las prudentes; la contraria las hace ganar. Con las horas pares, la v12 pierde 0,18 y la v14 0,42; con las impares ganan 0,38 y 0,81.
- **El día de la semana y el tramo de la semana no importan** para la v12 (todos positivos). Una máscara de "primera mitad de cada semana" daría en el banco +0,12 (v12) y +0,19 (v14), no lo de la web.
- **Son pocas horas las que mandan.** La v9 se separa de la v10 más de 100 kW en el 4,7 % de las horas; la v12, en el 8,8 %; la v14, en el 16,1 % (88 kW de media). Una sola hora con 500 kWh de diferencia mueve 0,09 puntos de la nota pública.

## 3. Fallos que harían cierta R sin que el banco los vea

**(a) Presupuesto de tiempo (40 s; después, regla de respaldo). Descartado.** Medido en la ventana de validación (1.848 pasos), con la máquina compartida:

| Versión | ms por paso | 2.016 pasos | El presupuesto se agota si el servidor es |
|---|---|---|---|
| v10 | 3,3-3,7 | 6,6-7,5 s | más de 5,3 veces más lento |
| v12 | 4,4-4,7 | 8,9-9,6 s | más de 4,2 veces más lento |
| v14 | 4,5-4,6 | 9,0-9,3 s | más de 4,3 veces más lento |

Simulado con presupuesto 40/k s (equivale a un servidor k veces más lento), 1.848 pasos:

```text
v10: x3, x4, x5: no se agota.  x6: 0 pasos (justo en el límite).  x8: 375 pasos, -4.729.  x12: 892 pasos, -8.483
v12: x3, x4: no se agota.      x5: 157 pasos, -1.753.  x6: 606 pasos, -6.257.  x8: 692 pasos, -7.097.  x12: 1140 pasos, -9.882
v14: x3, x4: no se agota.      x5: 130 pasos, -1.416.  x6: 400 pasos, -4.919.  x8: 816 pasos, -7.885.  x12: 1108 pasos, -9.763
respaldo solo al final: 7 pasos 0,00 · 28 pasos -0,22 · 59 pasos -0,43 · 97 pasos -0,80 · 157 pasos -1,75
```

No cuadra con la web por cuatro razones:
- Perder 0,2 y 0,45 exige caer en el respaldo justo en los últimos 25-60 pasos: el servidor tendría que ser entre 4,2 y 4,3 veces más lento, ni más ni menos.
- v12 y v14 tardan lo mismo: perderían lo mismo, no 0,2 una y 0,45 la otra.
- v8 y v9 hacen el mismo cálculo que la v10 y también salen por debajo.
- La regla de respaldo hunde CO2 y coste a la vez; en la web el CO2 no se mueve.

**(b) La semilla de cada semana. Descartado.** En el banco casa siempre (0 fallos). Si en el test no casara, el agente la olvida y decide como sin semilla:

```text
v10: con semilla 20.7852   sin semilla 20.7802 (-0.0050)
v12: con semilla 20.9166   sin semilla 20.9086 (-0.0080)
v14: con semilla 21.0732   sin semilla 21.0596 (-0.0136)
```
Como mucho cuesta 0,014. En la web, además, la v9 (con semilla) sacó +0,047 sobre la v8 (sin ella).

**(c) Empates del LP según la versión de scipy/HiGHS. Descartado.** Con otro algoritmo (punto interior en vez de símplex):

```text
v10 highs-ipm 20.7844 (-0.0008)    v12 highs-ipm 20.9161 (-0.0005)    v14 highs-ipm 21.0737 (+0.0005)
```

**(d) Otras cosas.**
- **El perfil interpolado de la v14 nunca se ha probado en los días 25-31**, donde el peso del mes vecino es máximo (~50 %). Las ventanas 1-7 y val son la situación espejo y dan +0,17 y +0,16 sobre la v12; en 15-21 da +0,003. Es el riesgo propio de la v14 y el banco no puede cerrarlo.
- **Los cuantiles del error de la v12** están medidos en el train. Si en el test el consumo se prevé mejor que en el train, la prudencia sobra. No se puede medir.
- El privado sale de la misma simulación que el público: un fallo de tiempo o una excepción se habría visto ya en el público (salvo que cayera solo en horas privadas del final, que exige otra vez la franja de 4,2-4,3).

## 4. Probabilidades, privado esperado y selección

**Probabilidad de cada hipótesis.** Uso como dato "v12 y v14 por debajo de la v10 en el público":

| Caso | Probabilidad de ese dato |
|---|---|
| M y máscara por horas | 0,15-0,21 |
| M y máscara por medias semanas | 0,04-0,07 |
| M y máscara por días enteros | 0,03 |
| R (con el ruido de cualquier máscara) | ~0,40-0,45 |

- Antes de ver la web: R tenía ~12 % (el banco da v12 > v10 en las seis ventanas y en 29 de 33 semanas-mes). Máscara: 40 % por horas, 40 % medias semanas, 20 % días (no se sabe; la frase "50 % de cada semana" sugiere un reparto por semana, el código admite cualquier máscara de horas).
- Después: **M ≈ 60 %, R ≈ 40 %**. Si R partía del 8 %, queda en 30 %; si partía del 20 %, en 55 %.
- Si supiéramos que la máscara es por horas: M 73 %. Si es por días enteros: R ~70 %.
- A favor de la máscara por horas: con días enteros, también v6 y v7 quedarían a 2 desviaciones del banco, y eso no tiene que ver con la prudencia.

**Nota privada esperada, frente a la v10** (la v10 = 0):

| Hipótesis | v12 | v14 |
|---|---|---|
| M, máscara por horas | +0,23 (de +0,12 a +0,30) | +0,44 (de +0,19 a +0,68) |
| M, medias semanas | +0,17 (de +0,08 a +0,26) | +0,37 (de +0,16 a +0,60) |
| M, días enteros | +0,15 (de +0,07 a +0,24) | +0,36 (de +0,15 a +0,58) |
| R | −0,04 (±0,1 a 0,17) | −0,09 (±0,3 a 0,65) |
| Mezcla 60/40 | +0,10 | +0,22 |

(Bajo M, el privado es la máscara complementaria de las que dan en el público algo parecido a la web; rango = percentiles 10 y 90. Detalle en `r3_calibracion_privado.csv`.)

**Qué dos seleccionar** (valor esperado de la mejor de las dos, frente a la v10 sola):

| Pareja | Si M | Si R | Mezcla 60/40 |
|---|---|---|---|
| **v14 y v10** | +0,44 | +0,14 | **+0,32** |
| v14 y v12 | +0,44 | +0,11 | +0,31 |
| v10 y v12 (la que coge la web por defecto) | +0,23 | +0,03 | +0,15 |

- **La v14 tiene que estar en cualquier caso.** Es la de mayor nota esperada y la que más baila; con otra al lado, ese baile juega a favor.
- **La segunda: v10 o v12 dan casi lo mismo.** La v10 gana si R tiene más del ~20 %. Con mi 40 %, la v10. Además es la única de las tres que no comparte el plan con incertidumbre, así que cubre el fallo que las otras dos tienen en común.
- **Hay que marcarlas a mano.** Por defecto la web cogería v10 y v12 (o v7/v9), que es la peor pareja.
- Si esta ronda sale un candidato que gane a la v14 en el episodio completo de las seis ventanas, ocupa el sitio de la v14. La v10 se queda.
- Si el jurado hiciera la media de las dos (y no la mejor), la pareja sería v14 y v12.

## Lo que no dio tiempo o es dudoso

- No se sabe cómo es la máscara real. Todo el reparto M/R cuelga de eso.
- Los tiempos están medidos con el agente en proceso y la máquina compartida, no con el `agent.py` empaquetado de cada versión. La medida empaquetada anterior (`ataque_empaquetado.csv`: 4,16 ms por paso, 9,0 s) coincide.
- El "respaldo solo al final" está simulado ajustando el presupuesto con tiempos de otra pasada: los pasos reales en respaldo bailan. Vale el orden de magnitud (unas 0,007-0,011 puntos por paso).
- La probabilidad de R antes de ver la web (12 %) es un juicio, no una medida.
- "Si R" en la tabla de parejas es una cuenta con normales, no una simulación.
- Las seis ventanas se solapan (1-7 con 3-9, 12-18 con 15-21): equivalen a unas 3-4 ventanas independientes.
- No se ha mirado si la web publica el tiempo de ejecución de cada envío. Si lo publica, cierra el punto (a) del todo.

## Ficheros

- `scripts/p1_lab/hard_r3_calibracion_mascaras.py`: familias de máscaras y horas del día (puntos 1 y 2).
- `scripts/p1_lab/hard_r3_calibracion_privado.py`: privado esperado si M es cierta.
- `scripts/p1_lab/hard_r3_calibracion_tiempo.py`: `tiempo`, `solver` y `semilla` (punto 3).
- `results/p1_hard/r3_calibracion_familias.csv`, `r3_calibracion_mascaras.txt`, `r3_calibracion_por_hora.csv`, `r3_calibracion_privado.csv`, `r3_calibracion_tiempo_val.csv`, `r3_calibracion_solver_val.csv`, `r3_calibracion_semilla_val.csv`.
- `results/hourly/calibra_3-9.pkl`, `calibra_12-18.pkl`, `calibra_15-21.pkl` (nuevas).
