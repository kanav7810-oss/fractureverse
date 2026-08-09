// Data layer. Two modes, and the app says which one it is in rather than falling back
// silently. Live mode talks to the FastAPI service in api/main.py, so the playground
// runs the real solver and sweep.json is never fetched. Offline mode reads the static
// fixtures built by app/gen_fixtures.py. The shapes are identical either way.

export const BASE = import.meta.env.BASE_URL + "data/";
export const API = import.meta.env.VITE_API_BASE ?? "/api";

export type Mode = "live" | "offline";

// Precomputed artifacts of Part 1 and Part 2. The backend serves these too, but they
// are the same bytes, so mode only decides where they are fetched from.
const SERVED_LIVE = new Set([
  "capabilities.json", "stats_summary.json", "anchored.json", "xfem.json",
  "peridynamic.json", "ml.json", "pinn.json", "figures.json", "validation.json",
]);

let modeProbe: Promise<Mode> | undefined;

export function mode(): Promise<Mode> {
  if (!modeProbe) {
    modeProbe = fetch(API + "/health")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("no backend"))))
      .then((h) => (h.live_solver ? "live" : "offline") as Mode)
      .catch(() => "offline" as Mode);
  }
  return modeProbe;
}

const cache = new Map<string, Promise<unknown>>();

export function loadJson<T>(name: string): Promise<T> {
  if (!cache.has(name)) {
    cache.set(name, mode().then((m) => {
      const url = m === "live" && SERVED_LIVE.has(name) ? `${API}/data/${name}` : BASE + name;
      return fetch(url).then((r) => {
        if (!r.ok) throw new Error(`${name} missing, run python app/gen_fixtures.py`);
        return r.json();
      });
    }));
  }
  return cache.get(name) as Promise<T>;
}

export type SolveBody = {
  domain: string;
  material?: string | null;
  theory?: string;
  growth_law?: string;
  load?: { sigma_max: number; R?: number };
  crack?: { a0: number; geometry: string; W?: number };
};

export type SolveResult = {
  K_I: number; K_II: number; K_IC: number; K_ratio: number; G: number;
  delta_K: number; da_dN: number; a_c: number; N_f: number; years_to_failure: number;
  plastic_zone: number; ssy_valid: boolean; theory: string; material: string;
  history: { a: number[]; N: number[] };
  J_elastic?: number; J_elastic_plastic?: number; J_IC?: number; J_ratio?: number;
  ctod?: number; ctod_critical?: number;
};

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(API + path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await r.json();
  if (!r.ok) throw new Error(payload?.detail?.error ?? `${path} failed`);
  return payload as T;
}

export const apiSolve = (body: SolveBody) => post<SolveResult>("/solve", body);

export type PredictResult = {
  log10_N_f: number; N_f_predicted: number; N_f_closed_form: number;
  life_ratio_error: number; a_c: number; model: string; note: string;
};

export const apiPredict = (body: Record<string, unknown>) =>
  post<PredictResult>("/predict", body);

export type DomainMeta = {
  domain: string;
  cycle_frequency_per_year: number;
  cycle_frequency_note: string;
  inspection_interval_note: string;
  impact: Record<string, unknown>;
  materials: string[];
};

export type Capabilities = {
  domains: Record<string, DomainMeta>;
  theories: { key: string; label: string; blurb: string }[];
  theory_for_domain: Record<string, string[]>;
  recommended_theory: Record<string, string>;
  geometries: string[];
  geometry_labels: Record<string, string>;
  growth_laws: string[];
  modes: string[];
};

export type SweepRecord = {
  id: string;
  domain: string;
  material: string;
  geometry: string;
  law: string;
  sigma_MPa: number;
  a0_mm: number;
  K_I: number;
  K_IC: number;
  K_ratio: number;
  G: number;
  delta_K: number;
  da_dN: number;
  a_c: number;
  N_f: number;
  years_to_failure: number;
  plastic_zone: number;
  ssy_valid: boolean;
  J_elastic?: number;
  J_elastic_plastic?: number;
  J_IC?: number;
  J_ratio?: number;
  ctod?: number;
  ctod_critical?: number;
};

export type Sweep = { sigma_MPa: number[]; a0_mm: number[]; records: SweepRecord[] };
export type Curves = Record<string, { a: number[]; N: number[] }>;

export type MlFixture = {
  report: any;
  shap: { features: string[]; mean_abs_shap: number[]; base_value: number };
  lstm_history: { epoch: number[]; train_loss: number[]; val_rmse: number[] };
  parity: { y: number[]; domain: string[]; models: Record<string, number[]> };
};

export type PinnFixture = {
  report: any;
  history: Record<string, number[]>;
  cod: { x: number[]; pinn: number[]; xfem: number[] };
  field: { xy: number[][]; uv_pinn: number[][]; uv_xfem: number[][] };
};

export type PeridynamicFixture = {
  scalars: Record<string, number | string | boolean | null>;
  energy_check: Record<string, number>;
  damage_shape: [number, number];
  damage: number[];
};

export type XfemFixture = Record<string, any> & {
  propagation: { path: number[][]; K_I: number[]; K_II: number[]; theta_deg: number[]; K_eff: number[]; a: number[] };
};

export type Figure = { file?: string; title?: string; caption?: string } & Record<string, unknown>;

// Formatting helpers. Life numbers arrive as cycles, the ML target arrives as log10 cycles.
export const fmt = (x: number | null | undefined, digits = 3): string =>
  x === null || x === undefined || !isFinite(x)
    ? "n/a"
    : Math.abs(x) >= 1e5 || (Math.abs(x) < 1e-3 && x !== 0)
    ? x.toExponential(2)
    : Number(x.toPrecision(digits)).toString();

export const fromLogLife = (log10N: number): number => Math.pow(10, log10N);
