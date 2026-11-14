# Cómo trabajamos: 3 personas, 3 Claudes, un repo (Opción B)

Owner: integrador.

## Quién es quién (rellenad los nombres)

| Rol | Persona | GitHub | Rama |
|---|---|---|---|
| P1 · Optimizador | _nombre_ | _@usuario_ | `p1-optimizador` |
| P2 · Previsión y datos | _nombre_ | _@usuario_ | `p2-prevision` |
| P3 · Validación y relato | _nombre_ | _@usuario_ | `p3-validacion` |
| Integrador | _P3 o una 4.ª persona_ | | revisa y fusiona en `main` |

Recomendamos que **P3 haga de integrador**. Valida todo lo que entra, que es justo lo que necesita para
contar la historia al jurado, y su carga de código es menor el sábado. Si sois 4, la cuarta persona es
integradora a tiempo completo y además lleva los envíos oficiales.

## 1. Preparar GitHub (una vez, lo hace quien tenga el repo)

1. **Hacer el repo privado durante el evento.**
   Settings → General → Danger Zone → Change visibility → Private.
   Ahora mismo es público: cualquiera ve la estrategia, y los datos oficiales no deben subirse.
2. **Invitar al equipo:** Settings → Collaborators → Add people, con los usuarios de GitHub de la tabla.
3. **Fusionar la estructura inicial en `main`**, que está en la rama `claude/clever-euler-koiz2q`.
4. **Proteger `main`** (recomendado):
   - Settings → Branches → Add branch ruleset (o "Add rule") sobre `main`.
   - Activar "Require a pull request before merging" y "Require status checks to pass", con el check `tests` de la CI.
5. **Modo de fusión:** Settings → General → Pull Requests → dejar "Allow merge commits" activado.
   Así las ramas personales se sincronizan sin conflictos.

## 2. Preparar cada portátil (cada persona, unos 10 min)

```bash
git clone https://github.com/aitorboligecubas/Datathon-26.git
cd Datathon-26
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
git checkout -b p1-optimizador                          # o p2-prevision / p3-validacion
python -m pytest -q && python eval.py --agent all       # tiene que salir todo en verde
```

Después:
- Descomprimid el ZIP oficial dentro del repo, en `starter_kit/`. Git lo ignora y no se sube.
- Arrancad Claude Code dentro de la carpeta (`claude`). Lee `CLAUDE.md` automáticamente.
- Pegad como primer mensaje el prompt de vuestro rol de `docs/prompts-arranque.md`.

## 3. El día a día

```text
           p1-optimizador ──●──●──PR──┐         ┌──●──●──PR──┐
main ──────────────────────────────────●(merge)──●────────────●(merge)── ...
           p2-prevision   ──●──●──●──PR──────────┘
```

- **Sincronizarse con `main`**: después de cada merge, y siempre antes de abrir una PR.

  ```bash
  git fetch origin && git merge origin/main
  ```

- **Abrir una PR**, con commits pequeños y un tema por PR:

  ```bash
  git push -u origin p1-optimizador
  ```

  Luego, en GitHub, abrid la PR de `p1-optimizador` → `main` y rellenad la plantilla. Hay que pegar la tabla de `eval.py`.
- **Quién fusiona**: solo el integrador, y solo con la CI en verde y si la tabla de `eval.py` no empeora (o si el empeoramiento está justificado).
- **Si necesitas un cambio en un fichero de otro rol**: apúntalo en tu PR, en "Peticiones a otros roles", y díselo a esa persona.
  Tu Claude no lo toca.
- **`results/experiments.csv`** es el registro común de experimentos. Lo escribe `eval.py --log` y git junta
  las líneas de todos sin conflictos (`.gitattributes`, `merge=union`).

## 4. Puntos de sincronización (15 min, todos juntos)

| Cuándo | Qué |
|---|---|
| **Sáb 12:30** | Estructura en `main`, todos clonados y con su Claude arrancado. El integrador empieza a VERIFICAR (`docs/reto.md`). |
| **Sáb 14:00** (comida) | Formato oficial verificado. P3: el simulador cuadra con `environment.py`. P2: `hourly.csv` con datos reales. Primer `eval.py --agent all` con datos reales. |
| **Sáb 17:00** | Primer envío oficial con el MPC v0. Decidir en qué se centra cada uno por la tarde según dónde está la diferencia entre `mpc` y `oracle`. |
| **Sáb 21:00** (cena) | Merge de todo. Envío oficial. P3 enseña las primeras gráficas. |
| **Dom 0:00** | Último merge grande. Dejar programado qué se prueba por la mañana. Dormir algo. |
| **Dom 9:00** | Últimas PRs. **9:30: congelación del código.** Solo se arreglan errores. |
| **Dom 10:00–11:30** | Envío final y slides. Ensayo del pitch. |
| **Dom 12:00** | **Fin de las entregas.** 14:00, demos. |

Envíos oficiales: 10 al día. Apuntad cada uno en `docs/envios.md` con el commit, el score local y el del leaderboard.
El leaderboard público es solo el 50 %, así que no os ajustéis a él.
