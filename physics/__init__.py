"""FRACTUREVERSE physics package.

Four fracture theories over three engineering domains:
  lefm         Linear elastic fracture mechanics, Paris and Walker crack growth.
  epfm         Elastic plastic fracture mechanics, J integral, J-R curve, CTOD.
  xfem         Extended finite element method with Heaviside and branch enrichment.
  peridynamic  Bond based peridynamics with bond breaking and damage field.

Support modules:
  mesh            Structured quadrilateral mesh with optional crack tip grading.
  materials       Loader for the three domain material databases in data/.
  unified_solver  Routes (domain, material, theory) to the right implementation.
"""

__all__ = [
    "lefm",
    "epfm",
    "xfem",
    "peridynamic",
    "mesh",
    "materials",
    "unified_solver",
]
