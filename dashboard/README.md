# Dashboard de decisió · Bateria del Campus Nord

Aplicació web (React + Vite + Tailwind + TanStack Query) per al **Premi Tukey**
(side challenge del Datathon FME 2026). Respon, amb les dades i el simulador del
repte de la bateria, les preguntes de decisió: **val la pena la bateria, com
gestionar-la, de quina mida i si ens podem fiar de les dades.**

Té **dues perspectives** (segons qui el mira, selector a la barra lateral + pàgina d'inici):

- **Decisió — Direcció i Sostenibilitat:** el dashboard estratègic (val la pena? quina mida? per emissions o preu?).
- **Operació del campus:** monitoratge del dia a dia (estat ara, pla d'avui, estalvi de la setmana, avisos). Vista `Avui` +
  `El campus` (connexió) + `Sensors`. Dades de `operations.json` / `hm_operations.json`.

I **dos modes** (bateria):

- **ST — Estàndard:** el repte original (bateria 2 MWh, previsió perfecta a 24 h). 7 vistes.
- **HM — Hard Mode:** el campus ampliat (bateria 6 MWh · ±1.500 kW, solar ×12, només 3 h
  de preu/CO₂ conegudes, meteo). 6 vistes. Dades de `scripts/export_hard.py`
  (reprodueix `scripts/p1_hard.py`): agent 20,83 / òptim 22,40; públic 23,70 (1r de 32).

La ruta és `#/<mode>/<vista>` (p. ex. `#/hm/solar`); per defecte `#/st/resum`.

No toca cap codi de `src/battery/` ni de l'agent: viu sencer dins de `dashboard/`
i només llegeix els mòduls del repte en mode lectura per generar les dades.

## Com es fa servir

```bash
cd dashboard
npm install
npm run data      # genera public/data/*.json del mode estàndard (ST)
npm run data:hard # genera public/data/hm_*.json del hard mode (HM)
npm run dev       # servidor de desenvolupament (http://localhost:5173)
npm run build     # build de producció a dist/
npm run preview   # serveix el build
```

`npm run data` necessita un Python amb les llibreries del repte. Ja hi ha un entorn
preparat a `dashboard/.venv` (ignorat per git); si no hi és:

```bash
python3 -m venv .venv && .venv/bin/pip install numpy pandas scipy scikit-learn joblib
python ../scripts/preparar_oficial.py    # descomprimeix oficial.zip (si cal)
npm run data
```

## D'on surten les xifres (coherència)

`scripts/export_data.py` reprodueix **exactament** els càlculs dels scripts
`analysis/p2_*.py` de P2 i del simulador `src/battery/sim.py`, i escriu JSON
estàtics a `public/data/`. Així cada número del dashboard coincideix amb l'informe
de P2 i amb `eval.py` (agent 6,09 · oracle 6,12 · 99,6 %, 2 MWh → 43 t i 92 k€…).
L'app desplegada només llegeix els JSON: no necessita Python.

| JSON | Contingut | Font |
|---|---|---|
| `kpis.json` | indicadors de portada | `sim` + `escenarios.csv` |
| `patterns.json` | CO₂/preu per hora i mes, conflicte | `p2_patrones` |
| `objective.json` | compromís CO₂/cost/70-30 | `p2_patrones` |
| `strategies.json` | comparativa, sostre, setmana tipus | `p2_resultados` + `p2_techo` |
| `scenarios.json` | dimensionat 1–16 MWh | `analysis/escenarios.csv` |
| `quality.json` | qualitat de les dades | `p2_calidad_datos` |
| `meta.json` | procedència i paràmetres | — |

## Les 7 vistes (cada una acaba en una decisió)

1. **Resum executiu** — val la pena la bateria?
2. **On es consumeix l'energia** — mapa de calor del campus (interactiu: hover/clic). On connectar la bateria?
3. **Quan contamina i costa la xarxa** — quan carregar i descarregar?
4. **CO₂, cost o 70/30** — què ha d'optimitzar l'agent?
5. **Funciona la nostra estratègia** — és bo el nostre agent?
6. **Quina mida de bateria** — 1, 2, 4 o 8 MWh? (interactiu: capacitat + payback)
7. **Ens podem fiar de les dades** — honestedat metodològica.

> **Nota sobre el mapa (vista 2):** és un **mapa 3D real** (MapLibre GL + tessel·les
> d'OpenStreetMap, en escala de grisos) amb les traces reials dels edificis del
> Campus Nord (`public/data/campus_buildings.geojson`, baixat d'OSM via Overpass).
> Els edificis de la UPC s'**extrudeixen en 3D** amb alçada i color segons el consum;
> l'entorn no-UPC queda pla i gris. El dataset NO desglossa el consum per edifici
> (només hi ha un comptador total), així que l'alçada/color és un **model il·lustratiu**
> que reparteix el total *mesurat* per tipus d'ús (`src/data/campus.ts`), separat del
> pipeline de dades mesurades i etiquetat com a tal a la vista. Necessita xarxa per a
> les tessel·les. Ajuda a decidir on connectar la bateria (prop de les càrregues grans
> i constants: BSC/MareNostrum).
>
> Per capturar el mapa, cal espera real (el Web Worker de MapLibre): `node scripts/shoot.mjs <url> <out.png>`.

## Decisions de disseny (criteris Tukey)

- **Utilitat per decidir:** cada gràfica porta la seva conclusió i cada vista una
  franja de *decisió que fonamenta*. Controls interactius al dimensionat i a la
  setmana tipus.
- **Adequació:** paleta validada (skill `dataviz`), que a més coincideix amb les
  figures de P2. **Mai dos eixos Y** en una gràfica; rampes d'un sol to per als
  mapes de calor; etiquetes directes i tooltips.
- **Coherència:** unitats i àmbits etiquetats sempre (scores sobre 1.848 h de
  validació vs t/€ anualitzats sobre 258 dies; dataset vs consum real).

## Estructura

```
dashboard/
  scripts/export_data.py   # genera els JSON (no s'empaqueta a l'agent)
  public/data/*.json       # dades estàtiques (es regeneren amb npm run data)
  src/
    lib/        theme, format, data (hooks TanStack)
    components/ ui, charts (tooltip, heatmap, legenda)
    views/      Overview, Patterns, Objective, Strategy, Sizing, Quality
```
