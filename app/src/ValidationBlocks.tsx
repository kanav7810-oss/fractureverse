// Explicit validation blocks. Numbers match the spec, plain text, sup tags only.
import { Note, Stat } from "./ui";

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
