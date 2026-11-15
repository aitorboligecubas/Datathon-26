"""Revisión "logica" (HARD MODE). NO se empaqueta. Comprueba a mano plan_scen (src/battery/hard.py) contra la
física de environment.py: signos, eficiencias, tramos con cuantiles de signo mixto y consumo neto > 1.500 kW.

    python scripts/p1_lab/hard_rev_logica_plan_scen.py
"""
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
from battery.hard import HARD_PARAMS as P, plan_scen  # noqa: E402
from battery.hard_solar import scen_probs  # noqa: E402

alphas = [0.1, 0.5, 0.9]
tail, head = scen_probs(alphas)
print("masa por nodo: tail", tail, "head", head)


def coste_esperado(a, nodes, w):
    """Compra esperada ponderada de una hora con la acción a (kW), con la distribución discreta de los nodos."""
    mass = np.array([0.3, 0.4, 0.3])
    return w * float((mass * np.maximum(np.asarray(nodes) + a, 0.0)).sum())


ok = True
# 1) Una hora, valor final 0: se descarga hasta el cuantil más alto (todo tramo ahorra algo).
a = plan_scen(3000.0, [[100.0, 200.0, 300.0]], tail, head, [1.0], 0.0, P)
print("1) descarga sin valor final:", a, "(esperado -300)"); ok &= abs(a[0] + 300) < 1e-6
# 2) Valor final entre los tramos: descargar el tramo i compensa si w·tail_i·eta_d > valor final.
#    tail = [1, .7, .3]; con valor final 0,5·eta_d se descargan los tramos 0 y 1 (hasta 200).
a = plan_scen(3000.0, [[100.0, 200.0, 300.0]], tail, head, [1.0], 0.5 * P.eta_discharge, P)
print("2) descarga con valor final 0,5·eta_d:", a, "(esperado -200)"); ok &= abs(a[0] + 200) < 1e-6
# 3) Signo mixto: nodos -200, 0, 300. Cargar hasta 200 cuesta w·head (0, .3, .7, 1): con valor final 0,5/eta_c
#    se cargan los tramos de coste < 0,5: de 0 a 0 (gratis, ancho 0), de 0 a 0 (ancho 0) y de 0 a 200 con head = .7?
neg_nodes = [[-200.0, 0.0, 300.0]]
a = plan_scen(3000.0, neg_nodes, tail, head, [1.0], 0.5 / P.eta_charge, P)
grid = np.linspace(-400, 400, 801)
best = grid[np.argmin([coste_esperado(x, neg_nodes[0], 1.0) - 0.5 / P.eta_charge * (P.eta_charge * max(x, 0) + min(x, 0) / P.eta_discharge) for x in grid])]
print("3) signo mixto:", a, "óptimo por fuerza bruta:", best); ok &= abs(a[0] - best) < 1.0 + 1e-6
# 4) Consumo neto por encima de la potencia: la descarga se queda en 1.500 kW.
a = plan_scen(3000.0, [[1400.0, 1600.0, 1800.0]], tail, head, [1.0], 0.0, P)
print("4) consumo neto > potencia:", a, "(esperado -1500)"); ok &= abs(a[0] + 1500) < 1e-6
# 5) Dos horas: mover energía solo si w_B·eta_c·eta_d > w_A (regla del 11 %), con consumo cierto.
n2 = [[500.0] * 3, [500.0] * 3]
a = plan_scen(0.0, n2, tail, head, [1.0, 1.10], 0.0, P); b = plan_scen(0.0, n2, tail, head, [1.0, 1.12], 0.0, P)
print("5) regla del 11 %: con 1,10 ->", a, "| con 1,12 ->", b); ok &= abs(a[0]) < 1e-6 and b[0] > 1.0
# 6) Fuerza bruta de una hora con valor final, descarga y carga, en una malla de valores finales.
for tv in (0.2, 0.6, 0.9, 1.2):
    for nodes in ([100.0, 400.0, 900.0], [-600.0, -100.0, 250.0], [-900.0, -500.0, -100.0]):
        a = plan_scen(3000.0, [nodes], tail, head, [1.0], tv, P)[0]
        obj = [coste_esperado(x, nodes, 1.0) - tv * (P.eta_charge * max(x, 0) + min(x, 0) / P.eta_discharge) for x in grid * 3.75]
        fa = coste_esperado(a, nodes, 1.0) - tv * (P.eta_charge * max(a, 0) + min(a, 0) / P.eta_discharge)
        if fa > min(obj) + 1e-6:
            ok = False
            print("   NO ÓPTIMO", tv, nodes, a, fa, min(obj))
print("TODO BIEN" if ok else "HAY DIFERENCIAS")
