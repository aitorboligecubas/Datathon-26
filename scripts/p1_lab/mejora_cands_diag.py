"""Descomposición del hueco de consumo y solar (para mejora_grid.py)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mejora_diag as d
from mejora_cands import v9

CANDS = {"base": v9, "hora actual exacta": d.perfect_now, "horas siguientes exactas": d.perfect_future,
         "todo exacto": d.perfect_netload}
