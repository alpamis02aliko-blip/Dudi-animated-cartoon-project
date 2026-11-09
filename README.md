# Mimi and the Bell Flower

A 12-second felt-plush cartoon built in code with three.js. There is no on-screen text.

Mimi, a plush grey kitten, sneezes a cherry petal off her nose. The sneeze startles a baby owl, which tumbles out of its nest. It bounces off a giant rubbery bell flower and lands in Mimi's paws. Mimi puts the chick on her head, bounces off the bell flower and returns it to the nest.

## Beats

| Time (s) | Beat |
|---|---|
| 0.0–2.6 | Spring orchard. A cherry petal drifts down onto Mimi's nose while the chick peeks over the nest edge. |
| 2.6–3.5 | Tickle, inhale, **sneeze**. The petal blasts away. |
| 3.5–4.6 | The startled chick hops, tips over the edge and falls from 3.2 to the flower. |
| 4.6–5.9 | **Boing**: the bell flower squashes and flings the chick; Mimi runs over and catches it. |
| 5.9–7.2 | A cuddle. Mimi puts the chick on her head and hops onto the bell flower. |
| 7.2–8.5 | The bell flower squashes, then launches Mimi. At the top of the jump the chick hops back into its nest. |
| 8.5–12.0 | Mimi lands on the flower and they wave. The petal floats back down onto Mimi's head. |

## Brand

All colours, sizes and the material are defined in `src/brand.js`. Change the values there to re-skin the film.

| Item | Spec |
|---|---|
| HERO | **Mimi** is a plush grey kitten 1.0 tall. Her head is a 0.52-wide sphere on a pear-shaped body, with four stub limbs, 0.2 ears and a 0.7 tail. She has a pink nose and big INK eyes with catchlights. Her rig covers blinks, brows and mouth shapes. Fur is SMOKE, the muzzle and chest are WHITE, and the paws are INK. |
| CHICK | A round PLUM baby owl, 0.22 wide, with a yellow beak, INK dot eyes and wing nubs. |
| LEAF | One cherry petal in PETAL. |
| MUSHROOM | A giant rubbery bell flower in BELL with WHITE spots. Its top is 1.0 high. |
| SET | A spring orchard with a big cherry tree. The nest sits on a branch at 3.2, with the bell flower directly below it. |
| PALETTE | SMOKE `#8C93A3`, WHITE `#F7F3EE`, INK `#15110F`, PLUM `#7B4B94`, PETAL `#F2B5C4`, BELL `#3F7CC9` |
| MATERIAL | Felt plush: `MeshPhysicalMaterial` with sheen 0.8 and roughness 0.75 |

## Run it

The scene needs no build step. three.js r170 is vendored in `vendor/`.

```bash
npm run serve            # then open http://localhost:8080
```

Click the page or press Space to pause.

## Render the MP4

The render script needs Node 18+, Playwright with Chromium, and ffmpeg.

```bash
npm run render           # out/mimi.mp4: 1920x1080, 30 fps, H.264
npm run preview          # out/preview.mp4: 1280x720, 24 fps
npm run stills           # PNG stills at the key beats
node render/render.mjs --stills 3.5 --cam 1.6,1.2,2.5,1.2,0.9,0.4   # debug camera
```

Every pose, prop and camera position is a pure function of time `t`, so the renderer can draw any frame in any order. It calls `window.renderAt(t)` and pipes each frame to ffmpeg.

## Layout

```
index.html          player / render host
src/brand.js        palette, sizes, material (the BRAND sheet)
src/models.js       Mimi, chick, petal, bell flower, cherry trees, nest
src/film.js         set dressing, lighting, beat timeline, camera
src/util.js         easing, envelopes, ballistic arcs, Hermite tracks
render/render.mjs   headless frame capture -> ffmpeg
```
