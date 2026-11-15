"""Revisión del PAQUETE ENTREGADO, cuarta parte: ¿crece el tiempo por paso a lo largo del episodio? NO se empaqueta.

    python scripts/p1_lab/hard_rc_paquete_tiempo.py <carpeta con agent.py del ZIP>
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hard_ataque_comun as c  # noqa: E402
import hard_rc_paquete_zip as z  # noqa: E402


def main() -> int:
    mod = z.cargar(Path(sys.argv[1]) / "agent.py", "agent_zip_t")
    envmod = z.cargar(c.REPO / "oficial" / "starter_kit" / "environment.py", "env_oficial4")
    full, _ = c.episodio_test("copia", semanas=[0, 3, 5, 7, 9, 11])
    r, a, ms, seen = z.correr(envmod, full, mod.BatteryAgent())
    tramos = [ms[i:i + 168].mean() for i in range(0, len(ms), 168)]
    print(f"{len(full)} h (sep, dic, feb, abr, jun, ago): score {r['score']:.3f} | infracciones {r['infraccions']} | ms/paso por semana {[round(float(t), 2) for t in tramos]} | "
          f"total {ms.sum() / 1000:.1f} s | proyección a 2.016 pasos {ms.mean() * 2.016:.1f} s | máx {ms.max():.1f} ms | pasos de más de 20 ms: {int((ms > 20).sum())}")
    print(f"acciones fuera de [-1500, 1500]: {int((np.abs(a) > 1500).sum())} | no finitas: {int((~np.isfinite(a)).sum())} | SOC mín/máx observado {min(o['soc_kwh'] for o in seen):.1f} / {max(o['soc_kwh'] for o in seen):.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
