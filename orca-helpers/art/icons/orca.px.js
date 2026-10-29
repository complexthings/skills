// Animated orca icons, 24x24. Black body with a lighter rim (reads on #1e1e1e), white eye patches
// with a grey edge (reads on white), light-blue ripples (darker blue tail for light bg).
pal({ k: "#0b0b12", l: "#5c5c72", w: "#ffffff", e: "#9a9aae", g: "#4a4a5e",
      b: "#7fd6ff", B: "#1fa8ff", d: "#2a78b0", s: "#b8e6ff" })

const T = Math.PI * 2
const mir = (L) => L.map((r) => r + [...r].reverse().join(""))
const tone = (t) => (t < 0.4 ? "b" : t < 0.75 ? "B" : "d")

// Draw an ASCII body (24 chars/row, k black, w white, g grey) at (0, oy), clipped at waterline W,
// with a lighter rim on every edge above the water.
function body(c, rows, oy, W) {
  const at = (x, y) => (rows[y - oy] || "")[x] || "."
  for (let y = oy; y < oy + rows.length && y < W; y++)
    for (let x = 0; x < 24; x++) {
      const v = at(x, y)
      if (v === ".") continue
      const edge = at(x, y - 1) === "." || at(x - 1, y) === "." || at(x + 1, y) === "."
      c.px(x, y, v === "w" ? "w" : edge ? "l" : v)
    }
  // grey edge around white patches (so white reads on white-ish areas / blends cleanly)
  for (let y = oy; y < oy + rows.length && y < W; y++)
    for (let x = 0; x < 24; x++)
      if (at(x, y) === "k" && [[1,0],[-1,0],[0,1],[0,-1]].some(([a,b]) => at(x+a, y+b) === "w")) c.px(x, y, "k")
}

// Expanding elliptical ripples around (cx, cy). style: dash | ring | dots
function ripples(c, ph, cx, cy, o = {}) {
  const { n = 2, r0 = 5, r1 = 11, ry0 = 1, ry1 = 3.4, style = "dash", from = -0.1 } = o
  for (let i = 0; i < n; i++) {
    const t = (ph + i / n) % 1
    if (t > 0.92) continue
    const rx = r0 + (r1 - r0) * t, ry = ry0 + (ry1 - ry0) * t
    const steps = 48
    for (let a = 0; a < steps; a++) {
      const th = (a / steps) * T
      if (Math.sin(th) < from) continue
      if (style === "dash" && (a + i * 2) % 6 > 3) continue
      if (style === "dots" && (a + i) % 4) continue
      c.px(Math.round(cx + Math.cos(th) * rx), Math.round(cy + Math.sin(th) * ry), tone(t))
    }
  }
}
const bob = (ph, phase0 = 0) => Math.round(0.5 + 0.5 * Math.sin(ph * T + phase0))

// ---- 1: front view, like the reference
const F = mir([
  "..........kk", "..........kk", ".........kkk", ".........kkk", "........kkkk",
  "........kkkk", ".......kkkkk", ".......kkkkk", "......kkkkkk", ".....kkkkkkk",
  "....kkkwwwkk", "....kkkwwwkk", "...kkkkwwkkk", "...kkkkkkkkk", "..kkkkkkkkkk", "..kkkkkkkkkk"])
anim("orca_1", { w: 24, h: 24, frames: 8, fps: 6 }, (c) => {
  ripples(c, c.phase, 12, 20, { r0: 6, r1: 11, ry0: 1.2, ry1: 3.2 })
  body(c, F, 3 + bob(c.phase), 19)
})

// ---- 2: side view, dorsal fin + head, right-facing
anim("orca_2", { w: 24, h: 24, frames: 8, fps: 6 }, (c) => {
  const S = [
    ".........k..............", ".........kk.............", "........kkk.............",
    "........kkkk............", ".......kkkkk............", ".......kkkkkk...........",
    "......kkkkkkk.....kkk...", "......kkkkkkkk..kkkkkkk.", ".....kkkkkkkkkkkkkkkkkkk",
    "...kkkkkkkkkkkkkkwwkkkkk", "..kkkkkkkkkkkkkkkwwwkkkk", "..kkkkkkkkkkkkkkkkkkkkkk"]
  ripples(c, c.phase, 12, 19, { r0: 7, r1: 11, ry0: 1.2, ry1: 3, style: "ring" })
  body(c, S, 6 + bob(c.phase, 1), 18)
})

// ---- 3: dorsal fin + back only, with a V wake that shimmers
anim("orca_3", { w: 24, h: 24, frames: 8, fps: 6 }, (c) => {
  const fin = [
    "...........k............", "...........kk...........", "..........kkk...........",
    "..........kkkk..........", ".........kkkkk..........", ".........kkkkkk.........",
    "........kkkkkkk.........", "........kkkkkkkk........", ".......kkkkkkkkk........",
    ".......kkkkkkkkkk.......", "......kkkkkkkkkkk.......", "......kkkkkkkkkkkk......",
    ".....kkkkkkkkkkkkk......", "....kkkkkkkkkkkkkkk.....", "....kkkkkkkkkkkkkkkk...."]
  const y = 6 + bob(c.phase)
  // wake: two lines trailing left, dashes slide with phase
  for (let i = 0; i < 9; i++) {
    const x = 7 - i
    if ((i + Math.round(c.phase * 8)) % 3) continue
    const t = i / 9
    c.px(x, 19 + Math.round(i * 0.35), tone(t))
    c.px(x + 4, 21 + Math.round(i * 0.15), tone(t))
  }
  ripples(c, c.phase, 12, 20, { r0: 6, r1: 10, ry0: 1, ry1: 2.6, from: 0.1, n: 1 })
  body(c, fin, y, 19)
})

// ---- 4: small front-view orca with a blowhole spout
const H = F.slice(5)
anim("orca_4", { w: 24, h: 24, frames: 10, fps: 8 }, (c) => {
  const oy = 9 + bob(c.phase)
  ripples(c, c.phase, 12, 20, { r0: 6, r1: 11, ry0: 1.2, ry1: 3, style: "dots" })
  body(c, H, oy, 19)
  c.px(11, oy + 1, "g"); c.px(12, oy + 1, "g")
  // spout: droplets arc out of the blowhole
  for (let i = 0; i < 4; i++) {
    const t = (c.phase + i / 4) % 1
    const side = i % 2 ? 1 : -1, sp = i < 2 ? 0.6 : 1
    const x = Math.round(11.5 + side * (0.5 + t * 3.5 * sp)), yy = Math.round(oy - 0.5 - Math.sin(Math.PI * t) * 7 * (0.7 + 0.3 * sp) + t * 2)
    if (t < 0.95) c.px(x, yy, t > 0.5 ? "B" : "s")
  }
  const top = Math.round(oy - 3 - 2 * Math.sin(c.phase * T)); c.px(11, oy - 1, "s"); c.px(12, oy - 1, "s"); c.px(11, oy - 2, "b")
})

// ---- 5: spyhop, tall rounded head with white chin, concentric ripples + sparkles
const P = mir([
  "..........kk", "........kkkk", ".......kkkkk", "......kkkkkk", "......kkkkkk", ".....kkkkkkk",
  ".....kkkkkkk", ".....kwwwkkk", ".....kkwwwkk", ".....kkkkkkk", "....kkkkkkkk", "....kkkkkkkk",
  "....kkkkkkkk", "....kkkkkkkk", "....kkkkkkkk"])
anim("orca_5", { w: 24, h: 24, frames: 12, fps: 8 }, (c) => {
  const oy = 3 + bob(c.phase, 2)
  ripples(c, c.phase, 12, 20, { r0: 5, r1: 11, ry0: 1.2, ry1: 3.3, style: "ring", n: 3 })
  body(c, P, oy, 19)
  // sparkles on the water
  for (let i = 0; i < 3; i++) {
    const t = (c.phase * 3 + i / 3) % 1
    if (t < 0.25) c.px([3, 19, 16][i], [21, 22, 23][i], "s")
  }
})

for (let i = 1; i <= 5; i++) sprite(`orca_${i}_still`, { w: 24, h: 24 }, stamp(`orca_${i}`, 0, 0, { frame: 0 }))
