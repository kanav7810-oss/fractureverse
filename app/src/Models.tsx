// Features 8 to 11. Model leaderboard, SHAP attribution, parity explorer, PINN against XFEM.
import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Scatter,
  ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";
import type { MlFixture, PinnFixture } from "./data";
import { fmt, fromLogLife } from "./data";
import { CHART_AXIS, CHART_GRID, DOMAIN_COLOR, Loading, Note, Section, Stat, useFixture } from "./ui";

const MODEL_LABEL: Record<string, string> = {
  lstm: "LSTM, two layers",
  xgboost_field: "XGBoost, field features",
  ridge: "Ridge, field features",
  paris_closed_form: "Closed form Paris, frozen F",
};

export function Leaderboard() {
  const ml = useFixture<MlFixture>("ml.json");
  const [split, setSplit] = useState<"train" | "val" | "test">("test");
  if (!ml.data) return <Loading what="the model report" />;
  const models = ml.data.report.models as Record<string, any>;
  const rows = Object.entries(models);

  return (
    <Section
      title="Prognostic model leaderboard"
      lede="Target is log10 of the cycles to failure over a 20 step observation window. The frontend converts with 10 to the power of the prediction before showing a life."
    >
      <div className="panel">
        <label className="field" style={{ maxWidth: 220 }}>
          Split
          <select value={split} onChange={(e) => setSplit(e.target.value as any)}>
            <option value="train">train, {ml.data.report.split_sizes.train} trajectories</option>
            <option value="val">val, {ml.data.report.split_sizes.val}</option>
            <option value="test">test, {ml.data.report.split_sizes.test}</option>
          </select>
        </label>
      </div>

      <div className="tablewrap panel" style={{ marginTop: 14 }}>
        <table>
          <thead>
            <tr>
              <th>Model</th>
              <th className="num">R squared</th>
              <th className="num">RMSE, decades</th>
              <th className="num">MAE, decades</th>
              <th className="num">Median life ratio error</th>
              <th className="num">Train seconds</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([k, v]) => (
              <tr key={k}>
                <td>{MODEL_LABEL[k] ?? k}</td>
                <td className="num">{fmt(v[split].r2, 5)}</td>
                <td className="num">{fmt(v[split].rmse, 3)}</td>
                <td className="num">{fmt(v[split].mae, 3)}</td>
                <td className="num">{fmt(v[split].median_life_ratio_error, 3)}</td>
                <td className="num">{v.wall_clock_s ? fmt(v.wall_clock_s, 4) : "closed form"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Note title="Finding 6.3, read this before quoting the R squared">
        Paris Law is a power law, so log life is close to linear in the log features and even ridge
        regression scores about 0.9998. R squared is not the discriminating metric here. Two things
        were done rather than hidden. The Paris coefficients, a_c and the a0 over a_c ratio were
        removed from the feature vector, otherwise the target is a closed form function of the inputs
        and the task is arithmetic. Inspection noise was added to the observed window, 0.02 decades on
        crack length and delta K, 0.08 decades on growth rate. Compare RMSE in decades of life, where
        the LSTM wins at 0.0277 against 0.0336 for ridge.
      </Note>

      <h2>Per domain, LSTM</h2>
      <div className="grid cols3">
        {Object.entries(models.lstm[split].per_domain as Record<string, any>).map(([d, v]) => (
          <div key={d} className="panel">
            <h3 style={{ color: DOMAIN_COLOR[d] }}>{d}</h3>
            <div className="grid cols2">
              <Stat k="R squared" v={fmt(v.r2, 5)} />
              <Stat k="RMSE" v={fmt(v.rmse, 3)} u="decades" />
              <Stat k="MAE" v={fmt(v.mae, 3)} u="decades" />
              <Stat k="Life ratio error" v={fmt(v.median_life_ratio_error, 3)} />
            </div>
          </div>
        ))}
      </div>

      <h2>LSTM training history</h2>
      <div className="panel">
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={ml.data.lstm_history.epoch.map((e, i) => ({
            epoch: e,
            train_loss: ml.data!.lstm_history.train_loss[i],
            val_rmse: ml.data!.lstm_history.val_rmse[i],
          }))} margin={{ top: 8, right: 18, bottom: 12, left: 4 }}>
            <CartesianGrid stroke={CHART_GRID} />
            <XAxis dataKey="epoch" tick={CHART_AXIS}
              label={{ value: "epoch", fill: "#8f8d87", fontSize: 11, position: "insideBottom", offset: -6 }} />
            <YAxis scale="log" domain={["auto", "auto"]} tick={CHART_AXIS} tickFormatter={(v) => fmt(v, 2)} />
            <Tooltip contentStyle={{ background: "#14161c", border: "1px solid #262a33", fontSize: 12 }}
              formatter={(v: any) => fmt(Number(v), 4)} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line dataKey="train_loss" stroke="#9aa4ff" dot={false} isAnimationActive={false} />
            <Line dataKey="val_rmse" stroke="#c96a3f" dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Section>
  );
}

export function ShapView() {
  const ml = useFixture<MlFixture>("ml.json");
  if (!ml.data) return <Loading what="the SHAP summary" />;
  const { features, mean_abs_shap, base_value } = ml.data.shap;
  const data = features
    .map((f, i) => ({ feature: f, value: mean_abs_shap[i] }))
    .sort((a, b) => b.value - a.value);

  return (
    <Section
      title="Feature attribution"
      lede="Mean absolute SHAP value per feature for the XGBoost model on the field feature set. The leaky features are absent by construction, which is asserted by validate_part2.py check 7."
    >
      <div className="panel">
        <ResponsiveContainer width="100%" height={Math.max(260, data.length * 26)}>
          <BarChart data={data} layout="vertical" margin={{ top: 8, right: 24, bottom: 8, left: 110 }}>
            <CartesianGrid stroke={CHART_GRID} />
            <XAxis type="number" tick={CHART_AXIS} tickFormatter={(v) => fmt(v, 2)}
              label={{ value: "mean absolute SHAP, decades of life", fill: "#8f8d87", fontSize: 11, position: "insideBottom", offset: -4 }} />
            <YAxis type="category" dataKey="feature" tick={{ ...CHART_AXIS, fontSize: 11 }} width={106} />
            <Tooltip contentStyle={{ background: "#14161c", border: "1px solid #262a33", fontSize: 12 }}
              formatter={(v: any) => fmt(Number(v), 4)} />
            <Bar dataKey="value" fill="#9aa4ff" isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="muted">
        Base value {fmt(base_value, 4)} decades, which is the mean predicted log10 life over the
        background sample, that is about {fmt(fromLogLife(base_value), 4)} cycles.
      </p>
      <h2>Features dropped on purpose</h2>
      <div className="hscroll">
        {(ml.data.report.feature_sets.leaky_dropped as string[]).map((f) => (
          <span key={f} className="badge warn">{f}</span>
        ))}
      </div>
    </Section>
  );
}

export function Parity() {
  const ml = useFixture<MlFixture>("ml.json");
  const [model, setModel] = useState("lstm");
  if (!ml.data) return <Loading what="the held out predictions" />;
  const { y, domain, models } = ml.data.parity;
  const pred = models[model];
  const points = y.map((t, i) => ({ truth: t, pred: pred[i], domain: domain[i] }));
  const lo = Math.min(...y) - 0.1;
  const hi = Math.max(...y) + 0.1;

  return (
    <Section
      title="Held out parity explorer"
      lede="225 test trajectories, predicted against true log10 life. Points on the diagonal are exact. Hover any point to read the life in cycles."
    >
      <div className="panel">
        <label className="field" style={{ maxWidth: 260 }}>
          Model
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            {Object.keys(models).map((m) => (
              <option key={m} value={m}>{MODEL_LABEL[m] ?? m}</option>
            ))}
          </select>
        </label>
        <ResponsiveContainer width="100%" height={420}>
          <ScatterChart margin={{ top: 12, right: 18, bottom: 16, left: 4 }}>
            <CartesianGrid stroke={CHART_GRID} />
            <XAxis type="number" dataKey="truth" domain={[lo, hi]} tick={CHART_AXIS}
              tickFormatter={(v) => fmt(v, 3)}
              label={{ value: "true log10 N_f", fill: "#8f8d87", fontSize: 11, position: "insideBottom", offset: -8 }} />
            <YAxis type="number" dataKey="pred" domain={[lo, hi]} tick={CHART_AXIS}
              tickFormatter={(v) => fmt(v, 3)}
              label={{ value: "predicted log10 N_f", angle: -90, fill: "#8f8d87", fontSize: 11, position: "insideLeft" }} />
            <ZAxis range={[26, 26]} />
            <Tooltip
              contentStyle={{ background: "#14161c", border: "1px solid #262a33", fontSize: 12 }}
              formatter={(v: any, n: any) => [`${fmt(Number(v), 5)} decades, ${fmt(fromLogLife(Number(v)), 4)} cycles`, n]} />
            <Scatter data={points} isAnimationActive={false}>
              {points.map((p, i) => (
                <Cell key={i} fill={DOMAIN_COLOR[p.domain] ?? "#8f8d87"} fillOpacity={0.75} />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
        <div className="legend">
          {Object.entries(DOMAIN_COLOR).map(([d, c]) => (
            <span key={d}><i className="swatch" style={{ background: c }} />{d}</span>
          ))}
          <span>same fixed split as every reported score, split.json is a fixture</span>
        </div>
      </div>
    </Section>
  );
}

export function PinnView() {
  const p = useFixture<PinnFixture>("pinn.json");
  if (!p.data) return <Loading what="the PINN fields" />;
  const a = p.data.report.accuracy;
  const arch = p.data.report.architecture;
  const cod = p.data.cod.x.map((x, i) => ({
    x: x * 1000, pinn: p.data!.cod.pinn[i] * 1e6, xfem: p.data!.cod.xfem[i] * 1e6,
  }));
  const hist = p.data.history.epoch.map((e, i) => {
    const row: Record<string, number> = { epoch: e };
    Object.keys(p.data!.history).forEach((k) => {
      if (k !== "epoch") row[k] = p.data!.history[k][i];
    });
    return row;
  });
  const lossKeys = Object.keys(p.data.history).filter((k) => k !== "epoch");
  const colors = ["#9aa4ff", "#7fd1c0", "#e8b04b", "#c96a3f", "#5560d6", "#c96a3f"];

  return (
    <Section
      title="Physics informed network against XFEM"
      lede={`${arch.depth} layers of ${arch.width} tanh units, ${arch.n_parameters.toLocaleString()} parameters, ${arch.enrichment}, trained for ${p.data.report.epochs} epochs in ${fmt(p.data.report.wall_clock_s, 4)} s on CPU.`}
    >
      <div className="grid cols4">
        <Stat k="Displacement relative L2" v={fmt(a.displacement_relative_L2_vs_xfem * 100)} u="percent" />
        <Stat k="K_I, PINN opening fit" v={fmt(a.K_I_pinn_from_opening)} u="MPa sqrt(m)" />
        <Stat k="K_I, XFEM opening fit" v={fmt(a.K_I_xfem_from_opening)} u="MPa sqrt(m)" />
        <Stat k="K_I, interaction integral" v={fmt(a.K_I_xfem_interaction_integral)} u="MPa sqrt(m)" />
        <Stat k="K_I closed form" v={fmt(a.K_I_analytical)} u="MPa sqrt(m)" />
        <Stat k="PINN K_I error" v={fmt(a.K_I_pinn_error_percent)} u="percent" />
        <Stat k="Panel" v={`${p.data.report.panel.W} by ${p.data.report.panel.H}`} u="m" />
        <Stat k="Applied stress" v={fmt(p.data.report.panel.sigma_MPa)} u="MPa" />
      </div>

      <h2>Crack opening profile, the panel that must not be cropped</h2>
      <div className="panel">
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={cod} margin={{ top: 8, right: 18, bottom: 14, left: 6 }}>
            <CartesianGrid stroke={CHART_GRID} />
            <XAxis dataKey="x" type="number" tick={CHART_AXIS} tickFormatter={(v) => fmt(v, 3)}
              label={{ value: "x along the crack in mm", fill: "#8f8d87", fontSize: 11, position: "insideBottom", offset: -6 }} />
            <YAxis tick={CHART_AXIS} tickFormatter={(v) => fmt(v, 3)}
              label={{ value: "opening in micron", angle: -90, fill: "#8f8d87", fontSize: 11, position: "insideLeft" }} />
            <Tooltip contentStyle={{ background: "#14161c", border: "1px solid #262a33", fontSize: 12 }}
              formatter={(v: any) => fmt(Number(v), 4)} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line dataKey="xfem" stroke="#e8b04b" dot={false} strokeWidth={2} isAnimationActive={false} />
            <Line dataKey="pinn" stroke="#9aa4ff" dot={false} strokeWidth={2} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <Note title="Finding 6.4">
        The opening is about 13 percent low at the crack centre while the whole displacement field is
        within 2.4 percent. Near tip behaviour is good, which is why the PINN K_I lands within 2.9
        percent of the interaction integral, and the same opening based estimator applied to the XFEM
        field lands further away than the PINN does. The centre of the profile is where the enrichment
        features carry the least information. The gap is shown in full, not cropped.
      </Note>

      <h2>Five loss terms with NTK style weighting</h2>
      <div className="panel">
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={hist} margin={{ top: 8, right: 18, bottom: 14, left: 6 }}>
            <CartesianGrid stroke={CHART_GRID} />
            <XAxis dataKey="epoch" tick={CHART_AXIS}
              label={{ value: "epoch", fill: "#8f8d87", fontSize: 11, position: "insideBottom", offset: -6 }} />
            <YAxis scale="log" domain={["auto", "auto"]} tick={CHART_AXIS} tickFormatter={(v) => fmt(v, 2)} />
            <Tooltip contentStyle={{ background: "#14161c", border: "1px solid #262a33", fontSize: 12 }}
              formatter={(v: any) => fmt(Number(v), 4)} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {lossKeys.map((k, i) => (
              <Line key={k} dataKey={k} stroke={colors[i % colors.length]} dot={false} isAnimationActive={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="muted">
        torch CPU is not bitwise portable across builds. These numbers are read from
        pinn/artifacts/pinn_report.json rather than retrained.
      </p>
    </Section>
  );
}
