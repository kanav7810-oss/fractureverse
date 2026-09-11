// Geometry library. Six cases, one style, palette only.
// No new colors, no new fonts, SVG line diagrams only.
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
  brazilian: { title: "Brazilian disk", desc: "Placeholder" },
  ct: { title: "Compact tension (CT)", desc: "Placeholder" },
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
