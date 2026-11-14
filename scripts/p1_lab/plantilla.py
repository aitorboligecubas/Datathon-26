"""Plantilla de candidato para scripts/p1_banco.py. Copia este fichero como cand_<nombre>.py.

Un candidato es un fichero que define `make_agent()` y devuelve un objeto con `act(obs) -> float`
(la interfaz oficial). Lo normal es heredar de MPCPolicy y cambiar una pieza. Piezas que se pueden
sobrescribir (ver src/battery/policy.py):

    track_block(obs) -> bool            seguimiento de semanas del test y de semanas sin datos
    note_weight(obs)                    historial de valles diarios (para el precio de reserva)
    reserve_weight(days_left) -> float  precio de reserva para cargar en una semana sin datos
    no_data_view(obs, H, load, pv, terminal) -> (load, pv, terminal)
    terminal_value(obs, H) -> float     valor de la carga al final del horizonte
    cap_discharge(action_kw, obs)       tope de descarga por la última lectura
    plan_action(obs) / act_obs(obs)     el paso completo
    self.forecaster                     objeto con update(obs) y forecast(obs, h) -> (load, pv)
    self.w_co2, self.w_cost             pesos del LP

Reglas para que el candidato se pueda llevar luego a src/battery/ (se empaqueta en agent.py):
    - solo numpy, pandas, scipy, math, collections, datetime, json, pathlib, typing (y el propio paquete);
    - nada de ficheros, red, ni llamadas a `.stack()`, `eval`, `exec`, `globals`, `locals`, `vars`;
    - determinista, menos de 5 ms por paso, y nunca lanzar una excepción hacia fuera;
    - no usar nada que dependa de qué mitad del test es pública o privada, ni fechas "a medida".
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from battery.policy import MPCPolicy  # noqa: E402


class Candidate(MPCPolicy):
    """Cambia aquí lo que quieras probar."""

    def reserve_weight(self, days_left: int) -> float:
        return super().reserve_weight(days_left)


class _Agent:
    def __init__(self):
        self.policy = Candidate()

    def act(self, obs):
        return self.policy.act(obs)


def make_agent():
    return _Agent()
