// Problem statement page. Five sections in order. Palette only, no new styles.
import {
  BrazilianDiagram,
  CcpDiagram,
  CtDiagram,
  DentDiagram,
  SentDiagram,
  TpbDiagram,
} from "./Geometry";
import { Section } from "./ui";

export function Problem() {
  return (
    <Section
      title="Problem"
      eyebrow="Why this exists"
      lede="One shared baseline for four fracture methods."
    >
      <h2>Section 1: The Problem</h2>
      <div className="panel">
        <p>
          Fracture mechanics research typically implements one simulation method in isolation.
          This makes cross-method comparison on identical inputs impossible. Different methods
          make different assumptions about crack geometry, material behavior, and length scale,
          and there is no shared baseline to evaluate where they agree and diverge.
        </p>
      </div>

      <h2>Section 2: What Fractureverse Does</h2>
      <div className="panel">
        <p>
          Fractureverse puts four methods, peridynamics, XFEM, cohesive zone modeling,
          and phase-field fracture, on one shared material database. The same material inputs,
          geometry, and loading conditions are fed to all four methods simultaneously. This
          enables direct comparison of crack initiation location, branching angle,
          propagation path, and fatigue life prediction.
        </p>
      </div>
    </Section>
  );
}
