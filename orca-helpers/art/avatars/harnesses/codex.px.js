// Codex: the Codex logo as a character. The gradient cloud is the whole body, two stubby feet
// under it, and the white ">_" prompt is its face. No legs, arms, torso or eyes.
// codexCloud is shared with codex/{todo,progress,complete}.px.js so every Codex avatar keeps one body.

// The logo gradient, top to bottom. A Mood swaps in its own light/mid/dark stops.
const CODEX_P = { l: "#B0A8FF", m: "#7A9CFF", d: "#3A48FF" }
const CODEX_OUT = "#16124A"
const mixHex = (a, b, t) => {
  const A = parseInt(a.slice(1, 7), 16), B = parseInt(b.slice(1, 7), 16)
  const ch = (s) => Math.round(((A >> s) & 255) * (1 - t) + ((B >> s) & 255) * t)
  return "#" + [16, 8, 0].map((s) => ch(s).toString(16).padStart(2, "0")).join("")
}
// n flat bands from P.l through P.m to P.d.
const codexBands = (P, n) => [...Array(n)].map((_, i) => {
  const t = n === 1 ? 0 : i / (n - 1)
  return t < 0.5 ? mixHex(P.l, P.m, t * 2) : mixHex(P.m, P.d, t * 2 - 1)
})

// Cloud outline in unit space: a core plus 7 bumps, like the logo's scalloped flower.
const CODEX_BUMPS = [...Array(7)].map((_, k) => { const a = -Math.PI / 2 + (k + 0.15) * 2 * Math.PI / 7; return [0.56 * Math.cos(a), 0.56 * Math.sin(a), 0.43] })
const codexInside = (nx, ny) => Math.hypot(nx, ny) <= 0.52 || CODEX_BUMPS.some(([bx, by, r]) => Math.hypot(nx - bx, ny - by) <= r)

// Hand-drawn left halves (mirrored) for the Wave Band sizes, where the round bumps don't survive.
const CODEX_MASK = {
  small: ["...##.#", ".######", "#######", "#######", "#######", ".######", "#######", "#######", ".######", "..###.#"],
  mid: ["....###.##", "..########", ".#########", "##########", "##########", "##########", ".#########", ".#########",
    "##########", "##########", "##########", ".#########", "..########", "...####.##"],
}

// The ">_" glyph sets, by cloud width. "prompt" is the logo; "blink" drops the cursor
// (writing), "check" is Complete, "dim" is a lowered chevron for sleepy or sad poses.
const CODEX_GLYPH = {
  big: {
    prompt: ["WW..............", ".WW.............", "..WW............", "...WW...........", "...WW...........", "..WW............", ".WW.....WWWWWWWW", "WW......WWWWWWWW"],
    blink: ["WW..............", ".WW.............", "..WW............", "...WW...........", "...WW...........", "..WW............", ".WW.............", "WW.............."],
    check: ["..............WW", ".............WW.", "............WW..", "...........WW...", "WW........WW....", ".WW......WW.....", "..WW....WW......", "...WW..WW.......", "....WWWW........", ".....WW........."],
    dim: ["................", "................", "................", "................", "WWWWWW..WWWWWWWW", "WWWWWW..WWWWWWWW", "................", "................"],
  },
  mid: {
    prompt: ["W.....", ".W....", "W..WWW"],
    blink: ["W.....", ".W....", "W....."],
    check: [".....W", "W...W.", ".W.W..", "..W..."],
    dim: ["......", "WW.WWW", "......"],
  },
  small: {
    prompt: ["W...", ".W..", "W.WW"],
    blink: ["W...", ".W..", "W..."],
    check: ["...W", "W.W.", ".W.."],
    dim: ["....", "WWWW", "...."],
  },
}

// Draws the cloud, its feet and its glyph. Returns the geometry so poses can place props.
// o: { x, y, w, h: cloud box (w 14 at 18px, 20 at 24px, 30+ at 48x64; h squashes or stretches); P: { l, m, d } stops (default: the logo); C: color map (Disabled);
//      tilt: px the top leans right (negative leans left); bands: gradient band count;
//      feet: true | false | [lift left, lift right] in px; fw, fh: foot size;
//      glyph: key of CODEX_GLYPH or null; gdx, gdy: glyph nudge }
function codexCloud(c, o) {
  const C = o.C || ((v) => v), P = o.P || CODEX_P
  const { x, y, w, h } = o, tilt = o.tilt || 0
  const big = w >= 30, size = big ? "big" : w >= 18 ? "mid" : "small"
  const G = codexBands(P, o.bands || (big ? 7 : w >= 18 ? 5 : 4)).map(C)
  const cx = x + w / 2 - 0.5, cy = y + h / 2 - 0.5
  // Feet first, so the cloud's bottom bumps overlap their tops.
  const fw = o.fw ?? (big ? 7 : w >= 18 ? 4 : 3), fh = o.fh ?? (big ? 5 : 3)
  const fy = y + h - (big ? 2 : 1)
  const fx = [Math.round(cx - w * 0.22 - fw / 2 + 0.5), Math.round(cx + w * 0.22 - fw / 2 + 0.5)]
  if (o.feet !== false) {
    const lift = Array.isArray(o.feet) ? o.feet : [0, 0]
    const fc = C(mixHex(P.d, "#000000", 0.2))
    fx.forEach((fxx, i) => { c.rect(fxx, fy - lift[i], fw, fh, fc); if (big) { c.px(fxx, fy - lift[i] + fh - 1, "_"); c.px(fxx + fw - 1, fy - lift[i] + fh - 1, "_") } })
  }
  // Tilt shears the top toward +x: row j shifts by tilt * (distance from the bottom).
  const shear = (j) => tilt * (y + h - 1 - j) / Math.max(1, h - 1)
  const band = (j) => G[Math.min(G.length - 1, Math.floor((j - y) / h * G.length))]
  if (big) for (let j = y; j < y + h; j++) for (let i = x - 2; i < x + w + 2; i++) {
    if (codexInside((i - shear(j) - cx) / (w / 2), (j - cy) / (h / 2))) c.px(i, j, band(j))
  }
  else {
    // Squash or stretch a mask by dropping or repeating its middle rows to fit h.
    const m = CODEX_MASK[size].map((r) => r + [...r].reverse().join(""))
    while (m.length > h) m.splice(m.length >> 1, 1)
    while (m.length < h) m.splice(m.length >> 1, 0, m[m.length >> 1])
    m.forEach((r, j) => [...r].forEach((ch, i) => { if (ch === "#") c.px(x + i + Math.round(shear(y + j)), y + j, band(y + j)) }))
  }
  const g = { x, y, w, h, cx, cy, fx, fy, fw, fh, G, size }
  if (o.glyph) {
    const gl = CODEX_GLYPH[size][o.glyph], gw = gl[0].length, gh = gl.length
    g.gx = Math.round(cx - gw / 2 + 0.5 + tilt / 2) + (o.gdx || 0)
    g.gy = Math.round(cy - gh / 2 + 0.5) + (o.gdy || 0)
    rows(c, g.gx, g.gy, gl, { W: "#FFFFFF" })
  }
  return g
}

// The six Prompt Band Avatar States at 46x62 (+1px outline = 48x64). Frame counts and fps
// match harness() in base.px.js so the manifest timings stay the same.
HARNESS.codex = { id: "codex", P: CODEX_P, e: "#16124A", outline: CODEX_OUT }
{
  const S = (name, fn) => sprite("codex_" + name, { w: 46, h: 62, outline: CODEX_OUT }, fn)
  const A = (name, frames, fps, fn) => anim("codex_" + name, { w: 46, h: 62, outline: CODEX_OUT, frames, fps }, (c) => fn(c, c.phase * Math.PI * 2, c.frame))
  const base = { x: 4, y: 20, w: 38, h: 34 }
  S("default", (c) => codexCloud(c, { ...base, glyph: "prompt" }))
  // Happy bounce: the cloud squashes and stretches on the beat, two notes rise.
  A("selected", 8, 8, (c, k, f) => {
    const s = Math.round(2 * Math.sin(k * 2)), note = ["..ee", "..e.", "..e.", ".ee.", ".ee."]
    codexCloud(c, { ...base, y: 20 - s, h: 34 + s, tilt: Math.round(Math.sin(k)), glyph: "prompt" })
    rows(c, 0, noteY(18, f), note, { e: "#F5C842" }); rows(c, 42, noteY(18, (f + 4) % 8), note, { e: "#F5C842" })
  })
  // Main Orchestrator: bouncing with the crown on top, twinkles.
  A("main", 6, 5, (c, k, f) => {
    const b = Math.round(1.5 * Math.sin(k))
    const { x, y, w } = codexCloud(c, { ...base, y: 22 - b, h: 32 + b, glyph: "prompt" })
    rows(c, x + Math.round((w - 25) / 2), y - 6, CROWN, CROWN_C)
    spark(c, f % 2 ? 3 : 42, 12, 2); spark(c, f % 2 ? 42 : 3, 20, 1)
  })
  // Gray, slumped low, dim glyph, one tear.
  S("disabled", (c) => {
    const { gx, gy } = codexCloud(c, { ...base, y: 26, h: 28, C: gray, glyph: "dim", gdy: 2 })
    c.rect(gx + 2, gy + 6, 2, 3, "#9FB6C4"); c.px(gx + 2, gy + 9, "#9FB6C4")
  })
  // Leaning over a keyboard, bobbing as it types; the cursor blinks and a lit key moves.
  A("writing", 4, 6, (c, k, f) => {
    codexCloud(c, { ...base, y: 17 + f % 2, h: 34, tilt: 2, feet: false, glyph: f % 2 ? "blink" : "prompt" })
    c.rect(2, 50, 42, 9, "#5A616B"); c.rect(2, 59, 42, 2, "#3B4048")
    for (let r = 0; r < 2; r++) for (let x = 8 + r * 2; x + 3 <= 38; x += 4) c.rect(x, 51 + r * 3, 3, 2, "#C9CED6")
    c.rect(13, 57, 20, 2, "#C9CED6")
    const lit = [[12, 51], [30, 54], [18, 54], [24, 51]][f]
    c.rect(lit[0], lit[1], 3, 2, "#4FA8E8")
  })
  // Impatient: one foot taps, the cloud tilts side to side, "..." fills up above it.
  A("waiting", 4, 4, (c, k, f) => {
    const dn = f % 2 === 1
    codexCloud(c, { ...base, tilt: f < 2 ? -2 : 2, feet: [0, dn ? 0 : 3], glyph: f === 3 ? "blink" : "prompt" })
    for (let i = 0; i <= f && i < 3; i++) c.rect(17 + i * 5, 12, 3, 3, "#FFFFFF")
    if (dn) { c.px(40, 58, "#F5C842"); c.px(42, 56, "#F5C842"); c.px(40, 54, "#F5C842") }
  })
}
for (const s of ["todo", "progress", "complete"]) include(`codex/${s}.px.js`)
