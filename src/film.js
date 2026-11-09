// "Mimi and the Bell Flower" — a 12 second plush short.
//
// BEATS
//  0.0–2.6  Spring orchard. A cherry petal lets go and drifts down onto Mimi's nose;
//           the baby owl peeks over the nest edge to watch.
//  2.6–3.5  Tickle… inhale… SNEEZE. The petal blasts away.
//  3.5–4.6  The startled chick hops, tips over the nest edge and falls 2.2 units.
//  4.6–5.9  BOING — the giant bell flower bounces the chick; Mimi scrambles and catches it.
//  5.9–7.2  A cuddle, the chick goes on Mimi's head, Mimi hops onto the bell flower.
//  7.2–8.5  Squash… launch! At the top of the jump the chick hops back into its nest.
//  8.5–12   Mimi lands on the bell, they wave; the petal floats back onto Mimi's head.

import * as THREE from '../vendor/three.module.js';
import { PALETTE, SUPPORT } from './brand.js';
import {
  clamp, lerp, seg, smooth, easeInOut, easeOut, env, impulse, blink, arcY, track, rng,
} from './util.js';
import {
  felt, petalGeometry, buildLeaf, buildMimi, poseMimi, MIMI_CHEST, MIMI_HEAD_TOP,
  buildChick, poseChick, buildBellFlower, bellCapHeight, buildHeroTree, buildBackgroundTree,
} from './models.js';

export const DURATION = 12;
const V3 = (x, y, z) => new THREE.Vector3(x, y, z);
const Y = V3(0, 1, 0);

// ------------------------------------------------------------- layout
const FLOWER = V3(0.2, 0, 0);
const NEST_SEAT = V3(0.2, 3.17, 0.03);
const MIMI_START = V3(1.5, 0, 0.7);
const MIMI_CATCH = V3(0.85, 0, 0.35);
const MIMI_ON_BELL = V3(0.2, 0, 0.38);
const BELL_R_MIMI = Math.hypot(MIMI_ON_BELL.x - FLOWER.x, MIMI_ON_BELL.z - FLOWER.z);

// ------------------------------------------------------------- timeline
function bellSquash(t) {
  let s = impulse(t, 4.57, 0.4, 6, 20);
  if (t >= 7.2 && t < 7.5) s += 0.3 * easeOut(seg(t, 7.2, 7.5)) + impulse(t, 7.2, 0.12, 8, 20);
  if (t >= 7.5) {
    const d = t - 7.5;
    s += 0.3 * Math.exp(-5 * d) * Math.cos(17 * d);
  }
  if (t >= 8.5) s += impulse(t, 8.5, 0.5, 5, 16) + 0.06 * smooth(seg(t, 8.5, 9.0));
  return s;
}
const bellScaleY = (t) => 1 - bellSquash(t);
const bellTopAt = (t, r) => bellScaleY(t) * bellCapHeight(r * (1 + 0.6 * bellSquash(t)) ** -1);

function mimiState(t) {
  const s = {};
  // Position.
  let pos;
  if (t < 5.0) pos = MIMI_START.clone();
  else if (t < 5.8) {
    const u = seg(t, 5.0, 5.8);
    pos = MIMI_START.clone().lerp(MIMI_CATCH, easeInOut(u));
    pos.y = Math.abs(Math.sin(u * Math.PI * 4)) * 0.07;
  } else if (t < 6.6) pos = MIMI_CATCH.clone();
  else if (t < 7.2) {
    const u = seg(t, 6.6, 7.2);
    pos = MIMI_CATCH.clone().lerp(MIMI_ON_BELL, u);
    pos.y = arcY(t, 6.6, 7.2, 0, bellTopAt(7.2, BELL_R_MIMI), 1.25);
  } else if (t < 7.5) {
    pos = MIMI_ON_BELL.clone();
    pos.y = bellTopAt(t, BELL_R_MIMI);
  } else if (t < 8.5) {
    pos = MIMI_ON_BELL.clone();
    pos.y = arcY(t, 7.5, 8.5, bellTopAt(7.5, BELL_R_MIMI), bellTopAt(8.5, BELL_R_MIMI), 2.1);
  } else {
    pos = MIMI_ON_BELL.clone();
    pos.y = bellTopAt(t, BELL_R_MIMI);
  }
  s.pos = pos;

  s.rotY = track([[0, -0.45], [5.0, -0.45], [5.15, -1.25], [5.6, -1.2], [5.85, -0.7], [6.4, -0.25], [7.2, -0.12], [9.0, -0.15], [12, -0.2]], t);
  s.lean = -0.12 * env(t, 5.05, 5.2, 5.6, 5.8);

  // Squash & stretch.
  let sq = 0.012 * Math.sin(t * 3.2);
  sq += -0.06 * env(t, 2.95, 3.4, 3.44, 3.5); // inhale stretch
  sq += impulse(t, 3.45, 0.32, 8, 18); // sneeze
  sq += impulse(t, 5.88, 0.26, 7, 18); // catch
  sq += 0.12 * env(t, 6.45, 6.58, 6.6, 6.66) - 0.1 * env(t, 6.62, 6.7, 6.95, 7.15); // hop
  sq += impulse(t, 7.2, 0.3, 8, 18) + 0.16 * env(t, 7.22, 7.48, 7.5, 7.55); // land + crouch
  sq -= 0.16 * env(t, 7.5, 7.56, 7.75, 7.98); // launch stretch
  sq += impulse(t, 8.5, 0.42, 7, 18);
  s.sq = clamp(sq, -0.2, 0.35);

  // Head.
  s.pitch = track([
    [0, 0], [0.6, -0.1], [1.3, -0.42], [2.1, -0.25], [2.6, -0.05], [2.95, -0.05], [3.4, -0.32],
    [3.47, 0.32], [3.75, 0.2], [3.95, -0.42], [4.55, -0.05], [4.8, -0.22], [5.2, -0.1], [5.9, 0.12],
    [6.15, 0.3], [6.5, 0.0], [7.0, -0.1], [7.6, -0.2], [8.4, 0.05], [9.2, -0.45], [11.0, -0.4],
    [11.45, -0.08], [12, -0.12],
  ], t);
  s.yaw = track([[0, 0], [1.3, -0.15], [2.6, 0], [3.9, -0.3], [4.6, -0.35], [5.0, 0], [6.0, 0.1], [7, 0], [12, 0]], t);
  s.roll = track([[0, 0], [1.0, 0.15], [2.6, 0.1], [3.0, 0], [5.95, 0], [6.2, 0.22], [6.5, 0], [9.5, 0.15], [11.4, 0.22], [12, 0.2]], t);

  // Face.
  let eye = blink(t, 1.6) * blink(t, 5.35) * blink(t, 6.35) * blink(t, 9.6) * blink(t, 10.7);
  eye *= 1 - 0.45 * env(t, 3.05, 3.3, 3.42, 3.44);
  eye *= 1 - env(t, 3.42, 3.45, 3.7, 3.85); // sneeze: eyes squeezed shut
  eye = Math.min(eye, 1 - 0.72 * smooth(seg(t, 11.35, 11.6))); // happy squint at the end
  s.eyeOpen = eye;
  s.eyeWide = 1 + 0.18 * env(t, 4.5, 4.6, 5.0, 5.3) + 0.08 * env(t, 7.55, 7.7, 8.2, 8.5);
  s.cross = env(t, 2.55, 2.75, 3.35, 3.45);
  s.browUp = 0.6 * env(t, 2.9, 3.2, 3.4, 3.47) + env(t, 4.5, 4.6, 5.1, 5.5) + 0.4 * env(t, 7.5, 7.7, 8.3, 8.6);
  s.browWorry = env(t, 4.5, 4.6, 5.4, 5.9) + 0.6 * env(t, 2.9, 3.1, 3.4, 3.47);
  s.mouthOpen = Math.max(
    0.35 * env(t, 3.0, 3.35, 3.42, 3.45),
    1.0 * env(t, 3.44, 3.47, 3.6, 3.9),
    0.7 * env(t, 4.55, 4.65, 5.2, 5.5),
    0.55 * env(t, 7.55, 7.7, 8.25, 8.55),
    0.25 * env(t, 9.9, 10.1, 10.6, 10.8),
  );
  s.smile = smooth(seg(t, 5.95, 6.2)) * (1 - smooth(seg(t, 6.5, 6.7))) + smooth(seg(t, 8.7, 9.2));

  // Arms [forward/up swing, outward splay].
  const armX = track([
    [0, -0.15], [3.3, -0.3], [3.47, -0.8], [3.8, -0.2], [4.55, -0.2], [4.75, -2.5], [5.0, -2.3],
    [5.12, -1.0], [5.7, -1.2], [5.9, -1.35], [6.2, -1.35], [6.5, -2.75], [7.95, -2.75], [8.1, -2.4],
    [8.45, -2.2], [8.7, -0.3], [9.8, -0.3], [12, -0.4],
  ], t);
  const armZ = track([
    [0, 0.2], [4.55, 0.2], [4.75, 0.45], [5.05, 0.25], [5.8, 0.1], [6.2, 0.05], [6.5, 0.25],
    [7.95, 0.25], [8.1, 0.9], [8.45, 0.9], [8.7, 0.25], [12, 0.2],
  ], t);
  const run = env(t, 5.05, 5.15, 5.7, 5.8);
  const swing = 0.5 * Math.sin(t * 28) * run;
  s.armL = [armX + swing, armZ];
  s.armR = [armX - swing, armZ];
  const wave = env(t, 9.7, 9.95, 10.8, 11.1);
  s.armR = [lerp(s.armR[0], -2.75, wave), lerp(s.armR[1], 0.45 + 0.35 * Math.sin(t * 13), wave)];

  // Legs.
  const air = env(t, 6.62, 6.7, 7.1, 7.2) + env(t, 7.52, 7.62, 8.35, 8.5);
  s.legL = 0.8 * Math.sin(t * 28) * run - 0.35 * air;
  s.legR = -0.8 * Math.sin(t * 28) * run - 0.5 * air;

  s.tailPhase = t * 2.4;
  s.tailAmp = 1 + 0.8 * env(t, 4.5, 4.7, 6.0, 6.5) + 0.6 * smooth(seg(t, 9.5, 10));
  return s;
}

function anchorWorld(ms, local) {
  const v = V3(local.x * (1 + 0.5 * ms.sq), local.y * (1 - ms.sq), local.z * (1 + 0.5 * ms.sq));
  v.applyAxisAngle(Y, ms.rotY);
  return v.add(ms.pos);
}

const CHICK_EDGE = V3(0.3, 3.24, 0.2);
const CHICK_BELL = V3(0.22, 0, 0.1);

function chickState(t) {
  const s = { rotX: 0, rotY: 0, rotZ: 0, sq: 0, wingL: 0.15, wingR: 0.15 };
  const flapFast = (amp) => amp * (0.5 + 0.5 * Math.sin(t * 60));
  const tumble = 4 * Math.PI * easeInOut(seg(t, 3.75, 5.9));

  if (t < 3.47) {
    const lean = env(t, 1.0, 1.5, 3.25, 3.47);
    s.pos = NEST_SEAT.clone().add(V3(0.03 * lean, 0.008 * Math.sin(t * 5), 0.05 * lean));
    s.rotX = 0.42 * lean;
    s.rotY = 0.75 * lean;
    s.wingL = s.wingR = 0.15 + 0.1 * Math.sin(t * 4);
  } else if (t < 3.75) {
    const u = seg(t, 3.47, 3.75);
    s.pos = NEST_SEAT.clone();
    s.pos.y += 0.13 * Math.sin(Math.PI * u);
    s.sq = -0.15 * Math.sin(Math.PI * u);
    s.wingL = s.wingR = flapFast(1.1);
    s.rotY = 0.75 * (1 - u);
  } else if (t < 3.9) {
    const u = easeInOut(seg(t, 3.75, 3.9));
    s.pos = NEST_SEAT.clone().lerp(CHICK_EDGE, u);
    s.rotX = tumble;
    s.wingL = s.wingR = flapFast(1.2);
  } else if (t < 4.57) {
    const u = seg(t, 3.9, 4.57);
    s.pos = CHICK_EDGE.clone().lerp(CHICK_BELL, u);
    s.pos.y = arcY(t, 3.9, 4.57, CHICK_EDGE.y, bellTopAt(4.57, 0.15), CHICK_EDGE.y + 0.04);
    s.rotX = tumble;
    s.wingL = s.wingR = flapFast(1.3);
  } else if (t < 5.9) {
    const start = CHICK_BELL.clone();
    start.y = bellTopAt(4.57, 0.15);
    const end = anchorWorld(mimiState(5.9), MIMI_CHEST);
    const u = seg(t, 4.57, 5.9);
    s.pos = start.clone().lerp(end, u);
    s.pos.y = arcY(t, 4.57, 5.9, start.y, end.y, 1.95);
    s.rotX = tumble;
    s.sq = impulse(t, 4.57, 0.6, 9, 22);
    s.wingL = s.wingR = flapFast(0.9) * (1 - 0.6 * u);
    s.rotY = lerp(0, -0.7, u);
  } else {
    const ms = mimiState(t);
    if (t < 6.2) {
      s.pos = anchorWorld(ms, MIMI_CHEST);
      s.rotZ = 0.25 * Math.sin(t * 14) * Math.exp(-6 * (t - 5.9));
      s.rotY = ms.rotY;
      s.sq = impulse(t, 5.9, 0.3, 9, 20);
    } else if (t < 6.6) {
      const u = easeInOut(seg(t, 6.2, 6.6));
      s.pos = anchorWorld(ms, MIMI_CHEST).lerp(anchorWorld(ms, MIMI_HEAD_TOP), u);
      s.pos.y += 0.25 * Math.sin(Math.PI * u);
      s.rotY = ms.rotY;
    } else if (t < 7.98) {
      s.pos = anchorWorld(ms, MIMI_HEAD_TOP);
      s.rotY = ms.rotY;
      s.wingL = s.wingR = 0.2 + flapFast(0.7) * env(t, 7.45, 7.55, 7.9, 7.98);
      s.sq = impulse(t, 6.6, 0.25, 9, 20) + 0.6 * impulse(t, 7.2, 0.3, 9, 20);
    } else if (t < 8.2) {
      const start = anchorWorld(mimiState(7.98), MIMI_HEAD_TOP);
      const u = seg(t, 7.98, 8.2);
      s.pos = start.clone().lerp(NEST_SEAT, u);
      s.pos.y = arcY(t, 7.98, 8.2, start.y, NEST_SEAT.y, NEST_SEAT.y + 0.12);
      s.wingL = s.wingR = flapFast(1.2);
      s.rotY = lerp(ms.rotY, 0.2, u);
    } else {
      s.pos = NEST_SEAT.clone();
      s.pos.y += 0.006 * Math.sin(t * 5);
      s.sq = impulse(t, 8.2, 0.35, 8, 20);
      s.rotX = 0.38 * smooth(seg(t, 8.6, 9.2));
      s.rotY = 0.25;
      const w = env(t, 9.2, 9.4, 10.9, 11.2);
      s.wingR = lerp(0.15, 1.25 + 0.45 * Math.sin(t * 15), w);
      s.wingL = 0.15 + 0.15 * w;
      s.rotZ = -0.08 * w;
    }
  }
  s.eyeOpen = blink(t, 1.9) * blink(t, 2.95) * (1 - 0.0) * blink(t, 6.05, 0.22) * blink(t, 9.0) * blink(t, 10.3) * blink(t, 11.6);
  s.eyeOpen *= 1 - 0.85 * env(t, 4.57, 4.62, 4.75, 4.85); // squeezed on the boing
  return s;
}

// ------------------------------------------------------------- camera
const CAM = [
  [0.0, [2.6, 1.5, 6.4], [0.9, 1.45, 0.0]],
  [2.4, [2.0, 1.1, 4.6], [1.2, 1.0, 0.3]],
  [3.3, [1.7, 1.55, 5.5], [0.85, 1.75, 0.2]],
  [4.4, [1.2, 1.95, 6.6], [0.5, 1.85, 0.0]],
  [6.0, [1.35, 1.35, 5.6], [0.6, 1.2, 0.1]],
  [7.4, [0.95, 2.1, 7.1], [0.3, 1.95, 0.0]],
  [8.3, [0.8, 2.35, 7.0], [0.25, 2.25, 0.0]],
  [10.0, [0.95, 2.25, 6.0], [0.25, 2.15, 0.1]],
  [12.0, [0.6, 2.45, 6.7], [0.2, 2.25, 0.0]],
];
function cameraAt(t) {
  return {
    pos: track(CAM.map((k) => [k[0], k[1]]), t),
    look: track(CAM.map((k) => [k[0], k[2]]), t),
  };
}

// ------------------------------------------------------------- scene
export function createFilm(renderer) {
  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(new THREE.Color(SUPPORT.SKY_HORIZON), 16, 60);

  // Sky dome.
  const sky = new THREE.Mesh(
    new THREE.SphereGeometry(90, 32, 16),
    new THREE.ShaderMaterial({
      side: THREE.BackSide,
      depthWrite: false,
      fog: false,
      uniforms: {
        top: { value: new THREE.Color(SUPPORT.SKY_TOP) },
        horizon: { value: new THREE.Color(SUPPORT.SKY_HORIZON) },
      },
      vertexShader: 'varying vec3 vP; void main(){ vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }',
      fragmentShader:
        'uniform vec3 top; uniform vec3 horizon; varying vec3 vP; void main(){ float h = clamp(normalize(vP).y*1.6, 0.0, 1.0); gl_FragColor = vec4(mix(horizon, top, pow(h,0.8)), 1.0); }',
    }),
  );
  scene.add(sky);

  // Lights.
  scene.add(new THREE.HemisphereLight('#e8f3ff', '#d8c2b4', 0.85));
  const sun = new THREE.DirectionalLight('#fff0dc', 2.5);
  sun.position.set(4, 8, 6);
  sun.target.position.set(0, 1.5, 0);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -6, right: 6, top: 7, bottom: -3, near: 1, far: 30 });
  sun.shadow.bias = -0.0004;
  sun.shadow.normalBias = 0.02;
  scene.add(sun, sun.target);
  const rim = new THREE.DirectionalLight('#ffd9e6', 1.1);
  rim.position.set(-3, 4, -5);
  scene.add(rim);
  const fill = new THREE.DirectionalLight('#cfe4ff', 0.45);
  fill.position.set(-5, 2, 4);
  scene.add(fill);

  // Ground & hills.
  const ground = new THREE.Mesh(new THREE.CircleGeometry(80, 64), felt(SUPPORT.GRASS));
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);
  for (const [x, z, r, c] of [[-14, -22, 11, SUPPORT.HILL], [10, -26, 14, SUPPORT.GRASS_DARK], [26, -18, 10, SUPPORT.HILL], [-30, -12, 12, SUPPORT.GRASS_DARK]]) {
    const h = new THREE.Mesh(new THREE.SphereGeometry(r, 32, 16), felt(c));
    h.scale.y = 0.35;
    h.position.set(x, 0, z);
    scene.add(h);
  }

  // Grass tufts and tiny flowers (instanced).
  const R = rng(3);
  const tuftGeo = new THREE.ConeGeometry(0.022, 0.11, 5);
  tuftGeo.translate(0, 0.055, 0);
  const tufts = new THREE.InstancedMesh(tuftGeo, felt(SUPPORT.GRASS_DARK), 900);
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), sc = new THREE.Vector3();
  for (let i = 0; i < tufts.count; i++) {
    const p = V3(-7 + R() * 15, 0, -6 + R() * 9);
    if (p.distanceTo(V3(FLOWER.x, 0, FLOWER.z)) < 0.75) p.x += 1.6;
    q.setFromEuler(new THREE.Euler((R() - 0.5) * 0.5, R() * 6, (R() - 0.5) * 0.5));
    const k = 0.6 + R() * 0.9;
    sc.set(k, k, k);
    tufts.setMatrixAt(i, m4.compose(p, q, sc));
  }
  tufts.receiveShadow = true;
  scene.add(tufts);
  const daisyGeo = new THREE.SphereGeometry(0.035, 10, 8);
  const daisies = new THREE.InstancedMesh(daisyGeo, felt('#ffffff'), 140);
  const dCols = [PALETTE.WHITE, PALETTE.PETAL, SUPPORT.BEAK, PALETTE.WHITE];
  for (let i = 0; i < daisies.count; i++) {
    const p = V3(-7 + R() * 15, 0.04, -6 + R() * 9);
    daisies.setMatrixAt(i, m4.compose(p, q.identity(), sc.set(1, 0.6, 1)));
    daisies.setColorAt(i, new THREE.Color(dCols[i % dCols.length]));
  }
  scene.add(daisies);

  // Fallen petals on the grass.
  const petalGeo = petalGeometry(0.06);
  const petalMat = felt(PALETTE.PETAL, { side: THREE.DoubleSide });
  const fallen = new THREE.InstancedMesh(petalGeo, petalMat, 160);
  for (let i = 0; i < fallen.count; i++) {
    const a = R() * Math.PI * 2, d = Math.sqrt(R()) * 3.2;
    const p = V3(-1.6 + Math.cos(a) * d * 1.3, 0.012, -0.5 + Math.sin(a) * d);
    q.setFromEuler(new THREE.Euler(-Math.PI / 2, 0, R() * 6));
    fallen.setMatrixAt(i, m4.compose(p, q, sc.set(1, 1, 1)));
  }
  fallen.receiveShadow = true;
  scene.add(fallen);

  // Drifting petals.
  const drift = new THREE.InstancedMesh(petalGeo, petalMat, 70);
  const driftSeeds = Array.from({ length: drift.count }, () => ({
    x: -4.5 + R() * 8, z: -3.5 + R() * 5.5, period: 6 + R() * 5, off: R() * 12,
    f: 0.6 + R(), ph: R() * 6, spin: 1 + R() * 2,
  }));
  scene.add(drift);

  // Set pieces.
  scene.add(buildHeroTree());
  for (const [x, z, s, seed] of [[-6.5, -7, 1.1, 21], [5.2, -8.5, 1.25, 22], [9.5, -5.5, 0.95, 23], [-10.5, -4.5, 1.0, 24], [2.5, -14, 1.4, 25], [-3.5, -16, 1.3, 26], [13, -13, 1.2, 27]]) {
    const tr = buildBackgroundTree(seed);
    tr.position.set(x, 0, z);
    tr.scale.setScalar(s);
    tr.rotation.y = seed;
    scene.add(tr);
  }
  const bell = buildBellFlower();
  bell.root.position.copy(FLOWER);
  scene.add(bell.root);

  const mimi = buildMimi();
  scene.add(mimi.root);
  const chick = buildChick();
  scene.add(chick.root);
  const leaf = buildLeaf();
  scene.add(leaf);

  const camera = new THREE.PerspectiveCamera(38, 16 / 9, 0.1, 200);

  // Nose position at the moment of the sneeze (cached, for the blast path).
  let sneezeNose = null;
  function noseAt(t) {
    poseMimi(mimi, mimiState(t));
    mimi.root.updateMatrixWorld(true);
    return mimi.noseAnchor.getWorldPosition(V3(0, 0, 0));
  }

  const LEAF_START = V3(0.95, 3.7, 0.75);
  const LEAF_RETURN = V3(-0.25, 4.7, 1.1);

  function poseLeaf(t) {
    leaf.visible = true;
    const flutter = (u, k) => leaf.rotation.set(0.7 * Math.sin(u * 9 * k) - 0.4, u * 5 * k, 0.9 * Math.sin(u * 7 * k));
    if (t < 0.5) {
      leaf.position.copy(LEAF_START).add(V3(0, 0.01 * Math.sin(t * 20), 0));
      leaf.rotation.set(-0.4, 0, 0.2 + 0.1 * Math.sin(t * 12));
    } else if (t < 2.6) {
      const u = seg(t, 0.5, 2.6);
      const nose = mimi.noseAnchor.getWorldPosition(V3(0, 0, 0));
      leaf.position.copy(LEAF_START).lerp(nose, smooth(u));
      leaf.position.x += 0.4 * Math.sin(u * Math.PI * 2.5) * (1 - u);
      leaf.position.z += 0.18 * Math.cos(u * Math.PI * 2) * (1 - u);
      flutter(u, 1);
      leaf.rotation.x = lerp(leaf.rotation.x, -0.25, smooth(seg(u, 0.8, 1)));
      leaf.rotation.y = lerp(leaf.rotation.y, mimiState(t).rotY, smooth(seg(u, 0.8, 1)));
      leaf.rotation.z = lerp(leaf.rotation.z, 0.3, smooth(seg(u, 0.8, 1)));
    } else if (t < 3.47) {
      leaf.position.copy(mimi.noseAnchor.getWorldPosition(V3(0, 0, 0)));
      leaf.rotation.set(-0.25 + 0.05 * Math.sin(t * 30), mimiState(t).rotY, 0.3);
    } else if (t < 4.7) {
      const u = seg(t, 3.47, 4.7);
      leaf.position.copy(sneezeNose).lerp(V3(-1.2, 4.9, 3.2), easeOut(u));
      flutter(u, 2.5);
    } else if (t > 9.3 && t < 11.3) {
      const u = seg(t, 9.3, 11.3);
      const top = mimi.headTop.getWorldPosition(V3(0, 0, 0));
      leaf.position.copy(LEAF_RETURN).lerp(top, smooth(u));
      leaf.position.x += 0.35 * Math.sin(u * Math.PI * 2.5) * (1 - u);
      flutter(u, 1);
      const k = smooth(seg(u, 0.8, 1));
      leaf.rotation.set(lerp(leaf.rotation.x, -1.35, k), lerp(leaf.rotation.y, 0.4, k), lerp(leaf.rotation.z, 0.2, k));
    } else if (t >= 11.3) {
      leaf.position.copy(mimi.headTop.getWorldPosition(V3(0, 0, 0)));
      leaf.rotation.set(-1.35, 0.4, 0.2);
    } else leaf.visible = false;
  }

  function renderAt(t) {
    t = clamp(t, 0, DURATION);
    if (!sneezeNose) sneezeNose = noseAt(3.47);

    const s = bellSquash(t);
    bell.squash.scale.set(1 + 0.6 * s, 1 - s, 1 + 0.6 * s);

    poseMimi(mimi, mimiState(t));
    mimi.root.updateMatrixWorld(true);
    poseChick(chick, chickState(t));
    poseLeaf(t);

    for (let i = 0; i < drift.count; i++) {
      const d = driftSeeds[i];
      const u = ((t + d.off) % d.period) / d.period;
      const p = V3(d.x + 0.5 * Math.sin(t * d.f + d.ph) + u * 1.2, 5.4 - u * 5.6, d.z + 0.3 * Math.cos(t * d.f * 0.7 + d.ph));
      q.setFromEuler(new THREE.Euler(t * d.spin + d.ph, t * d.spin * 0.6, Math.sin(t * d.f + d.ph)));
      drift.setMatrixAt(i, m4.compose(p, q, sc.set(1, 1, 1)));
    }
    drift.instanceMatrix.needsUpdate = true;

    const c = globalThis.DEBUG_CAM || cameraAt(t);
    camera.position.set(...c.pos);
    camera.lookAt(...c.look);
    renderer.render(scene, camera);
  }

  return { scene, camera, renderAt, leaf, mimi };
}
