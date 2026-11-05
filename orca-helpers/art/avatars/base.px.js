// Shared Harness Avatar character and the six picked Avatar States (picks.json).
// Canvas 46x62 + 1px outline = 48x64. Harness files call harness(H); colors are "#hex" so
// harness files never fight over palette keys.
pal({ k: "#2b1710" })

const rows = (c, x, y, g, map = {}) => g.forEach((r, j) => [...r].forEach((ch, i) => { if (ch !== ".") c.px(x + i, y + j, map[ch] || ch) }))
const EYES = {
  sq: ["eeee", "eeee", "eeee", "eeee"], happy: ["....", ".ee.", "e..e"], half: ["....", "....", "eeee", "eeee"],
}
const MOUTH = { smile: ["e....e", ".eeee."], flat: ["eeee"] }

// export.mjs crops the top CROP px off the 48x64 states, so nothing may draw above it.
// The Selected notes rise from `from` to CROP over 8 frames; a note's outline lands on CROP.
const CROP = 11
const noteY = (from, n) => from - Math.round((n * (from - CROP)) / 7)

// Desaturate for the Disabled state: luminance, lifted and compressed so it still reads on dark.
const gray = (hex) => {
  if (typeof hex !== "string" || !hex.startsWith("#")) return hex
  const n = parseInt(hex.slice(1, 7), 16), v = Math.round(60 + 0.6 * (0.299 * (n >> 16) + 0.587 * (n >> 8 & 255) + 0.114 * (n & 255)))
  const h = v.toString(16).padStart(2, "0")
  return "#" + h + h + h
}

// H: { id, P: { m, d, l } body mid/dark/light, e eye color, outline key or hex,
//      w, h, legH, inset, eyeY, dx (body size and face placement, Clawd defaults),
//      legs(c, ctx) to replace the four legs, deco(c, ctx) for the harness's signature marks }
// o: per-state pose: dx, dy, dh, dleg, eye, ex, ey, mouth, my, legs[4], aL, aR, arms, C color map.
function body(c, H, o = {}) {
  const C = o.C || ((x) => x)
  const m = C(H.P.m), d = C(H.P.d), l = C(H.P.l), e = C(H.e || "#1e120e")
  const w = H.w ?? 34, h = (H.h ?? 22) - (o.dh || 0), legH = (H.legH ?? 8) - (o.dleg || 0)
  const inset = H.inset ?? 7, eyeY = H.eyeY ?? 6, legs = o.legs || [0, 0, 0, 0]
  const bx = Math.round((46 - w) / 2) + (H.dx || 0) + (o.dx || 0), by = 58 - legH - h + (o.dy || 0)
  const ctx = { bx, by, w, h, legH, m, d, l, e, C, o, state: o.state }
  if (H.legs) H.legs(c, ctx)
  else [bx + 3, bx + 10, bx + w - 15, bx + w - 8].forEach((x, i) => {
    c.rect(x, by + h - 1, 5, legH + 1 - legs[i], m)
    c.rect(x, by + h + legH - legs[i] - 2, 5, 2, d)
  })
  c.rect(bx, by, w, h, m)
  c.rect(bx, by, w, 2, l); c.rect(bx, by + 2, 1, h - 5, l)
  c.rect(bx + w - 2, by + 2, 2, h - 2, d); c.rect(bx, by + h - 3, w, 3, d)
  c.px(bx, by, "_"); c.px(bx + w - 1, by, "_")
  if (o.arms !== false) [[-1, o.aL || {}], [1, o.aR || {}]].forEach(([s, a]) => {
    const x = s < 0 ? bx - 4 : bx + w, ah = a.h ?? 6, ay = by + (a.y ?? 9)
    c.rect(x, ay, 4, ah, m); c.rect(x, ay + ah - 2, 4, 2, d); c.px(x + (s < 0 ? 0 : 3), ay, l)
  })
  const E = EYES[o.eye || "sq"], EW = E[0].length, ey = by + eyeY + (o.ey || 0), ex = o.ex || 0
  ctx.eyes = [[bx + inset + ex, ey], [bx + w - inset - EW + ex, ey]]
  ctx.E = E
  ctx.eyes.forEach(([x, y]) => rows(c, x, y, E, { e }))
  if (o.mouth) { const M = MOUTH[o.mouth]; rows(c, bx + w / 2 - M[0].length / 2 + ex, by + eyeY + 9 + (o.my || 0), M, { e }) }
  if (H.deco) H.deco(c, ctx)
  return ctx
}

// Main Orchestrator crown, 25x8 (the prototype's 19px crown read too small).
const CROWN = ["y...........y...........y", "yy.........yyy.........yy", "yZy...y...yyZyy...y...yZy", "yyyy.yyy.yyyyyyy.yyy.yyyy",
  "yyyyyyyyyyyyyyyyyyyyyyyyy", "yyRRyyyyyyyBBByyyyyyyRRyy", "yyRRyyyyyyyBBByyyyyyyRRyy", "YYYYYYYYYYYYYYYYYYYYYYYYY"]
const CROWN_C = { y: "#F5C842", Y: "#C98F1C", Z: "#FFF0A0", R: "#E0443C", B: "#4FA8E8" }
function spark(c, x, y, s) { if (s === 1) c.px(x, y, "#FFF4E6"); if (s === 2) { c.px(x, y, "#FFF4E6"); [[1, 0], [-1, 0], [0, 1], [0, -1]].forEach(([a, b]) => c.px(x + a, y + b, "#FFF0A0")) } }

const HARNESS = {}
function harness(H) {
  HARNESS[H.id] = H
  const id = H.id, out = H.outline || "k"
  const S = (name, fn) => sprite(id + "_" + name, { w: 46, h: 62, outline: out }, fn)
  const A = (name, frames, fps, fn) => anim(id + "_" + name, { w: 46, h: 62, outline: out, frames, fps }, (c) => fn(c, c.phase * Math.PI * 2, c.frame))

  S("default", (c) => body(c, H, { state: "default" }))

  // selected_3: arms up, bobbing, two notes rising
  A("selected", 8, 8, (c, k, f) => {
    const p = Math.round(2 * Math.sin(k)), note = ["..ee", "..e.", "..e.", ".ee.", ".ee."]
    body(c, H, { state: "selected", dy: Math.round(Math.sin(k * 2)), eye: "happy", mouth: "smile", aL: { y: -6 + p, h: 9 }, aR: { y: -6 - p, h: 9 } })
    rows(c, 4, noteY(20, f), note, { e: "#F5C842" }); rows(c, 38, noteY(20, (f + 4) % 8), note, { e: "#F5C842" })
  })

  // main_2: bouncing with a bigger crown and twinkles
  A("main", 6, 5, (c, k, f) => {
    const b = Math.round(1.5 * Math.sin(k))
    const { bx, by, w } = body(c, H, { state: "main", dy: b, eye: "happy", mouth: "smile", aL: { y: 5, h: 5 }, aR: { y: 5, h: 5 } })
    rows(c, bx + Math.round((w - 25) / 2), by - 9 + (f === 2 || f === 3 ? 1 : 0) - (f === 0 ? 1 : 0), CROWN, CROWN_C)
    spark(c, f % 2 ? 4 : 41, by - 10, 2); spark(c, f % 2 ? 42 : 3, by - 3, 1)
  })

  // disabled_2: gray, slumped, sleepy eyes, one tear
  S("disabled", (c) => {
    const { bx, by } = body(c, H, { state: "disabled", C: gray, dh: 2, dleg: 1, eye: "half", mouth: "flat", my: -2, aL: { y: 10, h: 7 }, aR: { y: 10, h: 7 } })
    c.rect(bx + 8, by + 11, 2, 4, "#9FB6C4"); c.px(bx + 8, by + 15, "#9FB6C4")
  })

  // writing_1, made legible: a real keyboard with keycaps, outlined paws tapping, the pressed key lit
  A("writing", 4, 6, (c, k, f) => {
    const { m, d } = body(c, H, { state: "writing", eye: "half", ex: f < 2 ? -1 : 1, arms: false })
    c.rect(2, 48, 42, 9, "#5A616B"); c.rect(2, 57, 42, 2, "#3B4048")
    for (let r = 0; r < 2; r++) for (let x = 8 + r * 2; x + 3 <= 38; x += 4) c.rect(x, 49 + r * 3, 3, 2, "#C9CED6")
    c.rect(13, 55, 20, 2, "#C9CED6")
    const lit = [[12, 49], [30, 52], [18, 52], [24, 49]][f]
    c.rect(lit[0], lit[1], 3, 2, "#4FA8E8")
    ;[[7, f % 2], [33, 1 - f % 2]].forEach(([x, a]) => { c.rect(x, 45 + a, 6, 5, m); c.rect(x, 48 + a, 6, 2, d); c.box(x, 45 + a, 6, 5, out === "k" ? "#2b1710" : out) })
  })

  // waiting_2: foot tapping, glancing at the wrist watch
  A("waiting", 4, 4, (c, k, f) => {
    const dn = f % 2 === 1
    const { bx, by } = body(c, H, { state: "waiting", eye: "half", ex: f < 2 ? -2 : 2, mouth: "flat", legs: [0, 0, 0, dn ? 0 : 3], aL: { y: 10 }, aR: { y: 10 } })
    c.rect(bx - 4, by + 12, 4, 2, "#4A4A4A"); c.rect(bx - 3, by + 12, 2, 2, "#F5C842")
    if (dn) { c.px(40, 58, "#F5C842"); c.px(41, 56, "#F5C842"); c.px(40, 54, "#F5C842") }
  })
}

// Wave Band Avatar States: todo, progress (In Progress), complete. Each is drawn by hand at 18x18
// and 24x24 in every Avatar Mood, never downscaled. Files: <id>_<state>_<mood>_<size>, for example
// claude_progress_red_18. A Mood tints the Harness Avatar's body only, never props.
// Body palettes per Mood; default keeps the harness's brand colours (H.P).
const MOODS = {
  default: null,
  red: { m: "#E0443C", d: "#A82A24", l: "#F47B72" },
  blue: { m: "#4F8FE8", d: "#2F62B0", l: "#8DBBF5" },
  green: { m: "#4CB85C", d: "#2E8040", l: "#8ADB94" },
  yellow: { m: "#F5C842", d: "#C9971C", l: "#FFE38A" },
  purple: { m: "#9B6BD6", d: "#6A42A0", l: "#C6A4EE" },
  teal: { m: "#33B5A8", d: "#1F7F76", l: "#7EDBD1" },
}
const WAVE_SIZES = [18, 24]

// One Wave Band Avatar State for one harness, in every Mood and size. Called from
// harnesses/<id>/<state>.px.js. s: { frames, fps, draw(c, ctx) }; frames 1 is a still.
// The canvas is size-2 square; the harness outline adds 1px on every side.
// ctx: { size, mood, P (Mood body palette m/d/l), e (eye colour), out (outline), f (frame), k (phase in radians) }
function moodState(id, state, s) {
  const H = HARNESS[id], out = H.outline || "k", e = H.e || "#1e120e"
  for (const size of WAVE_SIZES) for (const mood of Object.keys(MOODS)) {
    const name = `${id}_${state}_${mood}_${size}`, P = MOODS[mood] || H.P
    const ctx = (c) => ({ size, mood, P, e, out, f: c.frame || 0, k: (c.phase || 0) * Math.PI * 2 })
    const o = { w: size - 2, h: size - 2, outline: out }
    if ((s.frames || 1) === 1) sprite(name, o, (c) => s.draw(c, ctx(c)))
    else anim(name, { ...o, frames: s.frames, fps: s.fps }, (c) => s.draw(c, ctx(c)))
  }
}
