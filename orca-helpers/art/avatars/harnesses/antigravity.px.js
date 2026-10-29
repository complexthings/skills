// Google Antigravity: the smooth arched "A" (no crossbar), rounded peak, soft inner arch, legs flaring
// into curled feet. Gradient: green top-left, red top-right, blending into blue over the lower body.
const AG = { g: [52, 168, 83], y: [251, 188, 4], r: [234, 67, 53], b: [51, 136, 255] }
const agMix = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t))
const agHex = (c) => "#" + c.map((v) => v.toString(16).padStart(2, "0")).join("")
harness({
  id: "antigravity", P: { m: "#3388FF", d: "#2563C9", l: "#7FB2FF" }, e: "#0d1a3a",
  legs() {},
  deco(c, { bx, by, w, C, o, eyes, E }) {
    const L = o.legs || [0, 0, 0, 0], cx = bx + w / 2 - 0.5
    // Skip face pixels so the eyes and mouth stay on top of the gradient.
    const keep = new Set()
    eyes.forEach(([x, y]) => E.forEach((r, j) => [...r].forEach((ch, i) => { if (ch !== ".") keep.add(x + i + "," + (y + j)) })))
    if (o.mouth) { const M = MOUTH[o.mouth], mx = bx + w / 2 - M[0].length / 2 + (o.ex || 0), my = by + 6 + 9 + (o.my || 0)
      M.forEach((r, j) => [...r].forEach((ch, i) => { if (ch !== ".") keep.add(mx + i + "," + (my + j)) })) }
    for (let x = bx - 3; x <= bx + w + 2; x++) {
      const bot = 57 - (x > cx ? L[3] : L[0]), H = bot - by + 1, dx = Math.abs(x - cx)
      for (let y = by; y <= 57; y++) {
        const dy = y - by, fromBot = bot - y
        let hw = dy < 9 ? 17 * Math.sqrt(Math.max(0, 1 - ((9 - dy - 0.5) / 9) ** 2)) + 0.5 : 17
        if (fromBot === 2) hw = 18.5; if (fromBot === 1) hw = 19.5; if (fromBot === 0) hw = 19.5
        let inside = dx <= hw - 0.5 && y <= bot
        if (fromBot === 0 && dx > 18) inside = false // toe tip curls up
        if (fromBot === 1 && dx > 19) inside = true
        const ot = by + Math.round(H * 0.58), oy = y - ot // inner arch opening
        if (oy >= 0 && dx <= 5.5 * Math.sqrt(Math.min(1, (oy + 0.5) / 4)) ) inside = false
        { if (!inside) { if (x >= bx && x < bx + w) c.px(x, y, "_"); continue }
          if (keep.has(x + "," + y)) continue
          const u = (x - (bx - 3)) / (w + 5), v = dy / H
          const s = Math.min(1, Math.max(0, (u - 0.3) / 0.4)), top = s < 0.5 ? agMix(AG.g, AG.y, s * 2) : agMix(AG.y, AG.r, s * 2 - 1)
          let col = agMix(top, AG.b, Math.min(1, Math.max(0, (v - 0.2) / 0.4)))
          if (dx >= hw - 1.5 || y === bot) col = agMix(col, [20, 40, 110], 0.25)
          c.px(x, y, C(agHex(col)))
        }
      }
    }
  },
})
// Wave Band body colour at (u, v), each 0..1 across the body's box. The default Mood keeps the
// brand gradient; any other Mood is its flat P.m (callers add P.l / P.d edges themselves).
const agBody = (mood, P, u, v) => mood !== "default" ? P.m : agHex(agMix(
  u < 0.5 ? agMix(AG.g, AG.y, Math.max(0, u - 0.15) / 0.35) : agMix(AG.y, AG.r, Math.min(1, (u - 0.5) / 0.35)),
  AG.b, Math.min(1, Math.max(0, (v - 0.25) / 0.45))))
for (const s of ["todo", "progress", "complete"]) include(`antigravity/${s}.px.js`)
