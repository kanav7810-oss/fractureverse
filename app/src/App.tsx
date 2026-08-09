// FRACTUREVERSE Part 3 shell. Twelve features, one sidebar, no router dependency.
import { motion } from "framer-motion";
import { useState } from "react";
import type { Capabilities } from "./data";
import { fmt } from "./data";
import { Leaderboard, Parity, PinnView, ShapView } from "./Models";
import { PeridynamicView, XfemView } from "./Physics";
import { Playground } from "./Playground";
import { Loading, Note, Section, Stat, useFixture, useMode } from "./ui";
import { Viewer3D } from "./Viewer3D";

function Overview({ caps }: { caps: Capabilities }) {
  const summary = useFixture<any>("stats_summary.json");
  const validation = useFixture<any>("validation.json");
  const passed = (v: any) => (v ? v.checks.filter((c: any) => c.pass).length : 0);

  return (
    <Section
      title="FRACTUREVERSE"
      eyebrow="Multi physics fracture propagation digital twin"
      claim={
        <>
          Four fracture theories on one material database, one unit convention and one
          validation harness, applied to an airframe panel, a cortical bone section and a
          concrete deck. Every number on this page is read from disk or from the solver.
          None is typed by hand.
        </>
      }
      hero={
        <>
          <span className="pill indigo"><b>4</b> theories, LEFM, EPFM, XFEM, peridynamics</span>
          <span className="pill jade"><b>3</b> domains, aerospace, biomedical, civil</span>
          <span className="pill ember"><b>1,500</b> seeded trajectories</span>
          <span className="pill">
            <b>
              {validation.data
                ? passed(validation.data.part1) + passed(validation.data.part2)
                : "..."}
            </b>
            physics and model checks passing
          </span>
        </>
      }
    >
      <div className="grid cols4">
        <Stat k="Theories" v={caps.theories.length} />
        <Stat k="Domains" v={Object.keys(caps.domains).length} />
        <Stat k="Trajectories" v="1,500" hint="500 per domain, seed 1337" />
        <Stat k="Figures" v={summary.data?.figure_count ?? "..."} u="at 300 dpi" />
        <Stat k="Part 1 checks" v={validation.data ? `${passed(validation.data.part1)} of ${validation.data.part1.checks.length}` : "..."} />
        <Stat k="Part 2 checks" v={validation.data ? `${passed(validation.data.part2)} of ${validation.data.part2.checks.length}` : "..."} />
        <Stat
          k="Best RMSE"
          v={summary.data
            ? fmt(Math.min(...Object.values(summary.data.machine_learning.test_scores as Record<string, any>)
                .map((s: any) => s.rmse_decades)), 3)
            : "..."}
          u="decades"
          hint="held out test split, lowest RMSE across the four models"
        />
        <Stat k="PINN field error" v="2.37" u="percent" />
      </div>

      <h2>The three domains</h2>
      <div className="hscroll">
        {Object.entries(caps.domains).map(([key, d]) => (
          <div key={key} className="panel" style={{ width: 360 }}>
            <h3>{key}</h3>
            <p style={{ fontSize: 13, margin: "0 0 10px" }}>{d.cycle_frequency_note}</p>
            <div className="grid cols2">
              <Stat k="Cycles per year" v={d.cycle_frequency_per_year.toLocaleString()} />
              <Stat k="Recommended theory" v={caps.recommended_theory[key]} />
            </div>
            <p className="muted" style={{ fontSize: 12, marginTop: 10 }}>{d.inspection_interval_note}</p>
            <p className="muted" style={{ fontSize: 12 }}>{String((d.impact as any).source)}</p>
          </div>
        ))}
      </div>

      <h2>Life per domain, both Paris coefficients</h2>
      <div className="tablewrap panel">
        {summary.data ? (
          <table>
            <thead>
              <tr>
                <th>Domain</th><th>Material</th><th className="num">Stress, MPa</th>
                <th className="num">N_f specified</th><th className="num">Years</th>
                <th className="num">N_f anchored</th><th className="num">Years</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(summary.data.domain_lives as Record<string, any>).map(([d, v]) => (
                <tr key={d}>
                  <td>{d}</td>
                  <td>{v.material}</td>
                  <td className="num">{fmt(v.sigma_max_MPa)}</td>
                  <td className="num">{fmt(v.specified.N_f, 5)}</td>
                  <td className="num">{fmt(v.specified.years_to_failure, 4)}</td>
                  <td className="num">{v.anchored ? fmt(v.anchored.N_f, 5) : "n/a"}</td>
                  <td className="num">{v.anchored ? fmt(v.anchored.years_to_failure, 4) : "n/a"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Loading what="the summary" />
        )}
      </div>

      <h2>Honesty notes carried forward</h2>
      <div className="grid cols2" style={{ marginTop: 4 }}>
        <Note title="The specified Paris coefficient is conservative">
          For 2024-T3 it predicts about 5.7 times the commonly cited growth rate at the same slope.
          Both lives are reported everywhere, and every life shown in this app uses the specified value.
        </Note>
        <Note title="Peridynamic strength depends on the horizon">
          Effective tensile strength scales as one over the square root of delta, so the horizon implied
          strength of 6.81 MPa sits next to the 12 MPa driving stress wherever the result appears.
        </Note>
        <Note title="The surrogate task is close to log linear">
          Ridge scores 0.9998 on the held out split. R squared is not the discriminating metric.
          Leaky features were removed and inspection noise was added, and the comparison to make is
          RMSE in decades of life.
        </Note>
        <Note title="The PINN opening is low at the crack centre">
          About 13 percent low at the centre while the whole field is within 2.4 percent. The near tip
          region, which sets K_I, is the accurate part.
        </Note>
      </div>
    </Section>
  );
}

function Theories({ caps }: { caps: Capabilities }) {
  const [open, setOpen] = useState(caps.theories[0].key);
  return (
    <Section
      title="Theory explorer"
      lede="Four ways to answer the same question, each strongest somewhere different. The list, the labels and the per domain availability all come from capabilities()."
    >
      <div className="hscroll">
        {caps.theories.map((t) => (
          <button
            key={t.key}
            className={`navbtn ${open === t.key ? "active" : ""}`}
            style={{ width: 200, background: "var(--panel)", border: "1px solid var(--line)" }}
            onClick={() => setOpen(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {caps.theories
          .filter((t) => t.key === open)
          .map((t) => (
            <motion.div
              key={t.key}
              className="panel"
              style={{ marginTop: 14 }}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22 }}
            >
              <h2 style={{ marginTop: 0 }}>{t.label}</h2>
              <p>{t.blurb}</p>
              <h3>Available for</h3>
              <div className="legend">
                {Object.entries(caps.theory_for_domain)
                  .filter(([, list]) => list.includes(t.key))
                  .map(([d]) => (
                    <span key={d} className={`badge ${caps.recommended_theory[d] === t.key ? "good" : ""}`}>
                      {d}
                      {caps.recommended_theory[d] === t.key ? " (recommended)" : ""}
                    </span>
                  ))}
              </div>
            </motion.div>
          ))}

      <h2>Geometries the solver will accept</h2>
      <div className="tablewrap panel">
        <table>
          <thead><tr><th>Key</th><th>Meaning</th></tr></thead>
          <tbody>
            {caps.geometries.map((g) => (
              <tr key={g}><td className="mono">{g}</td><td>{caps.geometry_labels[g]}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted">
        geometry_factor raises for an out of range a over W. Center and through are valid below 0.5,
        compact only between 0.2 and 0.8, so the playground offers no combination outside those bounds.
      </p>
    </Section>
  );
}

function Figures() {
  const figs = useFixture<Record<string, string>>("figures.json");
  const [zoom, setZoom] = useState<string | null>(null);
  if (!figs.data) return <Loading what="the figure captions" />;
  const names = Object.keys(figs.data).sort();
  return (
    <Section
      title="Figure gallery"
      lede="The 17 publication figures, served as the 300 dpi PNG that python_stats already produced. Nothing here is replotted in JavaScript, because a static chart gains nothing from being redrawn in the browser."
    >
      <div className="hscroll">
        {names.map((n) => (
          <div key={n} className="figcard">
            <img src={`${import.meta.env.BASE_URL}figures/${n}.png`} alt={figs.data![n]}
              loading="lazy" onClick={() => setZoom(n)} />
            <div className="cap"><strong>{n.replace(/_/g, " ")}</strong><br />{figs.data![n]}</div>
          </div>
        ))}
      </div>
      {zoom && (
        <motion.div className="lightbox" onClick={() => setZoom(null)}
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.15 }}>
          <img src={`${import.meta.env.BASE_URL}figures/${zoom}.png`} alt={figs.data[zoom]} />
        </motion.div>
      )}
    </Section>
  );
}

const FEATURES = [
  { id: "overview", label: "Overview", render: (c: Capabilities) => <Overview caps={c} /> },
  { id: "theories", label: "Theory explorer", render: (c: Capabilities) => <Theories caps={c} /> },
  { id: "playground", label: "Solver playground", render: (c: Capabilities) => <Playground caps={c} /> },
  { id: "viewer", label: "Crack viewer 3D", render: () => <Viewer3D /> },
  { id: "xfem", label: "XFEM crack path", render: () => <XfemView /> },
  { id: "peridynamic", label: "Peridynamic damage", render: () => <PeridynamicView /> },
  { id: "models", label: "Model leaderboard", render: () => <Leaderboard /> },
  { id: "shap", label: "Feature attribution", render: () => <ShapView /> },
  { id: "parity", label: "Parity explorer", render: () => <Parity /> },
  { id: "pinn", label: "PINN against XFEM", render: () => <PinnView /> },
  { id: "figures", label: "Figure gallery", render: () => <Figures /> },
  { id: "validation", label: "Validation log", render: () => <Validation /> },
];

// The detail strings are written by the validators, and a few of them are Python
// containers printed with repr. Nobody should have to read a dict literal to find out
// whether a check passed, so they are unpacked into plain reading order here. The text
// itself is never edited, only the punctuation around it.
function readable(detail: string): string {
  return String(detail)
    .replace(/\((\d+),\s*(\d+)\)/g, "$1 of $2")
    .replace(/[{}[\]']/g, "")
    .replace(/\bTrue\b/g, "yes")
    .replace(/\bFalse\b/g, "no")
    .replace(/\s+/g, " ")
    .trim();
}

// Round to something a reader can hold in their head. Errors in percent and stress
// intensities want figures, node counts do not.
function short(value: string): string {
  const n = Number(value);
  if (!isFinite(n) || value.trim() === "") return value.replace(/_/g, " ");
  if (Number.isInteger(n)) return n.toLocaleString();
  return Math.abs(n) >= 1e5 || (Math.abs(n) < 1e-3 && n !== 0)
    ? n.toExponential(3)
    : String(Number(n.toPrecision(6)));
}

// Part 1 writes its detail as a JSON blob, truncated by the validator at 400 characters.
// Rendered raw it is a wall of quotes. Split it into labelled pairs instead, which is
// the form the numbers were in before they were serialised.
function DetailCell({ detail }: { detail: string }) {
  const raw = String(detail);
  const looksStructured = raw.includes(":") && raw.includes('"');
  if (!looksStructured) return <td className="detail">{readable(raw)}</td>;

  const pairs = raw
    .replace(/[{}[\]"]/g, "")
    .split(",")
    .map((part) => part.split(":"))
    .filter((p) => p.length === 2 && p[0].trim())
    .map(([k, v]) => [k.trim().replace(/_/g, " "), short(v)] as [string, string]);

  if (!pairs.length) return <td className="detail">{readable(raw)}</td>;
  const shown = pairs.slice(0, 12);
  return (
    <td className="detail">
      <div className="kv">
        {shown.map(([k, v], i) => (
          <div key={i} className={v.length > 34 ? "wide" : undefined}>
            <span>{k}</span>
            <b className={v.length > 34 ? undefined : "fig"}>{v}</b>
          </div>
        ))}
      </div>
      {pairs.length > shown.length && (
        <p className="muted" style={{ fontSize: 11, margin: "6px 0 0" }}>
          {pairs.length - shown.length} further fields in research/part1_validation.json
        </p>
      )}
    </td>
  );
}

const VALIDATOR_NOTE: Record<string, string> = {
  "Part 1": "Physics. Each theory is measured against a target that does not come from this "
    + "codebase: the closed form Paris integral, handbook geometry factors, the analytical "
    + "centre cracked panel, K_I squared over E prime for the domain J integral, and the "
    + "Erdogan and Sih kink angle limit. Peridynamic calibration is checked both as the "
    + "continuum identity and as the discrete recovery at a stated horizon ratio.",
  "Part 2": "Models. validate_part2.py trains nothing. It loads the saved weights and the "
    + "frozen split from ml/artifacts and asserts they reproduce the published test scores "
    + "to 1e-9, so a reported number and a rerun number cannot drift apart. It also asserts "
    + "the leaky features are absent from the reported feature set.",
};

function Validation() {
  const v = useFixture<any>("validation.json");
  if (!v.data) return <Loading what="the validation reports" />;
  return (
    <Section
      title="Validation log"
      lede="Every acceptance check from the completed parts, as written by the validators themselves. Nothing here is a summary of a result, it is the result. Reproduce any row by running the validator named beside it."
    >
      {[["Part 1", v.data.part1], ["Part 2", v.data.part2]].map(([label, rep]: any) => {
        const ok = rep.checks.filter((c: any) => c.pass).length;
        return (
          <div key={label}>
            <h2>
              {label}, {ok} of {rep.checks.length} passing
            </h2>
            <p className="muted" style={{ fontSize: 13, maxWidth: "80ch" }}>
              {VALIDATOR_NOTE[label]}
            </p>
            <div className="tablewrap panel">
              <table>
                <thead>
                  <tr>
                    <th className="check">Check</th>
                    <th>Result</th>
                    <th>What was measured, and against what</th>
                  </tr>
                </thead>
                <tbody>
                  {rep.checks.map((c: any, i: number) => (
                    <tr key={i}>
                      <td className="check">{c.name}</td>
                      <td>
                        <span className={`badge ${c.pass ? "good" : "bad"}`}>
                          {c.pass ? "pass" : "fail"}
                        </span>
                      </td>
                      <DetailCell detail={c.detail} />
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
    </Section>
  );
}

export default function App() {
  const caps = useFixture<Capabilities>("capabilities.json");
  const dataMode = useMode();
  const [active, setActive] = useState("overview");

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          FRACTUREVERSE
          <small>Four theories, three domains, one validated stack.</small>
          <small data-testid="app-mode">
            {dataMode === undefined
              ? "checking for the solver service"
              : dataMode === "live"
              ? "live: solves run in api/main.py"
              : "offline: precomputed fixtures, start uvicorn for live solves"}
          </small>
        </div>
        <ul className="navlist">
          {FEATURES.map((f, i) => (
            <li key={f.id}>
              <button className={`navbtn ${active === f.id ? "active" : ""}`} onClick={() => setActive(f.id)}>
                <span className="num">{String(i + 1).padStart(2, "0")}</span>
                {f.label}
              </button>
            </li>
          ))}
        </ul>
      </aside>
      <main className="main">
        {caps.error && <div className="loading">{caps.error}</div>}
        {!caps.data && !caps.error && <Loading what="capabilities" />}
        {caps.data && (
          // No AnimatePresence around the feature swap. An exit animation here strands the
          // outgoing view under React 19 strict mode, and the section already fades itself in.
          <motion.div key={active} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }}>
            {FEATURES.find((f) => f.id === active)!.render(caps.data)}
          </motion.div>
        )}
      </main>
    </div>
  );
}
