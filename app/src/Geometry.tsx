// Geometry library. Six cases, one style, palette only.
// No new colors, no new fonts, SVG line diagrams only.
// Strokes use jade for panels, ember for cracks, indigo for loads, muted for labels.
export type GeometryKey = "sent" | "dent" | "ccp" | "tpb" | "brazilian" | "ct";

export const GEOMETRY_META: Record<GeometryKey, { title: string; desc: string }> = {
  sent: {
    title: "Single edge notch tension (SENT)",
    desc: "One edge crack under remote tension. Crack length a, width W, height H.",
  },
  dent: {
    title: "Double edge notch tension (DENT)",
    desc: "Two symmetric edge cracks under remote tension. Crack length a each side, width W, height H.",
  },
  ccp: {
    title: "Center cracked panel (CCP)",
    desc: "Center crack of half length a under remote tension. Width W, height H.",
  },
  tpb: {
    title: "Three point bend (TPB)",
    desc: "Edge cracked beam in bending. Span S, width W, crack length a, load P at midspan.",
  },
  brazilian: {
    title: "Brazilian disk",
    desc: "Cracked disk under diametral compression. Diameter D, crack half length a, load P.",
  },
  ct: {
    title: "Compact tension (CT)",
    desc: "Standard CT specimen with pin loading. Width W, crack length a, load P at pins.",
  },
};

function Frame({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <div className="panel" style={{ width: 300 }}>
      <h3>{label}</h3>
      <svg viewBox="0 0 200 140" width="100%" height="140" role="img" aria-label={label}>
        {children}
      </svg>
    </div>
  );
}

export function DentDiagram() {
  return (
    <Frame label="DENT">
      <rect x="60" y="10" width="80" height="120" fill="none" stroke="#7fd1c0" strokeWidth="2" />
      <line x1="60" y1="70" x2="90" y2="70" stroke="#e8b04b" strokeWidth="3" />
      <line x1="110" y1="70" x2="140" y2="70" stroke="#e8b04b" strokeWidth="3" />
      <text x="70" y="65" fill="#8f8d87" fontSize="9">a</text>
      <text x="120" y="65" fill="#8f8d87" fontSize="9">a</text>
      <text x="95" y="135" fill="#8f8d87" fontSize="9">W</text>
      <text x="95" y="30" fill="#8f8d87" fontSize="9">H</text>
      <line x1="60" y1="4" x2="140" y2="4" stroke="#9aa4ff" strokeWidth="1" />
      <text x="145" y="8" fill="#9aa4ff" fontSize="9">P</text>
      <line x1="60" y1="136" x2="140" y2="136" stroke="#9aa4ff" strokeWidth="1" />
      <text x="145" y="139" fill="#9aa4ff" fontSize="9">P</text>
    </Frame>
  );
}

export function CcpDiagram() {
  return (
    <Frame label="CCP">
      <rect x="60" y="10" width="80" height="120" fill="none" stroke="#7fd1c0" strokeWidth="2" />
      <line x1="80" y1="70" x2="120" y2="70" stroke="#e8b04b" strokeWidth="3" />
      <text x="96" y="65" fill="#8f8d87" fontSize="9">2a</text>
      <text x="95" y="135" fill="#8f8d87" fontSize="9">W</text>
      <text x="45" y="75" fill="#8f8d87" fontSize="9">H</text>
      <line x1="60" y1="4" x2="140" y2="4" stroke="#9aa4ff" strokeWidth="1" />
      <text x="145" y="8" fill="#9aa4ff" fontSize="9">P</text>
      <line x1="60" y1="136" x2="140" y2="136" stroke="#9aa4ff" strokeWidth="1" />
      <text x="145" y="139" fill="#9aa4ff" fontSize="9">P</text>
    </Frame>
  );
}

export function TpbDiagram() {
  return (
    <Frame label="TPB">
      <rect x="40" y="60" width="120" height="40" fill="none" stroke="#7fd1c0" strokeWidth="2" />
      <line x1="100" y1="100" x2="100" y2="75" stroke="#e8b04b" strokeWidth="3" />
      <text x="104" y="90" fill="#8f8d87" fontSize="9">a</text>
      <text x="95" y="115" fill="#8f8d87" fontSize="9">W</text>
      <text x="90" y="125" fill="#8f8d87" fontSize="9">S</text>
      <circle cx="50" cy="105" r="4" fill="none" stroke="#9aa4ff" strokeWidth="1" />
      <circle cx="150" cy="105" r="4" fill="none" stroke="#9aa4ff" strokeWidth="1" />
      <line x1="100" y1="45" x2="100" y2="60" stroke="#9aa4ff" strokeWidth="2" />
      <text x="104" y="52" fill="#9aa4ff" fontSize="9">P</text>
    </Frame>
  );
}

export function BrazilianDiagram() {
  return (
    <Frame label="Brazilian">
      <circle cx="100" cy="70" r="50" fill="none" stroke="#7fd1c0" strokeWidth="2" />
      <line x1="80" y1="70" x2="120" y2="70" stroke="#e8b04b" strokeWidth="3" />
      <text x="96" y="65" fill="#8f8d87" fontSize="9">2a</text>
      <text x="130" y="110" fill="#8f8d87" fontSize="9">D</text>
      <line x1="100" y1="5" x2="100" y2="20" stroke="#9aa4ff" strokeWidth="2" />
      <text x="104" y="14" fill="#9aa4ff" fontSize="9">P</text>
      <line x1="100" y1="120" x2="100" y2="135" stroke="#9aa4ff" strokeWidth="2" />
      <text x="104" y="133" fill="#9aa4ff" fontSize="9">P</text>
    </Frame>
  );
}

export function CtDiagram() {
  return (
    <Frame label="CT">
      <rect x="55" y="20" width="90" height="100" fill="none" stroke="#7fd1c0" strokeWidth="2" />
      <line x1="55" y1="70" x2="95" y2="70" stroke="#e8b04b" strokeWidth="3" />
      <text x="70" y="65" fill="#8f8d87" fontSize="9">a</text>
      <text x="90" y="125" fill="#8f8d87" fontSize="9">W</text>
      <circle cx="80" cy="45" r="5" fill="none" stroke="#9aa4ff" strokeWidth="1" />
      <circle cx="80" cy="95" r="5" fill="none" stroke="#9aa4ff" strokeWidth="1" />
      <text x="88" y="48" fill="#9aa4ff" fontSize="9">P</text>
      <text x="88" y="98" fill="#9aa4ff" fontSize="9">P</text>
    </Frame>
  );
}

export function GeometryStrip({ keys }: { keys: GeometryKey[] }) {
  const map: Record<GeometryKey, React.ReactNode> = {
    sent: <SentDiagram />,
    dent: <DentDiagram />,
    ccp: <CcpDiagram />,
    tpb: <TpbDiagram />,
    brazilian: <BrazilianDiagram />,
    ct: <CtDiagram />,
  };
  return (
    <div className="hscroll">
      {keys.map((k) => (
        <div key={k}>{map[k]}</div>
      ))}
    </div>
  );
}

export const METHOD_GEOMETRIES: Record<string, GeometryKey[]> = {
  peridynamics: ["sent", "dent", "ccp", "tpb", "brazilian", "ct"],
  xfem: ["sent", "dent", "ccp", "tpb", "brazilian", "ct"],
  cohesive: ["sent", "dent", "ccp", "tpb", "brazilian", "ct"],
  phasefield: ["sent", "dent", "ccp", "tpb", "brazilian", "ct"],
};

export function SentDiagram() {
  return (
    <Frame label="SENT">
      <rect x="60" y="10" width="80" height="120" fill="none" stroke="#7fd1c0" strokeWidth="2" />
      <line x1="60" y1="70" x2="100" y2="70" stroke="#e8b04b" strokeWidth="3" />
      <line x1="100" y1="0" x2="100" y2="10" stroke="#8f8d87" strokeWidth="1" />
      <text x="80" y="65" fill="#8f8d87" fontSize="9">a</text>
      <text x="95" y="135" fill="#8f8d87" fontSize="9">W</text>
      <line x1="60" y1="4" x2="140" y2="4" stroke="#9aa4ff" strokeWidth="1" markerEnd="url(#a)" />
      <text x="145" y="8" fill="#9aa4ff" fontSize="9">P</text>
      <line x1="60" y1="136" x2="140" y2="136" stroke="#9aa4ff" strokeWidth="1" />
      <text x="145" y="139" fill="#9aa4ff" fontSize="9">P</text>
    </Frame>
  );
}
