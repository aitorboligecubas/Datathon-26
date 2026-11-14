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
