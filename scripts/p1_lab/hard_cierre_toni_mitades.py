"""Cierre (lente: lo de Toni). La FINAL frente a la v10 con el criterio del comparador de Toni (mejora_privado.py):
nota en los meses que él supone privados (mar-ago) y públicos (sep-feb), cada mitad con su referencia sin batería.
Usa los registros hora a hora de hard_cierre_toni_tope.py (no simula). NO se empaqueta."""
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
REPO = Path(__file__).resolve().parents[2]
for extra in (str(REPO / "src"), str(REPO / "scripts"), str(REPO / "scripts" / "p1_lab")):
    if extra not in sys.path:
        sys.path.insert(0, extra)
import pandas as pd  # noqa: E402

import p1_hard as B  # noqa: E402
from battery.sim import baseline_totals, score  # noqa: E402

PRIVADO, PUBLICO = (3, 4, 5, 6, 7, 8), (9, 10, 11, 12, 1, 2)
full = B.hard_table()
for win in (sys.argv[1:] or ["val", "ep14"]):
    if win.startswith("ep"):
        import hard_ataque_comun as C
        df, _ = C.episodio_test("copia", desfases=(14, 21, 7) if win == "ep14" else (7, 14, 21))
    else:
        df = B.split_frame(full, win)
    df = df.reset_index(drop=True)
    out = {}
    for which in ("v10", "final"):
        log = pd.read_csv(REPO / "results" / "p1_hard" / f"cierre_toni_tope_{which}_{win}.csv", parse_dates=["timestamp"])
        assert len(log) == len(df) and (log.timestamp.values == pd.DatetimeIndex(df.timestamp).values).all()
        for label, months in (("privado_mar-ago", PRIVADO), ("publico_sep-feb", PUBLICO), ("todo", tuple(range(1, 13)))):
            m = df.timestamp.dt.month.isin(months).to_numpy()
            d, l = df[m], log[m]
            s = score({"co2_kg": float((l.import_kw.values * d.co2_kg_kwh.values).sum()),
                       "cost_eur": float((l.import_kw.values * d.price_eur_kwh.values).sum()), "infractions": 0}, baseline_totals(d))
            out[(which, label)] = (s["score_raw"], s["d_co2_pct"], s["d_cost_pct"])
    for label in ("privado_mar-ago", "publico_sep-feb", "todo"):
        a, b = out[("v10", label)], out[("final", label)]
        print(f"{win:5s} {label:16s} v10 {a[0]:.3f} (CO2 {a[1]:.2f} coste {a[2]:.2f}) | FINAL {b[0]:.3f} (CO2 {b[1]:.2f} coste {b[2]:.2f}) | "
              f"FINAL - v10 = {b[0] - a[0]:+.3f} (CO2 {b[1] - a[1]:+.2f}, coste {b[2] - a[2]:+.2f})")
