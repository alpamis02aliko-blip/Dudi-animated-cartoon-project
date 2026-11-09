import * as THREE from '../vendor/three.module.js';
import { PALETTE, SUPPORT, MATERIAL } from './brand.js';
import { rng } from './util.js';

const V3 = (x, y, z) => new THREE.Vector3(x, y, z);

// ---------------------------------------------------------------- materials
const matCache = new Map();
export function felt(hex, extra = {}) {
  const key = hex + JSON.stringify(extra);
  if (matCache.has(key)) return matCache.get(key);
  const color = new THREE.Color(hex);
  const m = new THREE.MeshPhysicalMaterial({
    color,
    roughness: MATERIAL.roughness,
    sheen: MATERIAL.sheen,
    sheenRoughness: 0.45,
    sheenColor: color.clone().lerp(new THREE.Color('#ffffff'), 0.3),
    ...extra,
  });
  matCache.set(key, m);
  return m;
}

const glossyInk = () =>
  new THREE.MeshPhysicalMaterial({
    color: new THREE.Color(PALETTE.INK),
    roughness: 0.18,
    clearcoat: 1,
    clearcoatRoughness: 0.08,
  });

function mesh(geo, mat, { cast = true, receive = true } = {}) {
  const m = new THREE.Mesh(geo, mat);
  m.castShadow = cast;
  m.receiveShadow = receive;
  return m;
}
const sphere = (r, mat, seg = 32) => mesh(new THREE.SphereGeometry(r, seg, Math.round(seg * 0.75)), mat);

// Orient obj so its +Z points along the outward direction `dir` from the origin.
function faceOut(obj, dir) {
  obj.lookAt(obj.position.clone().add(dir));
}

// ------------------------------------------------------------------- petal
export function petalGeometry(size = 1) {
  const s = new THREE.Shape();
  s.moveTo(0, 0);
  s.bezierCurveTo(-0.62, 0.28, -0.55, 0.92, -0.14, 1.0);
  s.lineTo(0, 0.86);
  s.lineTo(0.14, 1.0);
  s.bezierCurveTo(0.55, 0.92, 0.62, 0.28, 0, 0);
  const g = new THREE.ShapeGeometry(s, 16);
  const p = g.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), y = p.getY(i);
    p.setZ(i, 0.35 * x * x - 0.12 * y * y); // cupped, gently bent
  }
  g.translate(0, -0.5, 0);
  g.scale(size, size, size);
  g.computeVertexNormals();
  return g;
}

export function buildLeaf() {
  const m = mesh(petalGeometry(0.12), felt(PALETTE.PETAL, { side: THREE.DoubleSide }));
  const g = new THREE.Group();
  g.add(m);
  return g;
}

// -------------------------------------------------------------------- Mimi
export const MIMI_CHEST = V3(0, 0.33, 0.3); // where Mimi holds the chick (root-local)
export const MIMI_HEAD_TOP = V3(0, 0.9, -0.02); // where the chick rides (root-local)

export function buildMimi() {
  const fur = felt(PALETTE.SMOKE);
  const white = felt(PALETTE.WHITE);
  const ink = felt(PALETTE.INK);
  const nose = felt(SUPPORT.NOSE);
  const pink = felt(PALETTE.PETAL);
  const eyeMat = glossyInk();
  const shine = new THREE.MeshBasicMaterial({ color: '#ffffff' });

  const root = new THREE.Group();
  root.name = 'Mimi';

  // Pear body.
  const prof = [
    [0.0, 0.07], [0.16, 0.085], [0.225, 0.17], [0.232, 0.25], [0.205, 0.35],
    [0.155, 0.44], [0.105, 0.52], [0.0, 0.555],
  ].map(([x, y]) => new THREE.Vector2(x, y));
  const bodyPts = new THREE.SplineCurve(prof).getPoints(48).map((p) => new THREE.Vector2(Math.max(0, p.x), p.y));
  root.add(mesh(new THREE.LatheGeometry(bodyPts, 48), fur));

  const chest = sphere(0.135, white);
  chest.scale.set(1, 1.25, 0.55);
  chest.position.set(0, 0.28, 0.17);
  root.add(chest);

  // Stub legs with INK paws.
  const legs = [];
  for (const s of [-1, 1]) {
    const leg = new THREE.Group();
    leg.position.set(s * 0.1, 0.12, 0.04);
    const thigh = mesh(new THREE.CapsuleGeometry(0.065, 0.04, 6, 16), fur);
    thigh.position.y = -0.03;
    leg.add(thigh);
    const paw = sphere(0.07, ink, 24);
    paw.scale.set(1, 0.7, 1.25);
    paw.position.set(0, -0.075, 0.03);
    leg.add(paw);
    root.add(leg);
    legs.push(leg);
  }

  // Stub arms with INK paws.
  const arms = [];
  for (const s of [-1, 1]) {
    const arm = new THREE.Group();
    arm.position.set(s * 0.185, 0.4, 0.03);
    const a = mesh(new THREE.CapsuleGeometry(0.05, 0.08, 6, 16), fur);
    a.position.y = -0.07;
    arm.add(a);
    const paw = sphere(0.058, ink, 24);
    paw.position.y = -0.15;
    arm.add(paw);
    root.add(arm);
    arms.push(arm);
  }

  // Tail — rebuilt each frame from a swaying curve.
  const tailMat = fur;
  const tail = mesh(new THREE.BufferGeometry(), tailMat);
  const tailTip = sphere(0.045, fur, 16);
  root.add(tail, tailTip);

  // Head.
  const headPivot = new THREE.Group();
  headPivot.position.y = 0.5;
  root.add(headPivot);
  const head = new THREE.Group();
  head.position.y = 0.16; // head centre at 0.66, top at 0.92
  headPivot.add(head);
  head.add(sphere(0.26, fur, 48));

  const R = 0.26;
  const onHead = (x, y) => Math.sqrt(Math.max(0, R * R - x * x - y * y));

  for (const s of [-1, 1]) {
    const cheek = sphere(0.075, white);
    cheek.scale.set(1, 0.85, 0.75);
    cheek.position.set(s * 0.048, -0.085, 0.205);
    head.add(cheek);
  }
  const chin = sphere(0.05, white);
  chin.position.set(0, -0.13, 0.19);
  head.add(chin);

  const noseM = sphere(0.032, nose);
  noseM.scale.set(1.35, 0.85, 0.85);
  noseM.position.set(0, -0.045, 0.252);
  head.add(noseM);
  const noseAnchor = new THREE.Object3D();
  noseAnchor.position.set(0, -0.035, 0.285);
  head.add(noseAnchor);

  // Mouth: closed cat smile + open shape.
  const smileCurve = new THREE.CatmullRomCurve3([
    V3(-0.052, -0.108, 0.25), V3(-0.026, -0.128, 0.257), V3(0, -0.112, 0.262),
    V3(0.026, -0.128, 0.257), V3(0.052, -0.108, 0.25),
  ]);
  const smile = mesh(new THREE.TubeGeometry(smileCurve, 32, 0.0075, 8), ink, { cast: false });
  head.add(smile);
  const mouthOpen = sphere(0.05, ink, 24);
  mouthOpen.position.set(0, -0.135, 0.235);
  head.add(mouthOpen);
  const tongue = sphere(0.03, pink, 16);
  tongue.position.set(0, -0.03, 0.02);
  mouthOpen.add(tongue);

  // Big INK eyes with catchlights.
  const eyes = [];
  for (const s of [-1, 1]) {
    const x = s * 0.098, y = 0.02;
    const eye = new THREE.Group();
    const dir = V3(x, y, onHead(x, y)).normalize();
    eye.position.copy(dir.clone().multiplyScalar(0.236));
    faceOut(eye, dir);
    const ball = sphere(0.068, eyeMat, 32);
    ball.scale.set(0.86, 1.06, 0.5);
    eye.add(ball);
    const c1 = sphere(0.019, shine, 12);
    c1.position.set(-0.022, 0.03, 0.03);
    const c2 = sphere(0.009, shine, 8);
    c2.position.set(0.02, -0.025, 0.03);
    eye.add(c1, c2);
    eye.userData.base = eye.position.clone();
    head.add(eye);
    eyes.push(eye);
  }

  // Brows.
  const brows = [];
  for (const s of [-1, 1]) {
    const x = s * 0.1, y = 0.125;
    const brow = new THREE.Group();
    const dir = V3(x, y, onHead(x, y)).normalize();
    brow.position.copy(dir.clone().multiplyScalar(0.262));
    faceOut(brow, dir);
    const b = mesh(new THREE.CapsuleGeometry(0.011, 0.045, 4, 10), ink, { cast: false });
    b.rotation.z = Math.PI / 2;
    brow.add(b);
    brow.userData.base = brow.position.clone();
    brow.userData.baseQ = brow.quaternion.clone();
    head.add(brow);
    brows.push(brow);
  }

  // Ears 0.2 tall.
  for (const s of [-1, 1]) {
    const ear = new THREE.Group();
    ear.position.set(s * 0.14, 0.165, -0.02);
    ear.rotation.z = -s * 0.42;
    const outer = mesh(new THREE.ConeGeometry(0.088, 0.2, 24), fur);
    outer.scale.z = 0.6;
    outer.position.y = 0.07;
    const inner = mesh(new THREE.ConeGeometry(0.052, 0.13, 20), pink, { cast: false });
    inner.scale.z = 0.4;
    inner.position.set(0, 0.055, 0.03);
    ear.add(outer, inner);
    head.add(ear);
  }

  // Whiskers: three fine INK strokes per side.
  for (const s of [-1, 1]) {
    for (let k = 0; k < 2; k++) {
      const c = new THREE.QuadraticBezierCurve3(
        V3(s * 0.1, -0.075 - k * 0.025, 0.23),
        V3(s * 0.18, -0.07 - k * 0.03, 0.22),
        V3(s * 0.25, -0.06 - k * 0.05, 0.16),
      );
      head.add(mesh(new THREE.TubeGeometry(c, 12, 0.003, 4), ink, { cast: false }));
    }
  }

  const headTop = new THREE.Object3D();
  headTop.position.set(0.03, 0.272, 0.06);
  head.add(headTop);

  return { root, legs, arms, tail, tailTip, headPivot, head, eyes, brows, smile, mouthOpen, noseAnchor, headTop };
}

export function poseMimi(M, s) {
  M.root.position.copy(s.pos);
  M.root.rotation.set(0, s.rotY, s.lean || 0);
  M.root.scale.set(1 + 0.5 * s.sq, 1 - s.sq, 1 + 0.5 * s.sq);

  M.headPivot.rotation.set(s.pitch, s.yaw, s.roll);

  const open = Math.max(0.06, s.eyeOpen);
  M.eyes.forEach((e, i) => {
    const side = i === 0 ? -1 : 1;
    e.scale.set(s.eyeWide, open * s.eyeWide, 1);
    e.position.copy(e.userData.base);
    e.position.x -= side * 0.012 * s.cross;
    e.position.y += 0.006 * (s.eyeWide - 1) * 10;
  });
  M.brows.forEach((b, i) => {
    const side = i === 0 ? -1 : 1;
    b.position.copy(b.userData.base);
    b.position.y += 0.03 * s.browUp;
    b.quaternion.copy(b.userData.baseQ);
    b.rotateZ(side * (0.35 * s.browWorry));
  });

  const o = s.mouthOpen;
  M.mouthOpen.visible = o > 0.04;
  M.mouthOpen.scale.set(0.55 + 0.55 * o, 0.15 + 0.95 * o, 0.45);
  M.smile.visible = o < 0.3;
  M.smile.scale.set(1 + 0.15 * s.smile, 1 + 0.6 * s.smile, 1);

  const [aL, aR] = M.arms;
  aL.rotation.set(s.armL[0], 0, -s.armL[1]);
  aR.rotation.set(s.armR[0], 0, s.armR[1]);
  M.legs[0].rotation.set(s.legL, 0, -0.05);
  M.legs[1].rotation.set(s.legR, 0, 0.05);

  // Tail (0.7 long), curled up behind.
  const ph = s.tailPhase, a = s.tailAmp;
  const pts = [
    V3(0, 0.14, -0.19),
    V3(0.04 + 0.04 * Math.sin(ph), 0.11, -0.36),
    V3(0.1 + 0.09 * Math.sin(ph + 0.5) * a, 0.25, -0.48),
    V3(0.13 + 0.14 * Math.sin(ph + 1.0) * a, 0.44, -0.47),
    V3(0.08 + 0.18 * Math.sin(ph + 1.5) * a, 0.58, -0.37),
  ];
  const curve = new THREE.CatmullRomCurve3(pts);
  M.tail.geometry.dispose();
  M.tail.geometry = new THREE.TubeGeometry(curve, 40, 0.045, 12);
  M.tailTip.position.copy(pts[4]);
}

// ------------------------------------------------------------------- Chick
export function buildChick() {
  const plum = felt(PALETTE.PLUM);
  const face = felt(new THREE.Color(PALETTE.PLUM).lerp(new THREE.Color(PALETTE.WHITE), 0.45).getStyle());
  const beak = felt(SUPPORT.BEAK);
  const eyeMat = glossyInk();
  const shine = new THREE.MeshBasicMaterial({ color: '#ffffff' });

  const root = new THREE.Group();
  root.name = 'Chick';
  const bodyG = new THREE.Group();
  root.add(bodyG);
  const body = sphere(0.11, plum, 32);
  body.position.y = 0.11;
  bodyG.add(body);

  const eyes = [];
  for (const s of [-1, 1]) {
    const disc = sphere(0.045, face, 20);
    disc.scale.set(1, 1, 0.4);
    const dir = V3(s * 0.042, 0.025, 0.1).normalize();
    disc.position.copy(dir.clone().multiplyScalar(0.098)).add(V3(0, 0.11, 0));
    faceOut(disc, dir);
    bodyG.add(disc);
    const eye = new THREE.Group();
    eye.position.copy(dir.clone().multiplyScalar(0.112)).add(V3(0, 0.11, 0));
    faceOut(eye, dir);
    const dot = sphere(0.021, eyeMat, 16);
    dot.scale.z = 0.6;
    const c = sphere(0.006, shine, 8);
    c.position.set(-0.007, 0.008, 0.012);
    eye.add(dot, c);
    bodyG.add(eye);
    eyes.push(eye);
  }

  const bk = mesh(new THREE.ConeGeometry(0.018, 0.04, 12), beak);
  bk.position.set(0, 0.095, 0.112);
  bk.rotation.x = Math.PI * 0.62;
  bodyG.add(bk);

  for (const s of [-1, 1]) {
    const tuft = mesh(new THREE.ConeGeometry(0.022, 0.05, 10), plum);
    tuft.position.set(s * 0.055, 0.215, 0);
    tuft.rotation.z = -s * 0.45;
    bodyG.add(tuft);
    const foot = sphere(0.016, beak, 10);
    foot.scale.set(1.2, 0.6, 1.4);
    foot.position.set(s * 0.035, 0.008, 0.06);
    bodyG.add(foot);
  }

  const wings = [];
  for (const s of [-1, 1]) {
    const w = new THREE.Group();
    w.position.set(s * 0.1, 0.12, 0);
    const nub = sphere(0.045, plum, 16);
    nub.scale.set(0.45, 1, 0.8);
    nub.position.set(s * 0.012, -0.03, 0);
    w.add(nub);
    bodyG.add(w);
    wings.push(w);
  }

  // Re-centre so the body tumbles around its middle.
  bodyG.children.forEach((c) => (c.position.y -= 0.11));
  bodyG.position.y = 0.11;
  return { root, bodyG, eyes, wings };
}

export function poseChick(C, s) {
  C.root.visible = true;
  C.root.position.copy(s.pos);
  C.root.rotation.set(0, s.rotY, 0);
  C.bodyG.rotation.set(s.rotX, 0, s.rotZ);
  C.bodyG.scale.set(1 + 0.5 * s.sq, 1 - s.sq, 1 + 0.5 * s.sq);
  C.eyes.forEach((e) => (e.scale.y = Math.max(0.1, s.eyeOpen)));
  C.wings[0].rotation.z = -s.wingL;
  C.wings[1].rotation.z = s.wingR;
}

// --------------------------------------------------------- Bell "mushroom"
const BELL_OUTER = [
  [0.72, 0.53], [0.66, 0.585], [0.58, 0.66], [0.52, 0.78], [0.42, 0.9], [0.25, 0.98], [0.0, 1.0],
];
export function bellCapHeight(r) {
  // Outer dome height at radius r (unsquashed).
  for (let i = BELL_OUTER.length - 1; i > 0; i--) {
    const [r0, y0] = BELL_OUTER[i];
    const [r1, y1] = BELL_OUTER[i - 1];
    if (r >= r0 && r <= r1) return y0 + ((r - r0) / (r1 - r0)) * (y1 - y0);
  }
  return 0.53;
}

export function buildBellFlower() {
  const bell = felt(PALETTE.BELL, { side: THREE.DoubleSide, sheenRoughness: 0.35 });
  const white = felt(PALETTE.WHITE);
  const stem = felt(SUPPORT.STEM);

  const root = new THREE.Group();
  root.name = 'BellFlower';
  const squash = new THREE.Group();
  root.add(squash);

  const stemCurve = new THREE.CatmullRomCurve3([V3(0, 0, 0), V3(0.03, 0.25, 0.01), V3(-0.01, 0.5, 0), V3(0, 0.74, 0)]);
  squash.add(mesh(new THREE.TubeGeometry(stemCurve, 24, 0.065, 14), stem));

  // Bell cap: inner surface top->rim, then outer surface rim->top (outward normals).
  const prof = [
    [0.0, 0.76], [0.24, 0.74], [0.42, 0.67], [0.53, 0.585], [0.61, 0.525], [0.68, 0.5],
    ...BELL_OUTER,
  ].map(([x, y]) => new THREE.Vector2(x, y));
  const pts = new THREE.SplineCurve(prof).getPoints(90).map((p) => new THREE.Vector2(Math.max(0, p.x), p.y));
  const cap = mesh(new THREE.LatheGeometry(pts, 64), bell);
  squash.add(cap);

  // Little clapper inside the bell.
  const clap = sphere(0.07, felt(SUPPORT.BEAK), 16);
  clap.position.y = 0.56;
  squash.add(clap);

  // WHITE spots on the outer dome.
  const outer = new THREE.SplineCurve(BELL_OUTER.map(([x, y]) => new THREE.Vector2(x, y)));
  const R = rng(7);
  const spots = [
    [0.12, 0.3], [0.2, 1.4], [0.18, 2.6], [0.15, 3.9], [0.22, 5.1],
    [0.42, 0.9], [0.45, 2.0], [0.4, 3.2], [0.47, 4.4], [0.43, 5.6],
    [0.68, 0.2], [0.7, 1.5], [0.66, 2.7], [0.72, 4.0], [0.69, 5.2],
  ];
  for (const [u, th] of spots) {
    const p = outer.getPoint(u);
    const tg = outer.getTangent(u);
    const n2 = new THREE.Vector2(-tg.y, tg.x); // outward for rim->top order
    if (n2.y < 0) n2.multiplyScalar(-1);
    const n = V3(n2.x * Math.cos(th), n2.y, n2.x * Math.sin(th)).normalize();
    const spot = sphere(0.06 + R() * 0.03, white, 16);
    spot.scale.z = 0.22;
    spot.position.set(p.x * Math.cos(th), p.y, p.x * Math.sin(th)).addScaledVector(n, 0.004);
    faceOut(spot, n);
    squash.add(spot);
  }

  // Leaves at the base.
  for (const [a, l] of [[0.6, 0.42], [2.5, 0.36], [4.3, 0.4]]) {
    const leaf = sphere(0.1, stem, 20);
    leaf.scale.set(l / 0.1, 0.18, 0.8);
    leaf.position.set(Math.cos(a) * l * 0.85, 0.03, Math.sin(a) * l * 0.85);
    leaf.rotation.y = -a;
    leaf.rotation.z = 0.15;
    root.add(leaf);
  }

  return { root, squash };
}

// ---------------------------------------------------------------- Set
function blossomCloud(group, center, radii, count, minR, maxR, seed, avoid = []) {
  const R = rng(seed);
  const cols = [PALETTE.PETAL, SUPPORT.BLOSSOM_LIGHT, SUPPORT.BLOSSOM_DEEP, PALETTE.PETAL];
  let placed = 0, guard = 0;
  while (placed < count && guard++ < count * 20) {
    const p = V3(
      center.x + (R() * 2 - 1) * radii.x,
      center.y + (R() * 2 - 1) * radii.y,
      center.z + (R() * 2 - 1) * radii.z,
    );
    const q = V3((p.x - center.x) / radii.x, (p.y - center.y) / radii.y, (p.z - center.z) / radii.z);
    if (q.lengthSq() > 1) continue;
    const r = minR + R() * (maxR - minR);
    if (avoid.some(([c, d]) => p.distanceTo(c) < d + r)) continue;
    const s = sphere(r, felt(cols[Math.floor(R() * cols.length)]), 24);
    s.position.copy(p);
    s.scale.y = 0.85;
    group.add(s);
    placed++;
  }
}

export function buildHeroTree() {
  const g = new THREE.Group();
  const bark = felt(SUPPORT.BARK);
  const trunkCurve = new THREE.CatmullRomCurve3([
    V3(-1.9, -0.05, -0.75), V3(-1.82, 1.4, -0.72), V3(-1.62, 2.8, -0.68), V3(-1.75, 4.2, -0.8),
  ]);
  g.add(mesh(new THREE.TubeGeometry(trunkCurve, 32, 0.27, 20), bark));
  const flare = mesh(new THREE.ConeGeometry(0.5, 0.6, 24, 1, true), bark);
  flare.position.set(-1.9, 0.25, -0.75);
  g.add(flare);

  // Branch out to the nest.
  const branch = new THREE.CatmullRomCurve3([
    V3(-1.7, 2.75, -0.68), V3(-1.05, 3.02, -0.38), V3(-0.35, 3.02, -0.08), V3(0.2, 3.04, 0.0), V3(0.62, 3.16, 0.04),
  ]);
  g.add(mesh(new THREE.TubeGeometry(branch, 40, 0.07, 12), bark));
  const tip = sphere(0.05, bark, 12);
  tip.position.set(0.62, 3.16, 0.04);
  g.add(tip);
  const upper = new THREE.CatmullRomCurve3([V3(-1.7, 3.6, -0.75), V3(-2.6, 4.3, -1.0), V3(-3.2, 4.6, -1.2)]);
  g.add(mesh(new THREE.TubeGeometry(upper, 20, 0.11, 10), bark));
  const upper2 = new THREE.CatmullRomCurve3([V3(-1.7, 3.8, -0.75), V3(-0.9, 4.3, -0.9), V3(-0.2, 4.6, -1.1)]);
  g.add(mesh(new THREE.TubeGeometry(upper2, 20, 0.1, 10), bark));

  const nestC = V3(0.2, 3.2, 0.0);
  blossomCloud(g, V3(-1.6, 4.75, -1.0), V3(2.3, 0.85, 1.1), 46, 0.35, 0.75, 11, [[nestC, 0.95]]);
  blossomCloud(g, V3(-0.6, 3.25, -0.2), V3(1.0, 0.18, 0.25), 9, 0.1, 0.17, 12, [[nestC, 0.42]]);
  blossomCloud(g, V3(-2.0, 3.2, -0.6), V3(0.5, 0.4, 0.4), 6, 0.15, 0.3, 13, []);

  // Nest.
  const straw = felt(SUPPORT.STRAW);
  const nest = new THREE.Group();
  nest.position.set(0.2, 3.13, 0);
  const ring = mesh(new THREE.TorusGeometry(0.165, 0.07, 14, 32), straw);
  ring.rotation.x = Math.PI / 2;
  ring.position.y = 0.03;
  const bowl = sphere(0.2, straw, 24);
  bowl.scale.set(1, 0.32, 1);
  nest.add(ring, bowl);
  const R = rng(5);
  for (let i = 0; i < 14; i++) {
    const a = (i / 14) * Math.PI * 2 + R();
    const twig = mesh(new THREE.CylinderGeometry(0.008, 0.008, 0.16, 5), felt(SUPPORT.BARK));
    twig.position.set(Math.cos(a) * 0.2, 0.02 + R() * 0.04, Math.sin(a) * 0.2);
    twig.rotation.set(R() * 0.6, -a, Math.PI / 2 + (R() - 0.5) * 0.5);
    nest.add(twig);
  }
  g.add(nest);
  return g;
}

export function buildBackgroundTree(seed) {
  const g = new THREE.Group();
  const bark = felt(SUPPORT.BARK);
  const trunk = mesh(new THREE.CylinderGeometry(0.16, 0.26, 2.6, 12), bark);
  trunk.position.y = 1.3;
  g.add(trunk);
  blossomCloud(g, V3(0, 3.0, 0), V3(1.5, 0.9, 1.2), 16, 0.45, 0.85, seed);
  return g;
}
