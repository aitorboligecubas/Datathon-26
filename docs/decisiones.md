# Registro de decisiones (para el jurado)

Owner: P3. Cada decisión con su número de `eval.py` (validación con datos **oficiales**), incluidas las descartadas.
Al jurado le interesa tanto el razonamiento como el resultado.

| Fecha | Decisión | Alternativas | Evidencia (score / ΔCO2% / ΔCoste%) | Quién |
|---|---|---|---|---|
| Sáb 14/11 | Reto de la batería, porque es optimización pura con una métrica clara (encaja con el perfil FME) | Qualcomm, RawTree | `docs/retos-datathon-fme-2026.md` | equipo |
| Sáb 14/11 | Estrategia base: MPC con LP (HiGHS) a 25 h, con pesos que reproducen el score y regla greedy de respaldo | reglas fijas como la plantilla, RL | sintéticos: mpc 16,1 frente a oracle 18,1 (solo prueba el circuito) | P1 |
| Sáb 14/11 | Validación = últimas 168 h de cada mes del train, seguidas en un episodio (imita el test) | k-fold aleatorio (filtra futuro) | — | P3 |
