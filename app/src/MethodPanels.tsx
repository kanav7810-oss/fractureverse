// Cohesive zone and phase-field panels. Same selectors, same palette, no new styles.
// Text uses plain hyphens only. No em dashes in this file by project rule.
import { GeometryStrip } from "./Geometry";
import { Section } from "./ui";

export function PhaseFieldView() {
  return (
    <Section
      title="Phase-field fracture"
      lede="Diffuse crack representation with a length scale input. Geometry selects the panel, loading matches the shared database."
    >
      <h2>Geometry configurations</h2>
      <GeometryStrip keys={["sent", "dent", "ccp", "tpb", "brazilian", "ct"]} />
      <div className="panel" style={{ marginTop: 14 }}>
        <h3>Validation</h3>
        <p className="muted" style={{ fontSize: 13 }}>
          Benchmark case: shared panel set with the same material inputs as XFEM and
          peridynamics. Output: propagation path and fatigue life per geometry.
          Reference: handbook geometry factors through the shared LEFM baseline.
        </p>
      </div>
    </Section>
  );
}

export function CohesiveView() {
  return (
    <Section
      title="Cohesive zone modeling"
      lede="Traction separation law on a predefined interface path. Geometry selects the panel, loading matches the shared database."
    >
      <h2>Geometry configurations</h2>
      <GeometryStrip keys={["sent", "dent", "ccp", "tpb", "brazilian", "ct"]} />
      <div className="panel" style={{ marginTop: 14 }}>
        <h3>Validation</h3>
        <p className="muted" style={{ fontSize: 13 }}>
          Benchmark case: shared panel set with the same material inputs as XFEM and
          peridynamics. Output: initiation location and propagation path per geometry.
          Reference: handbook geometry factors through the shared LEFM baseline.
        </p>
      </div>
    </Section>
  );
}
