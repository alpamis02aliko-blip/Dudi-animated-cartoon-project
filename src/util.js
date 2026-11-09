// Small, deterministic animation helpers. Everything in the film is a pure
// function of time t (seconds), so any frame can be rendered in any order.

export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, t) => a + (b - a) * t;
export const seg = (t, a, b) => clamp((t - a) / (b - a));
export const smooth = (x) => x * x * (3 - 2 * x);
export const easeInOut = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
export const easeOut = (x) => 1 - Math.pow(1 - x, 3);
export const easeIn = (x) => x * x * x;

// Trapezoid envelope: ramps up a->b, holds, ramps down c->d.
export const env = (t, a, b, c, d) => smooth(seg(t, a, b)) * (1 - smooth(seg(t, c, d)));

// Damped "boing" that starts at zero at t0 and settles back to zero.
export const impulse = (t, t0, amp, k = 7, w = 18) =>
  t < t0 ? 0 : amp * Math.exp(-k * (t - t0)) * Math.sin(w * (t - t0));

// Blink: 1 = open, dips to 0 around tb.
export const blink = (t, tb, d = 0.16) => 1 - env(t, tb, tb + d * 0.4, tb + d * 0.55, tb + d);

// Ballistic arc that leaves y0 at t0, peaks at H and lands on y1 at t1.
export function arcY(t, t0, t1, y0, y1, H) {
  const D = t1 - t0;
  const a = Math.sqrt(Math.max(H - y0, 1e-6));
  const b = Math.sqrt(Math.max(H - y1, 1e-6));
  const g = (2 * (a + b) ** 2) / (D * D);
  const ta = (D * a) / (a + b);
  const dt = t - t0;
  return H - 0.5 * g * (dt - ta) ** 2;
}

// Non-uniform Catmull-Rom / cubic Hermite through [time, value] keys.
// value may be a number or an array of numbers.
export function track(keys, t) {
  const n = keys.length;
  if (t <= keys[0][0]) return keys[0][1];
  if (t >= keys[n - 1][0]) return keys[n - 1][1];
  let i = 0;
  while (i < n - 2 && t > keys[i + 1][0]) i++;
  const [t0, p0] = keys[i];
  const [t1, p1] = keys[i + 1];
  const prev = keys[Math.max(0, i - 1)];
  const next = keys[Math.min(n - 1, i + 2)];
  const h = t1 - t0;
  const u = (t - t0) / h;
  const h00 = 2 * u ** 3 - 3 * u ** 2 + 1;
  const h10 = u ** 3 - 2 * u ** 2 + u;
  const h01 = -2 * u ** 3 + 3 * u ** 2;
  const h11 = u ** 3 - u ** 2;
  const tan = (a, b, ta, tb) => (ta === tb ? 0 : (b - a) / (tb - ta));
  const one = (a0, a1, ap, an) => {
    const m0 = i === 0 ? 0 : tan(ap, a1, prev[0], t1);
    const m1 = i + 2 >= n ? 0 : tan(a0, an, t0, next[0]);
    return h00 * a0 + h10 * h * m0 + h01 * a1 + h11 * h * m1;
  };
  if (Array.isArray(p0)) return p0.map((_, k) => one(p0[k], p1[k], prev[1][k], next[1][k]));
  return one(p0, p1, prev[1], next[1]);
}

// Seeded PRNG so set dressing is identical every run.
export function rng(seed = 1) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let r = Math.imul(s ^ (s >>> 15), 1 | s);
    r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}
