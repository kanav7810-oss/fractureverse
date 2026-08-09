"""Machine learning stack for FRACTUREVERSE Part 2.

Everything here is seeded. Artifacts land in ml/artifacts so Part 4 can load
trained weights and a fixed test split instead of retraining.
"""

from pathlib import Path

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)

SEED = 1337
