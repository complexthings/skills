// Writes out/png/<name>.png for every avatar: static sprites copied, anims as frame 0.
// Run after `pxl build avatars.px.js --out out`: node png.mjs
import { loadProject, writePng } from "../../../../.claude/skills/claude-pxl/src/index.ts";
import { readdirSync, copyFileSync, mkdirSync } from "node:fs";
const d = new URL(".", import.meta.url).pathname;
const p = loadProject(d + "avatars.px.js");
mkdirSync(d + "out/png", { recursive: true });
for (const f of readdirSync(d + "out/sprites")) copyFileSync(d + "out/sprites/" + f, d + "out/png/" + f);
for (const f of readdirSync(d + "out/anims").filter((f) => f.endsWith(".png"))) writePng(d + "out/png/" + f, p.image(f.slice(0, -4)));
