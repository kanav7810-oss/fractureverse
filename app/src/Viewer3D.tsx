// Feature 5. Volumetric crack viewer.
// One InstancedMesh, so 50,000 cells is one draw call. A Radeon 610M will not hold 30 fps
// with 50,000 separate meshes, which is why nothing here is drawn individually.
// The field is the peridynamic damage field from the Part 1 branching run, resampled onto the
// grid and extruded through the thickness. It is a damage field, not a stress field, and the
// HUD says so.
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { useLayoutEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import type { PeridynamicFixture } from "./data";
import { fmt } from "./data";
import { Loading, Note, Section, Stat, useFixture } from "./ui";

const FULL: [number, number, number] = [50, 50, 20]; // 50,000 cells
const FALLBACK: [number, number, number] = [30, 30, 10]; // 9,000 cells
const FRAME_BUDGET_MS = 50;

function damageAt(d: number[], shape: [number, number], u: number, v: number) {
  const [nx, ny] = shape;
  const i = Math.min(nx - 1, Math.max(0, Math.round(u * (nx - 1))));
  const j = Math.min(ny - 1, Math.max(0, Math.round(v * (ny - 1))));
  return d[i * ny + j];
}

// Per instance colour was tried and dropped. three only declares the instancing colour
// attribute when instanceColor exists at material compile time, and under r3f the
// material here compiles first, so every cell rendered black. Pre allocating the
// attribute and forcing a recompile did not change it. Splitting the field into a mesh
// per damage band would fix the colour and cost the single draw call this whole view
// exists to demonstrate, so the cells are one jade and the threshold slider is what
// reads damage magnitude. The peridynamic view carries the full ramp on its 2D map.

function Field({
  fixture,
  res,
  threshold,
  onSlow,
}: {
  fixture: PeridynamicFixture;
  res: [number, number, number];
  threshold: number;
  onSlow: () => void;
}) {
  const ref = useRef<THREE.InstancedMesh>(null!);
  const [nx, ny, nz] = res;
  const count = nx * ny * nz;
  const slowFrames = useRef(0);

  useLayoutEffect(() => {
    const mesh = ref.current;
    const m = new THREE.Matrix4();
    const sx = 3.0 / nx, sy = 1.5 / ny, sz = 0.6 / nz;
    let n = 0;
    for (let i = 0; i < nx; i++) {
      for (let j = 0; j < ny; j++) {
        const d = damageAt(fixture.damage, fixture.damage_shape, i / (nx - 1), j / (ny - 1));
        for (let k = 0; k < nz; k++) {
          const visible = d >= threshold;
          const s = visible ? 1 : 0.0001; // hide intact cells without changing the draw call
          m.makeScale(sx * 0.92 * s, sy * 0.92 * s, sz * 0.92 * s);
          m.setPosition((i + 0.5) * sx - 1.5, (j + 0.5) * sy - 0.75, (k + 0.5) * sz - 0.3);
          mesh.setMatrixAt(n, m);
          n++;
        }
      }
    }
    mesh.instanceMatrix.needsUpdate = true;
  }, [fixture, nx, ny, nz, threshold]);

  useFrame((_, delta) => {
    if (delta * 1000 > FRAME_BUDGET_MS) {
      slowFrames.current += 1;
      if (slowFrames.current > 20) {
        slowFrames.current = 0;
        onSlow();
      }
    } else if (slowFrames.current > 0) {
      slowFrames.current -= 1;
    }
  });

  return (
    <instancedMesh ref={ref} args={[undefined as any, undefined as any, count]}>
      <boxGeometry />
      <meshStandardMaterial color="#7fd1c0" roughness={0.55} metalness={0.05} />
    </instancedMesh>
  );
}

export function Viewer3D() {
  const pd = useFixture<PeridynamicFixture>("peridynamic.json");
  const [res, setRes] = useState<[number, number, number]>(FULL);
  const [threshold, setThreshold] = useState(0.15);
  const [degraded, setDegraded] = useState(false);

  const count = useMemo(() => res[0] * res[1] * res[2], [res]);

  if (!pd.data) return <Loading what="the damage field" />;
  const s = pd.data.scalars as Record<string, any>;

  return (
    <Section
      title="Volumetric crack viewer"
      lede="The concrete panel damage field, extruded through the thickness and drawn as one instanced mesh, which is why 50,000 cells cost one draw call. Cells below the damage threshold shrink to nothing rather than being removed, so the instance count and the draw call never change. Raise the threshold to peel the field back to the fully broken core."
    >
      <div className="viewer">
        <Canvas camera={{ position: [3.4, 2.2, 3.2], fov: 45 }} dpr={[1, 1.5]}>
          <color attach="background" args={["#07080b"]} />
          <ambientLight intensity={0.55} />
          <directionalLight position={[4, 6, 5]} intensity={1.1} />
          <Field
            fixture={pd.data}
            res={res}
            threshold={threshold}
            onSlow={() => {
              if (res !== FALLBACK) {
                setRes(FALLBACK);
                setDegraded(true);
              }
            }}
          />
          <OrbitControls enablePan={false} />
        </Canvas>
        <div className="hud">
          <span className="fig">{count.toLocaleString()}</span> instances, one draw call
          {degraded && ", fell back to 30 x 30 x 10 after frame time passed 50 ms"}
        </div>
      </div>

      <div className="panel" style={{ marginTop: 14 }}>
        <div className="controls">
          <label className="field">
            Damage threshold <span className="val">{threshold.toFixed(2)}</span>
            <input type="range" min={0} max={0.95} step={0.05} value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))} />
          </label>
          <label className="field">
            Resolution
            <select value={res.join("x")} onChange={(e) => {
              setRes(e.target.value === FULL.join("x") ? FULL : FALLBACK);
              setDegraded(false);
            }}>
              <option value={FULL.join("x")}>50 x 50 x 20, 50,000 cells</option>
              <option value={FALLBACK.join("x")}>30 x 30 x 10, 9,000 cells</option>
            </select>
          </label>
        </div>
      </div>

      <h2>What the field is</h2>
      <div className="grid cols4">
        <Stat k="Panel" v={`${fmt(3.0)} x ${fmt(1.5)}`} u="m" />
        <Stat k="Horizon delta" v={fmt(s.delta)} u="m" />
        <Stat k="Applied stress" v={fmt(s.sigma_MPa)} u="MPa" />
        <Stat k="Horizon implied strength" v={fmt(s.pd_strength_MPa)} u="MPa" />
        <Stat k="Bonds" v={Number(s.n_bonds).toLocaleString()} />
        <Stat k="Broken fraction" v={fmt(s.broken_fraction)} />
        <Stat k="Branched" v={s.branched ? "yes" : "no"} />
        <Stat k="First branch at x" v={fmt(s.first_branch_x)} u="m" />
      </div>
      <Note title="Finding 6.2, carried from Part 1">
        Bond based peridynamics ties tensile strength to the horizon, effective strength scales as one
        over the square root of delta, and the Poisson ratio is fixed at one third in 2D plane stress.
        The horizon implied strength is {fmt(s.pd_strength_MPa)} MPa against the {fmt(s.sigma_MPa)} MPa
        applied, so both numbers appear together and neither is shown alone.
      </Note>
    </Section>
  );
}
