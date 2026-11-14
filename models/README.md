# models/

Owner: P2. Lo que hay aquí (`.json`, `.pkl`, `.joblib`, `.npy`, `.npz`) va en la raíz del ZIP, junto a `agent.py`.

- `forecaster.json`: perfiles de demanda (168 valores por hora de la semana) y solar (24 por hora).
- `objective_refs.json`: media horaria de CO₂ (kg) y coste (€) sin batería, que dan los pesos del LP.

Se generan con `python scripts/train_forecaster.py`, solo a partir del split de **train**.
Haced commit solo de artefactos entrenados con datos oficiales y pequeños (el ZIP tiene que pesar ≤ 25 MB).
Si no hay artefactos, el agente funciona igual: aprende el perfil sobre la marcha y usa referencias por defecto.
