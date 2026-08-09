// Small shared pieces. Kept in one file on purpose, none of them earns its own module.
import { motion } from "framer-motion";
import { useEffect, useState, type ReactNode } from "react";
import { loadJson, mode, type Mode } from "./data";

export function useMode(): Mode | undefined {
  const [m, setM] = useState<Mode | undefined>(undefined);
  useEffect(() => {
    let live = true;
    mode().then((v) => live && setM(v));
    return () => {
      live = false;
    };
  }, []);
  return m;
}

// Pass undefined to skip the fetch. The playground uses that in live mode, where the
// precomputed grid must not be loaded at all.
export function useFixture<T>(name: string | undefined) {
  const [state, setState] = useState<{ data?: T; error?: string }>({});
  useEffect(() => {
    if (!name) return;
    let live = true;
    loadJson<T>(name)
      .then((d) => live && setState({ data: d }))
      .catch((e) => live && setState({ error: String(e.message || e) }));
    return () => {
      live = false;
    };
  }, [name]);
  return state;
}

export function Loading({ what }: { what: string }) {
  return <div className="loading">Loading {what}</div>;
}

// Pass hero to lift the header into a banner. Only the landing view uses it, the other
// eleven keep the plain title so the app does not shout on every screen.
export function Section({ title, lede, eyebrow, claim, hero, children }: {
  title: string;
  lede?: string;
  eyebrow?: string;
  claim?: ReactNode;
  hero?: ReactNode;
  children: ReactNode;
}) {
  const header = (
    <>
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <h1>{title}</h1>
      {claim && <p className="claim">{claim}</p>}
      {lede && <p className="lede">{lede}</p>}
      {hero && <div className="rail">{hero}</div>}
    </>
  );
  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.22, 0.61, 0.36, 1] }}
    >
      {hero ? <div className="hero">{header}</div> : header}
      {children}
    </motion.section>
  );
}

export function Stat({ k, v, u, hint }: { k: string; v: ReactNode; u?: string; hint?: string }) {
  return (
    <div className="stat" title={hint}>
      <div className="k">{k}</div>
      <div className="v">
        {v}
        {u && <span className="u">{u}</span>}
      </div>
    </div>
  );
}

export function Note({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="note">
      <h4>{title}</h4>
      <p>{children}</p>
    </div>
  );
}

export function Select({
  label,
  value,
  options,
  labels,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  labels?: Record<string, string>;
  onChange: (v: string) => void;
}) {
  return (
    <label className="field">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => (
          <option key={o} value={o}>
            {labels?.[o] ?? o}
          </option>
        ))}
      </select>
    </label>
  );
}

export function Slider({
  label,
  values,
  index,
  unit,
  onChange,
}: {
  label: string;
  values: number[];
  index: number;
  unit: string;
  onChange: (i: number) => void;
}) {
  return (
    <label className="field">
      {label} <span className="val">{values[index]} {unit}</span>
      <input
        type="range"
        min={0}
        max={values.length - 1}
        step={1}
        value={index}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}

export const CHART_AXIS = { stroke: "#8f8d87", fontSize: 11 };
export const CHART_GRID = "#262a33";
export const DOMAIN_COLOR: Record<string, string> = {
  aerospace: "#9aa4ff",
  biomedical: "#7fd1c0",
  civil: "#e8b04b",
};
