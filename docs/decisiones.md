# Registro de decisiones (para el jurado)

Owner: P3. Cada decisión con su número de `eval.py` (validación con datos **oficiales**), incluidas las descartadas.
Al jurado le interesa tanto el razonamiento como el resultado.

| Fecha | Decisión | Alternativas | Evidencia (score / ΔCO2% / ΔCoste%) | Quién |
|---|---|---|---|---|
| Sáb 14/11 | Reto de la batería, porque es optimización pura con una métrica clara (encaja con el perfil FME) | Qualcomm, RawTree | `docs/retos-datathon-fme-2026.md` | equipo |
| Sáb 14/11 | Estrategia base: MPC con LP (HiGHS) a 24 h, con pesos que reproducen el score y regla greedy de respaldo | reglas fijas como la plantilla, RL | **datos oficiales: mpc 5,97 / oracle 6,12 / plantilla oficial 0,03 (7 infracciones) / greedy 0,08** | P1 |
| Sáb 14/11 | Pesos del LP con referencias del train (93,2 kg CO₂/h y 156,3 €/h) en lugar de valores por defecto | pesos fijos | mpc 5,87 → 5,97 (ΔCO₂ 5,21 → 5,62 %) | P2 |
| Sáb 14/11 | La previsión de demanda y solar no es prioritaria: la solar es de 26 kW de media y la red solo baja de 500 kW el 0,5 % de las horas | GBDT de demanda | ruido del 10 % en precio/CO₂: 5,97 → 5,94 | equipo |
| Sáb 14/11 | Gastar la carga al final: si la previsión llega con < 24 valores (fin de los datos), el valor terminal es 0. El test tiene ~1.700 h, no 2.016, así que no basta con contar pasos | contar hasta 2.016 | mpc 5,97 → **6,08** (oracle 6,12). Ante el jurado: la carga final no puntúa en el reto; en la operación real habría que darle valor | P1 |
| Sáb 14/11 | Nuestro simulador replica exactamente environment.py | usar solo el oficial | `scripts/calibrate_sim.py`: mismo score, CO₂, coste e infracciones | P3 |
| Sáb 14/11 | Validación = últimas 168 h de cada mes del train, seguidas en un episodio (imita el test) | k-fold aleatorio (filtra futuro) | — | P3 |
