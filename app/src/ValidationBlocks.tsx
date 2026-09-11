// Explicit validation blocks. Numbers match the spec, plain text, sup tags only.
import { Stat } from "./ui";

export function XfemValidation() {
  return (
    <div className="panel" style={{ marginTop: 14 }}>
      <h3>Validation</h3>
      <p className="muted" style={{ fontSize: 13 }}>
        Benchmark case: panel 0.1 by 0.2 m under 100 MPa applied stress.
        Geometry: center cracked panel.
        Inputs: 100 MPa stress, opening fit for K.
        Output: K_I 25.5 MPa sqrt(m) from opening fit.
        Reference: closed form K_I 27.9 MPa sqrt(m). Error 8.6 percent.
      </p>
      <div className="grid cols4">
        <Stat k="K_I measured" v="25.5" u="MPa sqrt(m)" />
        <Stat k="K_I reference" v="27.9" u="MPa sqrt(m)" />
        <Stat k="Error" v="8.6" u="percent" />
        <Stat k="Stress" v="100" u="MPa" />
      </div>
    </div>
  );
}

export function PeridynamicsValidation() {
  return (
    <div className="panel" style={{ marginTop: 14 }}>
      <h3>Validation</h3>
      <p className="muted" style={{ fontSize: 13 }}>
        Benchmark case: pre-notched plate under tension with branching.
        Geometry: concrete panel run from Part 1.
        Inputs: 15.5 mm horizon, 11,400 bonds, 5,400 elements.
        Output: kink angle with 18 percent error before tuning.
        Reference: analytical branching angle.
      </p>
      <div className="grid cols4">
        <Stat k="Horizon" v="15.5" u="mm" />
        <Stat k="Bonds" v="11,400" />
        <Stat k="Elements" v="5,400" />
        <Stat k="Kink error" v="18" u="percent" />
      </div>
    </div>
  );
}
