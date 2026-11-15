"""El arreglo del final del test: la última semana dura 168 h desde su primera hora. Se compara el código nuevo con el
ZIP de la FINAL (v14) en los dos calendarios posibles de agosto.

    python scripts/p1_lab/hard_fin_agosto.py <carpeta con el agent.py de la v14>
"""
import importlib.util
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "src"), str(REPO / "scripts")]
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import p1_hard  # noqa: E402
from battery.hard import HardBatteryAgent  # noqa: E402

spec = importlib.util.spec_from_file_location("agent_v14", sys.argv[1] + "/agent.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
t = p1_hard.hard_table(); ts = pd.DatetimeIndex(t["timestamp"]); H1 = pd.Timedelta(hours=1)


def week(src, dst, n=168):
    s = pd.Timestamp(src); w = t[(ts >= s) & (ts < s + n * H1)].copy()
    w["timestamp"] = w["timestamp"] + (pd.Timestamp(dst) - s); return w


prior = json.load(open(REPO / "models" / "hard_market.json"))
c2, ce = float(prior["co2_ref_kg_per_h"]) * 2016, float(prior["cost_ref_eur_per_h"]) * 2016
jun = week("2026-06-17 00:00", "2026-06-24 00:00")
jul = week("2026-07-18 00:00", "2026-07-25 00:00")
for name, aug in (("agosto 25-31", week("2026-07-14 00:00", "2026-08-25 00:00")),
                  ("agosto 16 (23 h) - 23 (22 h)", week("2026-07-12 23:00", "2026-08-16 23:00"))):
    df = pd.concat([jun, jul, aug], ignore_index=True)
    (ta, la), (tb, lb) = p1_hard.simulate_hard(mod.BatteryAgent(), df), p1_hard.simulate_hard(HardBatteryAgent(), df)
    d = 100 * (0.7 * (ta["co2_kg"] - tb["co2_kg"]) / c2 + 0.3 * (ta["cost_eur"] - tb["cost_eur"]) / ce)
    dif = np.abs(la["action_kw"].to_numpy() - lb["action_kw"].to_numpy()) > 1e-9
    print(f"{name}: v14 soc_final={ta['final_soc_kwh']:.1f} infr={ta['infractions']} | nueva soc_final={tb['final_soc_kwh']:.1f} "
          f"infr={tb['infractions']} | acciones distintas={int(dif.sum())} (antes de agosto: {int(dif[:336].sum())}) | ganancia={d:+.3f} puntos", flush=True)
