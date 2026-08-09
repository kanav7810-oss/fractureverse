"""Publication figures for FRACTUREVERSE Part 2.

17 charts, 300 dpi PNG, 12 pt axis labels, legend on every multi series chart.
Outputs land in python_stats/figures. Expensive physics runs are cached under
python_stats/cache so regenerating a figure does not re run a solver.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIGURES = ROOT / "figures"
CACHE = ROOT / "cache"
FIGURES.mkdir(exist_ok=True)
CACHE.mkdir(exist_ok=True)

RESEARCH = ROOT.parent / "research"
