// Renders the film frame-by-frame in headless Chromium and encodes an H.264 MP4.
//
//   node render/render.mjs                      -> out/mimi.mp4 (1920x1080, 30 fps)
//   node render/render.mjs --w 1280 --h 720 --fps 24 --out out/preview.mp4
//   node render/render.mjs --stills 0,3.5,8      -> out/still_<t>.png only
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { extname, join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = Object.fromEntries(
  process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? [...a, [v.slice(2), arr[i + 1]]] : a), []),
);
const W = +(args.w || 1920), H = +(args.h || 1080), FPS = +(args.fps || 30);
const OUT = resolve(ROOT, args.out || 'out/mimi.mp4');

const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript' };
const server = createServer(async (req, res) => {
  try {
    const p = join(ROOT, decodeURIComponent(new URL(req.url, 'http://x').pathname));
    const body = await readFile(p.endsWith('/') ? p + 'index.html' : p);
    res.writeHead(200, { 'content-type': TYPES[extname(p)] || 'application/octet-stream' });
    res.end(body);
  } catch {
    res.writeHead(404).end();
  }
}).listen(0);
const port = server.address().port;

const browser = await chromium.launch({
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
page.on('console', (m) => m.type() === 'error' && console.error('[page]', m.text()));
page.on('pageerror', (e) => console.error('[page]', e.message));
await page.goto(`http://localhost:${port}/index.html?render&w=${W}&h=${H}`);
await page.waitForFunction('window.ready === true', null, { timeout: 120000 });
const duration = await page.evaluate('window.DURATION');
const canvas = await page.$('canvas');

const debugCam = args.cam ? (([a, b, c, d, e, f]) => ({ pos: [a, b, c], look: [d, e, f] }))(args.cam.split(',').map(Number)) : null;
async function frame(t) {
  await page.evaluate(([t, cam]) => window.renderAt(t, cam), [t, debugCam]);
  return canvas.screenshot({ type: 'png' });
}

await mkdir(dirname(OUT), { recursive: true });

if (args.stills) {
  const { writeFile } = await import('node:fs/promises');
  for (const t of args.stills.split(',').map(Number)) {
    const f = resolve(dirname(OUT), `still_${t.toFixed(2)}.png`);
    await writeFile(f, await frame(t));
    console.log('wrote', f);
  }
} else {
  const total = Math.round(duration * FPS) + 1;
  const ff = spawn('ffmpeg', [
    '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', OUT,
  ], { stdio: ['pipe', 'inherit', 'inherit'] });
  const t0 = Date.now();
  for (let i = 0; i < total; i++) {
    const buf = await frame(i / FPS);
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
    if (i % 15 === 0) {
      const el = (Date.now() - t0) / 1000;
      console.log(`frame ${i + 1}/${total}  ${(el / (i + 1)).toFixed(2)}s/frame`);
    }
  }
  ff.stdin.end();
  await new Promise((r) => ff.on('close', r));
  console.log('wrote', OUT);
}

await browser.close();
server.close();
