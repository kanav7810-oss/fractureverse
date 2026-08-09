// Features 6 and 7. XFEM crack path and the peridynamic damage map.
import { useEffect, useRef } from "react";
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { PeridynamicFixture, XfemFixture } from "./data";
import { fmt } from "./data";
import { CHART_AXIS, CHART_GRID, Loading, Note, Section, Stat, useFixture } from "./ui";

export function XfemView() {
  const x = useFixture<XfemFixture>("xfem.json");
  if (!x.data) return <Loading what="the XFEM results" />;

  const prop = x.data.propagation;
  const path = prop.path.map((p: number[], i: number) => ({
    x: p[0] * 1000, y: p[1] * 1000, step: i,
    K_I: prop.K_I[i], K_II: prop.K_II[i], theta: prop.theta_deg[i], a: prop.a[i] * 1000,
  }));
  const domains = Object.keys(x.data).filter((k) => k !== "propagation");

  return (
    <Section
      title="XFEM crack path"
      lede="Enriched elements let the crack cut through the mesh, so the path is an output rather than an input. The path below is the cached 30 degree mixed mode propagation, 12 steps, about 21 s of solver time recorded once in Part 2."
    >
      <h2>Path in the panel</h2>
      <div className="panel">
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={path} margin={{ top: 8, right: 18, bottom: 12, left: 4 }}>
            <CartesianGrid stroke={CHART_GRID} />
            <XAxis dataKey="x" type="number" domain={["dataMin - 2", "dataMax + 2"]}
              tick={CHART_AXIS} tickFormatter={(v) => fmt(v, 3)}
              label={{ value: "x in mm", fill: "#8f8d87", fontSize: 11, position: "insideBottom", offset: -6 }} />
            <YAxis dataKey="y" type="number" domain={["dataMin - 2", "dataMax + 2"]}
              tick={CHART_AXIS} tickFormatter={(v) => fmt(v, 3)}
              label={{ value: "y in mm", angle: -90, fill: "#8f8d87", fontSize: 11, position: "insideLeft" }} />
            <Tooltip contentStyle={{ background: "#14161c", border: "1px solid #262a33", fontSize: 12 }}
              formatter={(v: any) => fmt(Number(v), 4)} />
            <Line dataKey="y" stroke="#c96a3f" strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <h2>Stress intensity along the path</h2>
      <div className="panel">
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={path} margin={{ top: 8, right: 18, bottom: 12, left: 4 }}>
            <CartesianGrid stroke={CHART_GRID} />
            <XAxis dataKey="step" tick={CHART_AXIS}
              label={{ value: "propagation step", fill: "#8f8d87", fontSize: 11, position: "insideBottom", offset: -6 }} />
            <YAxis tick={CHART_AXIS} tickFormatter={(v) => fmt(v, 3)}
              label={{ value: "MPa sqrt(m) and degrees", angle: -90, fill: "#8f8d87", fontSize: 11, position: "insideLeft" }} />
            <Tooltip contentStyle={{ background: "#14161c", border: "1px solid #262a33", fontSize: 12 }}
              formatter={(v: any) => fmt(Number(v), 4)} />
            <Line dataKey="K_I" stroke="#9aa4ff" dot={false} strokeWidth={2} isAnimationActive={false} />
            <Line dataKey="K_II" stroke="#7fd1c0" dot={false} strokeWidth={2} isAnimationActive={false} />
            <Line dataKey="theta" stroke="#e8b04b" dot={false} strokeWidth={2} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
        <div className="legend" style={{ marginTop: 8 }}>
          <span><i className="swatch" style={{ background: "#9aa4ff" }} />K_I</span>
          <span><i className="swatch" style={{ background: "#7fd1c0" }} />K_II</span>
          <span><i className="swatch" style={{ background: "#e8b04b" }} />kink angle in degrees</span>
        </div>
      </div>

      <h2>Single step solve, one per domain</h2>
      <div className="hscroll">
        {domains.map((d) => {
          const r = x.data![d];
          return (
            <div key={d} className="panel domaincard">
              <h3>{d}</h3>
              <div className="grid cols2">
                <Stat k="K_I from XFEM" v={fmt(r.K_I)} u="MPa sqrt(m)" />
                <Stat k="K_I analytical" v={fmt(r.K_I_analytical)} u="MPa sqrt(m)" />
                <Stat k="K_II" v={fmt(r.K_II)} u="MPa sqrt(m)" />
                <Stat k="Kink angle" v={fmt(r.kink_angle_deg)} u="deg" />
              </div>
              <p className="muted" style={{ fontSize: 12, marginTop: 10 }}>
                The interaction integral only visits elements where grad q is non zero, and the domain
                independence spread is under 0.1 percent of K_I over r_d from 2 to 5 elements.
              </p>
            </div>
          );
        })}
      </div>
    </Section>
  );
}

function DamageCanvas({ data }: { data: PeridynamicFixture }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const [nx, ny] = data.damage_shape;
    const ctx = cv.getContext("2d")!;
    const img = ctx.createImageData(nx, ny);
    for (let i = 0; i < nx; i++) {
      for (let j = 0; j < ny; j++) {
        const d = data.damage[i * ny + j];
        const p = ((ny - 1 - j) * nx + i) * 4;
        // Same ink to jade to ember ramp as the 3D viewer uses.
        const u = d < 0.5 ? d * 2 : (d - 0.5) * 2;
        const a = d < 0.5 ? [16, 23, 28] : [85, 96, 214];
        const b = d < 0.5 ? [85, 96, 214] : [154, 164, 255];
        img.data[p] = Math.round(a[0] + (b[0] - a[0]) * u);
        img.data[p + 1] = Math.round(a[1] + (b[1] - a[1]) * u);
        img.data[p + 2] = Math.round(a[2] + (b[2] - a[2]) * u);
        img.data[p + 3] = 255;
      }
    }
    cv.width = nx;
    cv.height = ny;
    ctx.putImageData(img, 0, 0);
  }, [data]);
  return <canvas ref={ref} style={{ width: "100%", imageRendering: "pixelated", borderRadius: 8, border: "1px solid #262a33" }} />;
}

export function PeridynamicView() {
  const pd = useFixture<PeridynamicFixture>("peridynamic.json");
  if (!pd.data) return <Loading what="the peridynamic run" />;
  const s = pd.data.scalars as Record<string, any>;
  const e = pd.data.energy_check;

  return (
    <Section
      title="Peridynamic damage and branching"
      lede="Bonds break on their own, so nucleation and branching need no predefined path. The field below is the Part 1 concrete panel run, 5,000 nodes and 67,318 bonds, damage on a 100 by 50 grid."
    >
      <div className="panel">
        <DamageCanvas data={pd.data} />
        <div className="legend" style={{ marginTop: 10 }}>
          <span><i className="swatch" style={{ background: "rgb(16,23,28)" }} />intact</span>
          <span><i className="swatch" style={{ background: "rgb(85,96,214)" }} />partial</span>
          <span><i className="swatch" style={{ background: "rgb(154,164,255)" }} />fully broken</span>
          <span>panel 3.0 m by 1.5 m, notch tip at x = {fmt(s.notch_tip_x)} m</span>
        </div>
      </div>

      <h2>Run summary</h2>
      <div className="grid cols4">
        <Stat k="Applied stress" v={fmt(s.sigma_MPa)} u="MPa" />
        <Stat k="Horizon implied strength" v={fmt(s.pd_strength_MPa)} u="MPa" />
        <Stat k="Horizon delta" v={fmt(s.delta)} u="m" />
        <Stat k="Grid spacing dx" v={fmt(s.dx)} u="m" />
        <Stat k="Branch columns" v={s.n_branch_columns} />
        <Stat k="First branch at x" v={fmt(s.first_branch_x)} u="m" />
        <Stat k="Crack advance" v={fmt(s.crack_advance)} u="m" />
        <Stat k="Hillerborg length l_ch" v={fmt(s.l_ch)} u="m" />
      </div>

      <h2>Fracture energy check</h2>
      <div className="tablewrap panel">
        <table>
          <thead><tr><th>Quantity</th><th className="num">Value</th></tr></thead>
          <tbody>
            {Object.entries(e).map(([k, v]) => (
              <tr key={k}><td className="mono">{k}</td><td className="num">{fmt(v as number, 5)}</td></tr>
            ))}
          </tbody>
        </table>
      </div>

      <Note title="Finding 6.2">
        Effective tensile strength scales as one over the square root of the horizon, so the horizon
        implied strength of {fmt(s.pd_strength_MPa)} MPa is a property of the discretisation, not of the
        concrete. It is displayed next to the {fmt(s.sigma_MPa)} MPa driving stress everywhere the
        peridynamic result appears.
      </Note>
    </Section>
  );
}
