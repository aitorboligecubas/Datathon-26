"""Revisión "logica" (HARD MODE). NO se empaqueta. Solo con el train: ¿los días laborables de Semana Santa
(1 y 2 de abril de 2026, miércoles y jueves) consumen como un laborable normal? El test de marzo (25-31/03/2026)
incluye el lunes 30 y el martes 31 de esa misma semana, que CAMPUS_HOLIDAYS trata como laborables.

    python scripts/p1_lab/hard_rev_logica_semana_santa.py
"""
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "scripts"))
import p1_hard  # noqa: E402

t = p1_hard.hard_table()
t = t[(t.timestamp >= "2026-03-01") & (t.timestamp < "2026-04-24")].copy()
t["dia"] = t.timestamp.dt.normalize()
d = t.groupby("dia").load_kw.agg(["mean", "max"]).round(0)
d["dow"] = d.index.dayofweek
lab = d[(d.dow < 5) & ~d.index.isin(pd.to_datetime(["2026-04-01", "2026-04-02", "2026-04-03", "2026-04-06"]))]
print("laborables normales de marzo y abril (media diaria kW): media %.0f, mín %.0f, máx %.0f, n=%d" % (
    lab["mean"].mean(), lab["mean"].min(), lab["mean"].max(), len(lab)))
print("domingos: media %.0f" % d[d.dow == 6]["mean"].mean())
print(d.loc["2026-03-27":"2026-04-08"].to_string())
