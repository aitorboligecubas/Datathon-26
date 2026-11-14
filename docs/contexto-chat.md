# Contexto completo para continuar en otro chat

*Generado el sábado 14 nov 2026. Pega este fichero al empezar un chat nuevo (o di "lee docs/contexto-chat.md").*

## Quién y qué
- Participo en la **Datathon FME 2026** (6.ª edición, AED + FME-UPC), **sáb 14 – dom 15 nov 2026**,
  Facultat de Matemàtiques i Estadística, C/ Pau Gargallo 14, Barcelona. Gratis, 400+ participantes,
  equipos de **máx. 4**, **+2.000 €** en premios. Web: https://www.datathon.cat
- Hemos elegido el **reto de UPC Sostenible: control de la batería del campus**.
- Forma de trabajo: **Opción B** → cada miembro con su Claude Code en su portátil, **repo de GitHub
  compartido**, una rama por persona, PRs pequeños y frecuentes a `main`, una persona integradora.
- Aún sin definir: nombres/perfiles del equipo, quién es el integrador, URL del repo en GitHub.

## Horario oficial
**Sábado 14/11:** 8:30 check-in (Vèrtex) · 9:00 inauguración · 10:00 desayuno y presentación de retos ·
11:30 excursión a la FME · 12:00 GitHub 101 · 14:00 comida · 15:00 charla Qualcomm · 16:00 Innovamat ·
17:00 snacks · 18:00 realidad virtual · 19:00 charla Novartis · 21:00 cena · 22:00 Wikirace ·
0:00 pica-pica · 0:30 karaoke.
**Domingo 15/11:** 9:00 desayuno · **12:00 último aviso de entregas** · 13:00 comida · **14:00 demos** ·
17:00 deliberación · 17:30 premios · 18:30 despedida.
→ Ventana real de trabajo ≈ sáb 10:00 → dom 12:00 (~26 h). Congelar código dom ~9:30.

## Normas generales (datathon.cat/condicions)
- Se permiten ideas previas y librerías open source; **no reutilizar código propio previo**.
- Rúbrica orientativa: idea e innovación, tecnología, aprendizaje, diseño y usabilidad, presentación,
  resolución del problema, eficiencia (incl. escalabilidad).
- Ediciones anteriores: **500 € por reto + 500 € premio Rookie** (1.º–2.º curso o bachillerato);
  cada sponsor juzga su reto. Para 2026 el reparto no está publicado.
- Ganadores 2025 en retos abiertos: modelo + SHAP + LLM que explica en lenguaje de negocio + "qué
  cambiar". En retos con leaderboard: pipeline sólido y validación temporal honesta.

## Los tres retos (detalle en retos-datathon-fme-2026.md)
1. **UPC Sostenible — batería** (ELEGIDO): https://repteupc.datathon.cat
2. Qualcomm — copiloto de matemáticas en Arduino UNO Q con M3Kang: https://github.com/mpous/datathon-UPC-maths-qualcomm-arduino-unoq
3. RawTree — recomendador en tiempo real: https://datathon.rawtree.dev

## Reto elegido: datos clave
- `BatteryAgent.act(obs) -> kW` hora a hora, 12 semanas de test (2.016 h; última semana de cada mes;
  train = primeras ~3 semanas de cada mes, un año de datos reales).
- `Score = max(0, 0,70·ΔCO2% + 0,30·ΔCoste% − penalización·infracciones)`; **el jurado decide de
  forma decisiva** (presentación, razonamiento técnico, análisis, justificación).
- Batería 2.000 kWh, ±500 kW, rendimiento 90 % (η = √0,9 por sentido), SOC inicial 1.000 kWh sin
  reinicios, sin degradación, exportar no paga ni ahorra CO₂.
- obs incluye precio y CO₂ de las próximas 24 h; demanda y solar futuras hay que preverlas.
- Envío: 10/día, 60 s para toda la simulación, ZIP ≤ 25 MB con agent.py + .pkl en la raíz,
  solo numpy/pandas/scipy/sklearn/joblib/xgboost/lightgbm/math/datetime/collections/itertools/
  random/json/pathlib/typing. Leaderboard público = 50 %, privado = 50 %.
- Datos: contador.csv (15 min, demanda = −contador), inversor.csv (5 min, 3 inversores), meteo.csv,
  entradas_salidas.csv, precio_pvpc.csv (1 h), co2_red.csv (1 h). ZIP oficial de 13 MB con
  tutorial.ipynb, agent.py, environment.py (simulador oficial) y docs.
- Conflictos a resolver con environment.py: penalización −0,20 vs −1,00; excedente 0,04 €/kWh vs 0.
- Estrategia recomendada: peso por hora `w = 0,7·co2/media + 0,3·precio/media`; mover energía
  solo si `w_destino·0,9 > w_origen`; cargar excedente solar siempre; **MPC con programación lineal**
  (scipy linprog/HiGHS) a 24 h con valor terminal del SOC; medir que cabe en 60 s.

## Recomendaciones de organización del repo (para el chat que lleva el código)
- Reparto por ficheros para que dos Claudes nunca toquen el mismo:
  P1 optimizador (`policy.py`: BatteryAgent, MPC/LP, safety clamp), P2 previsión
  (`forecaster.py` + modelos .pkl + carga de datos), P3 validación y relato (simulador local
  calibrado contra `starter_kit/environment.py`, análisis, slides), integrador (`eval.py`,
  empaquetado, tests).
- Contrato de previsión: `Forecaster.update(obs)` y `Forecaster.forecast(obs, h=24) -> (load_kw[h], pv_kw[h])`.
- El servidor solo carga `agent.py` (no puede importar módulos hermanos: `importlib`/`sys` no
  están permitidos) → usar un script que **concatene** forecaster + policy en un solo `agent.py`
  y compruebe los imports prohibidos antes de generar el ZIP.
- Un único comando de evaluación para todo el equipo, con split de validación = última semana de
  train de cada mes (imita el test) y un registro de experimentos (CSV) en el repo.
- Safety clamp oficial: `|p| ≤ 500`; al cargar `p ≤ (2000 − soc)/η − 1e-4`; al descargar
  `|p| ≤ soc·η − 1e-4`, con η = √0,90.
- En otro chat se hizo un prototipo de esta estructura (simulador, evaluador, baseline heurístico
  con score 5,2 en datos sintéticos, 0 infracciones). No está subido a GitHub; es solo referencia.

## Pendiente
1. Descargar el ZIP oficial y descomprimirlo en la raíz del repo.
2. Montar la estructura en el repo de GitHub del equipo (chat de código).
3. Decidir roles e integrador; crear ramas `p1-optimizador`, `p2-prevision`, `p3-validacion`.
4. P3: calibrar `src/sim.py` contra `starter_kit/environment.py` (primera hora).
5. P1: MPC/LP, primero con previsión perfecta (techo teórico), luego con el forecaster.
6. P2: forecaster entrenado (perfiles + GBDT con meteo/hora/día) y medir su error.

## Otros
- La skill `hackathon-genius` se actualizó a 14-nov-2026 (`hackathon-genius.zip`). Hay que subirla
  en claude.ai → Ajustes → Capacidades → Skills para que se aplique.
