# analysis/

Owner: P2 (datos y análisis). Gráficas y cifras para la presentación (las usa P3). **No se empaqueta**: aquí se puede usar matplotlib, notebooks, etc.

De dónde salen los datos:

```bash
python eval.py --agent all --save-hourly
```

Escribe `results/hourly/{nothing,greedy,mpc,oracle}.csv`. Las columnas están en `src/battery/sim.py` (LOG_COLUMNS).

Encargos (ver `docs/prompts-arranque.md`, P2):
- CO₂ y precio por hora del día y por mes: ¿cuándo es sucia y cara la red? ¿Coinciden?
- Una semana tipo: carga de la batería sobre el CO₂ del mix (log de `--save-hourly`).
- Por qué el ahorro máximo es de ~6 %.
- Escenarios de tamaño de batería (1, 2, 4 y 8 MWh) con el oracle: toneladas de CO₂ y €/año.
- Comparativa de estrategias ("capturamos el 99,6 % del máximo teórico").

Cada gráfica, con una frase de "qué demuestra" para P3.

## Hecho (fases 1 y 2)

| Informe | Script | Contenido |
|---|---|---|
| [`calidad_datos.md`](calidad_datos.md) | `python analysis/p2_calidad_datos.py` | Qué falla en los datos, cuánto y si cambia el score |
| [`patrones.md`](patrones.md) | `python analysis/p2_patrones.py` | Cuándo es sucia y cara la red, y el conflicto entre CO₂ y precio |
| [`techo.md`](techo.md) | `python analysis/p2_techo.py` | Por qué el ahorro máximo es de ~6 % |
| [`escenarios.md`](escenarios.md) | `python analysis/p2_escenarios.py` | Qué ahorraría una batería de 1, 2, 4, 8 o 16 MWh |

| [`resumen_graficas.md`](resumen_graficas.md) | `python analysis/p2_resultados.py` (2 de las 11 gráficas) | Las 11 gráficas ordenadas por bloque del guion, con la cifra que hay que decir |
| [`informe_p2_para_p1.md`](informe_p2_para_p1.md) | — | Qué ha hecho P2, qué tiene que tener en cuenta P1 y qué hacer ahora |

Las figuras están en `figs/` (PNG a 200 ppp, listas para una slide). El estilo común está en `p2_estilo.py`.
