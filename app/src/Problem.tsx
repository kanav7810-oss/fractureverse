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

      <h2>Section 3: Geometry Diagrams</h2>
      <p className="muted">
        One labeled schematic per method. Panel, crack, loading arrows, and key dimensions.
      </p>
      <h3>Peridynamics</h3>
      <div className="hscroll">
        <SentDiagram />
        <DentDiagram />
        <CcpDiagram />
      </div>
      <h3>XFEM</h3>
      <div className="hscroll">
        <TpbDiagram />
        <BrazilianDiagram />
        <CtDiagram />
      </div>
      <h3>Cohesive zone</h3>
      <div className="hscroll">
        <SentDiagram />
        <CcpDiagram />
        <CtDiagram />
      </div>
      <h3>Phase-field</h3>
      <div className="hscroll">
        <DentDiagram />
        <TpbDiagram />
        <BrazilianDiagram />
      </div>

      <h2>Section 4: What Was Validated</h2>
      <div className="tablewrap panel">
        <table>
          <thead>
            <tr>
              <th>Method</th><th>Benchmark Case</th><th>Key Metric</th>
              <th className="num">Value</th><th>Reference</th><th className="num">Error</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Peridynamics</td><td>Pre-notched plate branching</td><td>Kink angle</td>
              <td className="num">18 percent</td><td>Analytical angle</td><td className="num">18 percent</td>
            </tr>
            <tr>
              <td>XFEM</td><td>0.1 by 0.2 m panel, 100 MPa</td><td>K_I opening fit</td>
              <td className="num">25.5 MPa sqrt(m)</td><td>Closed form 27.9</td><td className="num">8.6 percent</td>
            </tr>
            <tr>
              <td>PINN vs XFEM</td><td>Same panel</td><td>K_I PINN</td>
              <td className="num">26.9 MPa sqrt(m)</td><td>Integral 27.7</td><td className="num">2.89 percent</td>
            </tr>
            <tr>
              <td>PINN field</td><td>Same panel</td><td>Relative L2</td>
              <td className="num">2.37 percent</td><td>XFEM field</td><td className="num">2.37 percent</td>
            </tr>
            <tr>
              <td>LSTM</td><td>225 samples, 3 domains</td><td>RMSE</td>
              <td className="num">0.0277 decades</td><td>Held out split</td><td className="num">n/a</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p className="muted" style={{ fontSize: 12 }}>
        LSTM detail: R squared 0.99989, MAE 0.0227 decades.
        Per domain RMSE: aerospace 0.0228, biomedical 0.0254, civil 0.0338.
        PINN centre opening 13 percent low, enrichment carries least information at centre.
      </p>

      <h2>Section 5: Who This Is For</h2>
      <div className="panel">
        <p>
          This platform is built for researchers who want a shared computational baseline
          for fracture method comparison, and for students learning the differences between
          continuum and non-continuum fracture formulations.
        </p>
      </div>
    </Section>
  );
}
