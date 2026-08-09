"""Physics informed neural network for the centre cracked panel.

CPU only. Artifacts land in pinn/artifacts.
"""

from pathlib import Path

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)

SEED = 1337
