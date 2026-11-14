# analysis/

Owner: P3. Gráficas y análisis para la presentación. **No se empaqueta**: aquí se puede usar matplotlib, notebooks, etc.

De dónde salen los datos:

```bash
python eval.py --agent all --save-hourly
```

Escribe `results/hourly/{nothing,greedy,mpc,oracle}.csv`. Las columnas están en `src/battery/sim.py` (LOG_COLUMNS).

Ideas de figuras: una semana tipo (carga de la batería sobre el CO₂ del mix), ahorro acumulado de CO₂ y de €,
comparativa de estrategias ("capturamos el X % del máximo teórico"), análisis por mes y robustez con `--fc-noise`.
