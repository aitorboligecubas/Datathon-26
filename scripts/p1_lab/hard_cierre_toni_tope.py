"""Cierre (lente: lo de Toni). ¿Afecta a la FINAL el fallo del tope de descarga que arregla `revision-decision`?
Cuenta, hora a hora, cuándo el tope del modo estándar (lo comprado la hora anterior) cambia la acción del plan.
NO se empaqueta.   python scripts/p1_lab/hard_cierre_toni_tope.py val [final|v10]
"""
import sys
import types
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
REPO = Path(__file__).resolve().parents[2]
for extra in (str(REPO / "src"), str(REPO / "scripts"), str(REPO / "scripts" / "p1_lab")):
    if extra not in sys.path:
        sys.path.insert(0, extra)
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import p1_hard as B  # noqa: E402
from battery.policy import MPCPolicy  # noqa: E402

win = sys.argv[1] if len(sys.argv) > 1 else "val"
which = sys.argv[2] if len(sys.argv) > 2 else "final"
full = B.hard_table()
if win.startswith("ep"):      # episodio con el calendario real del test (datos de 14 o 7 días antes)
    import hard_ataque_comun as C
    df, exclude = C.episodio_test("copia", desfases=(14, 21, 7) if win == "ep14" else (7, 14, 21))
    exclude = set(exclude)
else:
    df = B.split_frame(full, win)
    exclude = set(df.timestamp)
fit_df = full[~full.timestamp.isin(exclude)]
solar = B.fit_solar(fit_df)
if which == "final":
    a = B.hard_agent(B.fit_market(exclude, fit_df), solar)
else:
    a = B.hard_agent(B.fit_market(exclude, fit_df, blend=False, weekend=False), solar, use_scenarios=False)
pol = a.policy
rec = []
orig_cap = pol.cap_discharge


def cap(self, action_kw, obs):
    out = orig_cap(action_kw, obs)
    std = MPCPolicy.cap_discharge(self, action_kw, obs)
    nl = self.netload
    rec.append(dict(timestamp=obs.timestamp, plan=float(action_kw), out=float(out), std=float(std),
                    net_prev=float(obs.load_prev_kw - obs.pv_prev_kw), scen_used=bool(getattr(nl, "scen_used", False)),
                    fresh=bool(getattr(nl, "fresh", False)), net_lo0=float(getattr(nl, "net_lo0", float("nan")))))
    return out


pol.cap_discharge = types.MethodType(cap, pol)
totals, log = B.simulate_hard(a, df)
base = B.baseline_totals(df)
co2 = 100 * (base["co2_kg"] - totals["co2_kg"]) / base["co2_kg"]
eur = 100 * (base["cost_eur"] - totals["cost_eur"]) / base["cost_eur"]
r = pd.DataFrame(rec).merge(log, on="timestamp", how="left")
r["net_real"] = r.load_kw - r.pv_kw
n = len(df)
sur = r.net_prev <= 0
want = r.plan < -1e-6
changed = (r.out - r.plan).abs() > 1e-6
would = (r["std"] - r.plan).abs() > 1e-6
blocked = sur & want & (r.out > -1e-6)
print(f"[{which}] {win}: {n} h, llamadas al tope {len(r)}, score {0.7 * co2 + 0.3 * eur:.3f} (CO2 {co2:.2f} coste {eur:.2f}) "
      f"infr {totals['infractions']} vertido {totals['export_kwh']:.0f} kWh, SOC final {totals['final_soc_kwh']:.0f}")
print(f"  horas con el plan con incertidumbre (scen_used): {int(r.scen_used.sum())} de {len(r)}")
print(f"  horas tras una hora con excedente (lectura neta <= 0): {int(sur.sum())}")
print(f"  ... y el plan quería descargar: {int((sur & want).sum())}; de ellas con consumo neto real > 0: {int((sur & want & (r.net_real > 0)).sum())}")
print(f"  ... BLOQUEADAS por el tope (plan < 0, sale 0): {int(blocked.sum())}; kWh que el plan quería: {-r.plan[blocked].sum():.0f}")
print(f"  horas en que el tope cambia la acción (cualquier caso): {int(changed.sum())}; kWh recortados {(r.out - r.plan)[changed].sum():.0f}")
print(f"  horas en que el tope del modo estándar la HABRÍA cambiado: {int(would.sum())} (tras excedente: {int((would & sur).sum())}); kWh {(r['std'] - r.plan)[would].sum():.0f}")
fin = sur & (r.net_real > 0) & (r.action_kw > -1e-6)
print(f"  acción final sin descarga tras excedente con consumo neto real > 0: {int(fin.sum())}; de ellas el plan quería descargar: {int((fin & want).sum())}")
r.to_csv(REPO / "results" / "p1_hard" / f"cierre_toni_tope_{which}_{win}.csv", index=False)
