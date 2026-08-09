"""Regenerate every figure. python -m python_stats.generate_all [n ...]"""

from __future__ import annotations

import sys
import time
import traceback

from . import FIGURES
from .charts import ALL


def run(numbers: list[int] | None = None) -> dict:
    todo = ALL if not numbers else [ALL[n - 1] for n in numbers]
    out = {}
    for fn in todo:
        n = int(fn.__name__.split("_")[1])
        t0 = time.perf_counter()
        try:
            path = fn()
            dt = time.perf_counter() - t0
            out[n] = {"ok": True, "path": str(path), "seconds": round(dt, 2)}
            print(f"[ok]   chart {n:2d}  {dt:6.2f}s  {path.name}")
        except Exception as exc:
            out[n] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            print(f"[FAIL] chart {n:2d}  {type(exc).__name__}: {exc}")
            traceback.print_exc()
    return out


if __name__ == "__main__":
    nums = [int(a) for a in sys.argv[1:]]
    res = run(nums or None)
    bad = [k for k, v in res.items() if not v["ok"]]
    print(f"\n{len(res) - len(bad)}/{len(res)} charts written to {FIGURES}")
    sys.exit(1 if bad else 0)
