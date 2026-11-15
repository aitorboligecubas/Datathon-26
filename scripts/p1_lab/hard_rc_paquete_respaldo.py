"""Revisión del PAQUETE ENTREGADO, tercera parte: cuántas horas decide el plan con incertidumbre y cuántas el de
respaldo (plan_fixed, que sí aplica el tope "no descargar más de lo comprado la hora anterior"). NO se empaqueta.

    python scripts/p1_lab/hard_rc_paquete_respaldo.py <carpeta con agent.py del ZIP>
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hard_ataque_comun as c  # noqa: E402
import hard_rc_paquete_zip as z  # noqa: E402


def main() -> int:
    mod = z.cargar(Path(sys.argv[1]) / "agent.py", "agent_zip_resp")
    envmod = z.cargar(c.REPO / "oficial" / "starter_kit" / "environment.py", "env_oficial3")
    for nombre, sem, nov in (("sep+feb+jun", [0, 5, 9], "copia"), ("oct+nov(cero)+dic", [1, 2, 3], "cero")):
        full, _ = c.episodio_test(nov, semanas=sem)
        ag = mod.BatteryAgent()
        usados = []

        class Espia:
            def act(self, obs):
                a = ag.act(obs)
                usados.append(bool(getattr(ag.policy.netload, "scen_used", False)))
                return a
        r, a, ms, seen = z.correr(envmod, full, Espia())
        u = np.array(usados)
        resp = np.where(~u)[0]
        print(f"{nombre}: {len(full)} h | score {r['score']:.3f} | infracciones {r['infraccions']} | plan con incertidumbre {int(u.sum())} h, "
              f"respaldo {len(resp)} h | n_fallbacks (regla simple) {getattr(ag.policy, 'n_fallbacks', '?')} | elapsed_s {round(getattr(ag.policy, 'elapsed_s', -1), 2)} | "
              f"presupuesto {getattr(ag.policy, 'time_budget_s', '?')} | ms/paso {ms.mean():.1f} (máx {ms.max():.1f})")
        if len(resp):
            print("   horas de respaldo (t, fecha, SOC, acción):", [(int(t), str(seen[t]["timestamp"])[5:16], round(seen[t]["soc_kwh"]), round(float(a[t]))) for t in resp[:12]],
                  "..." if len(resp) > 12 else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
