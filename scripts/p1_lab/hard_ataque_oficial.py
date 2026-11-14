"""Contraste del banco del HARD MODE con el simulador OFICIAL (oficial/starter_kit/environment.py). NO se empaqueta.

Owner: P1. El banco (scripts/p1_hard.py) usa nuestra copia de la física (battery.sim.apply_action). Aquí el
mismo episodio se pasa por la clase oficial CampusBatteryEnv con la batería del modo difícil (6.000 kWh,
1.500 kW, rendimiento 0,9), recortando la observación a 3 valores y añadiendo la meteo y la batería, que es lo
que anunció la organización. Si las infracciones y el score coinciden, el banco mide lo mismo que el oficial.

    python scripts/p1_lab/hard_ataque_oficial.py
"""
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hard_ataque_comun as c  # noqa: E402
from battery.hard import HardBatteryAgent  # noqa: E402
from battery.sim import to_env_frame  # noqa: E402

SPEC = {"capacity_kwh": 6000, "power_kw": 1500, "efficiency": 0.9, "soc_init": 0.5, "soc_min": 0.0,
        "soc_max": 1.0, "dt_hours": 1, "degradation": False}
METEO = ("irradiancia_wm2", "temp_ambient_c", "temp_panel_c", "vent_ms")


def main() -> int:
    path = c.REPO / "oficial" / "starter_kit" / "environment.py"
    spec = importlib.util.spec_from_file_location("env_oficial", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    full, _ = c.episodio_test("copia")

    class HardEnv(mod.CampusBatteryEnv):
        def _get_obs(self):
            obs = super()._get_obs()
            if obs is None:
                return None
            obs["preus_properes_24h"] = obs["preus_properes_24h"][:3]
            obs["co2_properes_24h"] = obs["co2_properes_24h"][:3]
            prev = self.t - 1 if self.t > 0 else self.t
            for k in METEO:
                obs["noves_dades_5min"][k] = float(full[k].iloc[prev])
            obs["cap_max_kwh"], obs["power_max_kw"] = self.cap, self.power
            return obs

    env = HardEnv(to_env_frame(full), spec=SPEC)
    agent = HardBatteryAgent()
    obs, done = env.reset(), False
    while not done:
        obs, done = env.step(agent.act(obs))
    res = env.evaluate_results()
    half = [i < len(full) // 2 for i in range(len(full))]
    pub = env.evaluate_results(mask=half)
    priv = env.evaluate_results(mask=[not m for m in half])
    ours = c.simular(HardBatteryAgent(), full)
    print(f"oficial : score {res['score']:.2f} | CO2 {res['co2_estalviat_pct']:.2f} % | coste {res['cost_estalviat_pct']:.2f} % | "
          f"infracciones {res['infraccions']} | mitad pública {pub['score']:.2f} | mitad privada {priv['score']:.2f}")
    print(f"banco   : score {ours['score']:.2f} | infracciones {ours['infr']}")
    print("COINCIDEN" if abs(res["score"] - ours["score"]) < 0.006 and res["infraccions"] == ours["infr"] else "NO COINCIDEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
