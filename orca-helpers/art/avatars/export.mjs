// Exports every avatar in avatars.px.js to orca-helpers/hooks/assets/avatars/:
//   <name>.png  transparent PNG; animated avatars are a horizontal frame strip
//   <name>_<n>.png  one PNG per frame, for the terminal Image, which cannot crop a strip
//   <name>_<n>.svg  one SVG per frame, the same pixels as <rect> elements (Desktop app has no Image element;
//     its Svg source is capped at 131072 chars, so a frame strip cannot be one SVG)
//   manifest.json  { <name>: { w, h, frames, ms } }, ms = per-frame durations
// Names are <id>_<state> for the 48x53 Prompt Band states (drawn 48x64, cropped) and <id>_<state>_<mood>_<size> for
// the Wave Band states (todo, progress, complete) at 18 and 24; see moodState() in base.px.js.
// Run: node export.mjs [file.px.js]
import { loadProject, writePng, Img, toHex } from "../../../.claude/skills/claude-pxl/src/index.ts";
import { mkdirSync, writeFileSync } from "node:fs";

const here = new URL(".", import.meta.url).pathname;
const out = here + "../../hooks/assets/avatars/";
const p = loadProject(process.argv[2] || here + "avatars.px.js");
mkdirSync(out, { recursive: true });

// Horizontal runs of one color per row become one <rect>.
function svg(img) {
  const r = [];
  for (let y = 0; y < img.h; y++) {
    for (let x = 0; x < img.w; ) {
      const c = img.data[y * img.w + x];
      let n = 1;
      while (x + n < img.w && img.data[y * img.w + x + n] === c) n++;
      if (c & 255) r.push(`<rect x="${x}" y="${y}" width="${n}" height="1" fill="${toHex(c)}"/>`);
      x += n;
    }
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${img.w} ${img.h}" width="${img.w}" height="${img.h}" shape-rendering="crispEdges">${r.join("")}</svg>\n`;
}

// The 48x64 Prompt Band states lose their top CROP px, the headroom no frame draws in,
// so the Avatars sit 5 cells tall with no blank row above them (#176). A frame that
// draws there stops the export rather than lose pixels.
const CROP = 11;
function crop(name, img, i) {
  if (img.w !== 48 || img.h !== 64) return img;
  const top = img.data.subarray(0, CROP * img.w).findIndex((c) => c & 255);
  if (top !== -1) throw new Error(`${name}_${i} draws at y ${Math.floor(top / img.w)}, above the ${CROP}px crop`);
  const out = new Img(img.w, img.h - CROP);
  out.data.set(img.data.subarray(CROP * img.w));
  return out;
}

const manifest = {};
for (const name of p.exported()) {
  const fr = p.frames(name);
  const imgs = (fr.length ? fr.map((f) => f.img) : [p.image(name)]).map((img, i) => crop(name, img, i));
  const { w, h } = imgs[0];
  const strip = new Img(w * imgs.length, h);
  imgs.forEach((img, i) => { for (let y = 0; y < h; y++) strip.data.set(img.data.subarray(y * w, y * w + w), y * strip.w + i * w); });
  writePng(out + name + ".png", strip);
  imgs.forEach((img, i) => { writePng(out + `${name}_${i}.png`, img); writeFileSync(out + `${name}_${i}.svg`, svg(img)); });
  manifest[name] = { w, h, frames: imgs.length, ms: fr.length ? fr.map((f) => f.ms) : [] };
}
writeFileSync(out + "manifest.json", "{\n" + Object.entries(manifest).map(([k, v]) => ` "${k}": ${JSON.stringify(v)}`).join(",\n") + "\n}\n");
console.log(`exported ${Object.keys(manifest).length} avatars to ${out}`);
