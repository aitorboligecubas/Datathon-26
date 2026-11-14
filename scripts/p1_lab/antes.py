"""Referencia: el agente del primer envío (sin seguimiento de semanas sin datos)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from battery.policy import MPCPolicy  # noqa: E402


class Before(MPCPolicy):
    def track_block(self, obs):
        return False


class _Agent:
    def __init__(self):
        self.policy = Before()

    def act(self, obs):
        return self.policy.act(obs)


def make_agent():
    return _Agent()
