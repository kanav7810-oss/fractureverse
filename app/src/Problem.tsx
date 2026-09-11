// Problem statement page. Five sections in order. Palette only, no new styles.
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
    </Section>
  );
}
