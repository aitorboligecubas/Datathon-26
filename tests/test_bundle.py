"""Owner: INTEGRADOR. El agent.py empaquetado solo usa imports permitidos y funciona aislado."""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_build_submission():
    out = subprocess.run([sys.executable, "scripts/build_submission.py"], cwd=REPO,
                         capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "prueba aislada OK" in out.stdout
