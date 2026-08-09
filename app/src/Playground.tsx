// Features 3 and 4. Solver playground, plus the growth curve and the anchored versus
// specified Paris coefficient comparison.
//
// Two paths, and the badge on screen says which one is running. In live mode every
// selector change posts to /api/solve and the numbers come from a fresh solver, the
// growth history included, so any geometry and any growth law is available and
// sweep.json is never fetched. In offline mode the precomputed grid answers instead,
// which only covers this fixed set of stresses and initial crack lengths, and growth
// histories only exist for the center cracked panel under Paris.
import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { Capabilities, Curves, PredictResult, SolveResult, Sweep, SweepRecord } from "./data";
import { apiPredict, apiSolve, fmt } from "./data";
import { CHART_AXIS, CHART_GRID, Loading, Note, Section, Select, Slider, Stat, useFixture, useMode } from "./ui";

// The grid axes. Identical in both modes so the two paths are comparable.
const SIGMAS = [40, 60, 80, 100, 125, 150, 180, 220, 260];
const A0S = [0.5, 1.0, 2.0, 4.0, 8.0];

const key = (r: { domain: string; material: string; geometry: string; law: string; sigma_MPa: number; a0_mm: number }) =>
  `${r.domain}|${r.material}|${r.geometry}|${r.law}|${r.sigma_MPa}|${r.a0_mm}`;

type View = {
  K_I: number; K_IC: number; K_ratio: number; G: number; delta_K: number; da_dN: number;
  a_c: number; N_f: number; years_to_failure: number; plastic_zone: number;
  ssy_valid: boolean;
  J_elastic?: number; J_elastic_plastic?: number; J_ratio?: number;
  ctod?: number; ctod_critical?: number;
};

const fromRecord = (r: SweepRecord): View => r;
const fromSolve = (r: SolveResult): View => r;

// The mode probe has to settle before any hook below runs, otherwise the offline path
// would fire a 1.9 MB sweep.json fetch that live mode never wants.
export function Playground({ caps }: { caps: Capabilities }) {
  const resolved = useMode();
  if (!resolved) return <Loading what="the data source" />;
  return <PlaygroundBody caps={caps} live={resolved === "live"} />;
}

function PlaygroundBody({ caps, live }: { caps: Capabilities; live: boolean }) {
  const curves = useFixture<Curves>(live ? undefined : "curves.json");
  const anchored = useFixture<any[]>("anchored.json");

  const [domain, setDomain] = useState("aerospace");
  const [material, setMaterial] = useState(caps.domains.aerospace.materials[0]);
  const [geometry, setGeometry] = useState("center");
  const [law, setLaw] = useState("paris");
  const [theory, setTheory] = useState("lefm");
  const [si, setSi] = useState(5);
  const [ai, setAi] = useState(1);

  const materials = caps.domains[domain].materials;
  const mat = materials.includes(material) ? material : materials[0];
  const sigma = SIGMAS[si];
  const a0 = A0S[ai];

  // Live path.
  const [solved, setSolved] = useState<SolveResult | undefined>(undefined);
  const [solveErr, setSolveErr] = useState<string | undefined>(undefined);
  const [pred, setPred] = useState<PredictResult | undefined>(undefined);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!live) return;
    let current = true;
    setBusy(true);
    setSolveErr(undefined);
    const body = {
      domain, material: mat, theory: "lefm", growth_law: law,
      load: { sigma_max: sigma * 1e6, R: 0.1 },
      crack: { a0: a0 / 1000, geometry, W: 0.1 },
    };
    // The elastic plastic solve returns J and CTOD but no growth history, because a
    // life needs the Paris integration that lives in the linear elastic path. The Part
    // 3 grid merged the two for the same point and so does this, with two calls.
    Promise.all([apiSolve(body),
                 theory === "epfm" ? apiSolve({ ...body, theory: "epfm" }) : undefined])
      .then(([base, ep]) => current && (setSolved({ ...base, ...(ep ?? {}) }), setSolveErr(undefined)))
      .catch((e) => current && (setSolved(undefined), setSolveErr(String(e.message || e))))
      .finally(() => current && setBusy(false));
    apiPredict({ domain, material: mat, a0: a0 / 1000, sigma_max: sigma * 1e6, R: 0.1, W: 0.1, geometry, law })
      .then((p) => current && setPred(p))
      .catch(() => current && setPred(undefined));
    return () => {
      current = false;
    };
  }, [live, domain, mat, theory, law, geometry, sigma, a0]);

  // Offline path.
  const sweep = useFixture<Sweep>(live ? undefined : "sweep.json");
  const index = useMemo(() => {
    const m = new Map<string, SweepRecord>();
    sweep.data?.records.forEach((r) => m.set(key(r), r));
    return m;
  }, [sweep.data]);

  const record = live
    ? undefined
    : index.get(key({ domain, material: mat, geometry, law, sigma_MPa: sigma, a0_mm: a0 }));

  if (!live && sweep.error) return <div className="loading">{sweep.error}</div>;
  if (!live && !sweep.data) return <Loading what="the solver grid" />;

  const rec: View | undefined = live
    ? solved && fromSolve(solved)
    : record && fromRecord(record);

  const curve = live
    ? solved?.history && { a: solved.history.a, N: solved.history.N }
    : record && curves.data
    ? curves.data[record.id]
    : undefined;
  const curveData = curve ? curve.N.map((n, i) => ({ N: n, a: curve.a[i] * 1000 })) : [];

  return (
    <Section
      title="Solver playground"
      lede="Every selector below is built from capabilities(), nothing about the physics is hardcoded in the frontend."
    >
      <div className="panel">
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 12 }}>
          <span className={`badge ${live ? "good" : "warn"}`} data-testid="solver-mode">
            {live ? "live backend, every result is a fresh solve" : "offline fixtures, results come from the precomputed grid"}
          </span>
          {live && <span className="badge">{busy ? "solving" : "ready"}</span>}
        </div>
        <div className="controls">
          <Select label="Domain" value={domain} options={Object.keys(caps.domains)}
            onChange={(d) => { setDomain(d); setMaterial(caps.domains[d].materials[0]); }} />
          <Select label="Material" value={mat} options={materials} onChange={setMaterial} />
          <Select label="Geometry" value={geometry} options={caps.geometries}
            labels={caps.geometry_labels} onChange={setGeometry} />
          <Select label="Growth law" value={law} options={caps.growth_laws} onChange={setLaw} />
          {live && (
            <Select label="Theory" value={theory} options={["lefm", "epfm"]}
              labels={{ lefm: "Linear elastic", epfm: "Elastic plastic" }} onChange={setTheory} />
          )}
          <Slider label="Peak stress" values={SIGMAS} index={si} unit="MPa" onChange={setSi} />
          <Slider label="Initial crack a0" values={A0S} index={ai} unit="mm" onChange={setAi} />
        </div>
      </div>

      {!rec ? (
        <div className="panel" style={{ marginTop: 14 }} data-testid="no-solution">
          <p style={{ margin: 0 }}>
            {solveErr ??
              "No solution at this combination. geometry_factor rejects this a over W ratio, so the grid has no entry rather than an extrapolated one. Center and through are valid below 0.5, compact only between 0.2 and 0.8."}
          </p>
        </div>
      ) : (
        <>
          <h2>Linear elastic result</h2>
          <div className="grid cols4" data-testid="solver-stats">
            <Stat k="K_I" v={fmt(rec.K_I)} u="MPa sqrt(m)" />
            <Stat k="K_I over K_IC" v={fmt(rec.K_ratio)} hint={`K_IC = ${rec.K_IC} MPa sqrt(m)`} />
            <Stat k="Critical crack a_c" v={fmt(rec.a_c * 1000)} u="mm" />
            <Stat k="Energy release rate G" v={fmt(rec.G)} u="J per m2" />
            <Stat k="delta K" v={fmt(rec.delta_K)} u="MPa sqrt(m)" />
            <Stat k="da over dN" v={fmt(rec.da_dN)} u="m per cycle" />
            <Stat k="Cycles to failure" v={fmt(rec.N_f, 4)} u="cycles" />
            <Stat k="Service life" v={fmt(rec.years_to_failure)} u="years"
              hint={`${caps.domains[domain].cycle_frequency_per_year} cycles per year`} />
          </div>

          <div style={{ marginTop: 12, display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
            <span className={`badge ${rec.ssy_valid ? "good" : "warn"}`}>
              {rec.ssy_valid ? "Small scale yielding holds" : "Small scale yielding violated, read J not K"}
            </span>
            <span className="badge">plastic zone {fmt(rec.plastic_zone * 1000)} mm</span>
            <span className="badge">life from the specified Paris C, not the anchored one</span>
          </div>

          {rec.J_elastic_plastic !== undefined && (
            <>
              <h2>Elastic plastic result at the same point</h2>
              <div className="grid cols4">
                <Stat k="J elastic" v={fmt(rec.J_elastic)} u="J per m2" />
                <Stat k="J elastic plastic" v={fmt(rec.J_elastic_plastic)} u="J per m2" />
                <Stat k="J over J_IC" v={fmt(rec.J_ratio)} />
                <Stat k="CTOD" v={fmt((rec.ctod ?? 0) * 1e6)} u="micron"
                  hint={`critical CTOD ${fmt((rec.ctod_critical ?? 0) * 1e6)} micron`} />
              </div>
            </>
          )}
        </>
      )}

      {live && pred && (
        <>
          <h2>What the LSTM says about the same crack</h2>
          <div className="grid cols4" data-testid="predict-stats">
            <Stat k="Life, LSTM" v={fmt(pred.N_f_predicted, 4)} u="cycles"
              hint="from the first 20 observed samples only" />
            <Stat k="Life, closed form" v={fmt(pred.N_f_closed_form, 4)} u="cycles" />
            <Stat k="Life ratio error" v={fmt(pred.life_ratio_error * 100, 3)} u="percent" />
            <Stat k="log10 life" v={fmt(pred.log10_N_f, 5)} />
          </div>
          <p className="muted" style={{ fontSize: 12 }}>{pred.note}</p>
        </>
      )}

      <h2>Crack growth history</h2>
      {curveData.length ? (
        <div className="panel" data-testid="growth-chart">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={curveData} margin={{ top: 8, right: 18, bottom: 8, left: 4 }}>
              <CartesianGrid stroke={CHART_GRID} />
              <XAxis dataKey="N" type="number" scale="log" domain={["auto", "auto"]}
                tick={CHART_AXIS} tickFormatter={(v) => fmt(v, 2)}
                label={{ value: "cycles N", fill: "#8f8d87", fontSize: 11, position: "insideBottom", offset: -4 }} />
              <YAxis tick={CHART_AXIS} tickFormatter={(v) => fmt(v, 2)}
                label={{ value: "a in mm", angle: -90, fill: "#8f8d87", fontSize: 11, position: "insideLeft" }} />
              <Tooltip contentStyle={{ background: "#14161c", border: "1px solid #262a33", fontSize: 12 }}
                formatter={(v: any) => fmt(Number(v), 4)} />
              <Line type="monotone" dataKey="a" stroke="#9aa4ff" dot={false} strokeWidth={2} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="muted">
          Offline mode stores growth histories for the center cracked panel under the Paris law
          only. Switch geometry to center and the law to paris, or start the backend, which
          returns the history for every combination it can solve.
        </p>
      )}

      <h2>Which Paris coefficient produced that life</h2>
      <Note title="Finding 6.1, carried from Part 1">
        The specified coefficient for 2024-T3 predicts about 5.7 times the commonly cited growth rate
        at the same slope, so lives computed with it are conservative. Both are shown. Every life on
        this page uses the specified value.
      </Note>
      <div className="tablewrap panel" style={{ marginTop: 12 }}>
        {anchored.data ? (
          <table>
            <thead>
              <tr>
                <th>Domain</th><th>Material</th><th className="num">Paris C specified</th>
                <th className="num">N_f specified</th><th className="num">Paris C anchored</th>
                <th className="num">N_f anchored</th><th className="num">Ratio</th>
              </tr>
            </thead>
            <tbody>
              {anchored.data.map((r) => (
                <tr key={r.domain + r.material}>
                  <td>{r.domain}</td>
                  <td>{r.material}</td>
                  <td className="num">{fmt(r.paris_C)}</td>
                  <td className="num">{fmt(r.N_f_specified, 4)}</td>
                  <td className="num">{r.paris_C_anchored ? fmt(r.paris_C_anchored) : "n/a"}</td>
                  <td className="num">{r.N_f_anchored ? fmt(r.N_f_anchored, 4) : "n/a"}</td>
                  <td className="num">{r.ratio ? fmt(r.ratio) : "n/a"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Loading what="the anchored comparison" />
        )}
      </div>
    </Section>
  );
}
