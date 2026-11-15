import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mejora_diag as d
import mejora_cands as mc
CANDS = {"base": mc.v12, "precio real 24h": d.perfect_price, "CO2 real 24h": d.perfect_co2, "ambos reales": d.perfect_market}
