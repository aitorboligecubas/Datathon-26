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
| Sáb 14/11 | Reequilibrar los roles: P1 optimización y robustez, P2 datos y análisis (+ escenarios de tamaño de batería para UPC Sostenible), P3 relato, presentación e integración. Trabajo por fases | P2 centrado en previsión | la previsión de consumo apenas cambia el score (la solar es minúscula) y el mpc ya está al 99,3 % del techo: el valor está en la robustez, las pruebas y el relato | equipo |
| Sáb 14/11 | Detectar el final del episodio solo por la previsión recortada, sin contar pasos | contador hasta 2.016 | con el contador, el agente se paraba desde la hora 2.016: histórico completo (5.993 h) 1,78 → **5,67** (oracle 5,68). En validación no cambia | P1 |
| Sáb 14/11 | Tope de descarga: nunca más de lo que el campus compró la hora anterior. Se justifica por el mecanismo (avería del contador de 14 h a 0 el 17–18/06/2026: se vertían 666 kWh), no por la ganancia | descargar según la previsión | validación 6,08 → **6,09**; en el train no cambia ninguna decisión; sin parámetros | P1 |
| Sáb 14/11 | Mantener el valor de la carga al final del horizonte aunque no aporte | quitarlo | 0,00 de diferencia con cualquier valor (cuantil 0 a 1): el plan de 24 h ya fija la primera hora | P1 |
| Sáb 14/11 | No invertir en prever el consumo | GBDT de demanda | previsión propia frente a una plana de 1.000 kW: 0,00; con el consumo real: +0,02 | P1 |
| Sáb 14/11 | La duda "seguido o por semanas" no es un riesgo | — | por semanas: mpc 6,47 / oracle 6,49, 0 infracciones. Con ruido del 20 % en precio y CO₂: 6,01. Train: 5,54 / 5,54 | P1 |
