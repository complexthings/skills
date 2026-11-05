// Antigravity complete: the work is done. The same arched "A" as Todo (dome, inner arch notch, flared feet); props use fixed colours.
{
  // body spans per row, same as todo.px.js: [x0, x1] or [x0, x1, x2, x3] (inner arch notch between)
  const S18 = { 2: [5, 10], 3: [4, 11], 4: [3, 12], 5: [3, 12], 6: [2, 13], 7: [2, 13], 8: [2, 13], 9: [2, 13],
    10: [2, 6, 9, 13], 11: [2, 5, 10, 13], 12: [2, 5, 10, 13], 13: [1, 5, 10, 14], 14: [0, 4, 11, 15], 15: [0, 4, 11, 15] }
  const S24 = { 3: [8, 13], 4: [6, 15], 5: [5, 16], 6: [4, 17], 7: [4, 17], 8: [3, 18], 9: [3, 18], 10: [3, 18], 11: [3, 18],
    12: [3, 18], 13: [3, 18], 14: [3, 9, 12, 18], 15: [3, 8, 13, 18], 16: [3, 8, 13, 18], 17: [2, 7, 14, 19], 18: [2, 6, 15, 19],
    19: [1, 5, 16, 20], 20: [0, 4, 17, 21], 21: [0, 4, 17, 21] }
  const has = (S, x, y) => { const r = S[y]; return !!r && (x >= r[0] && x <= r[1] || r.length > 2 && x >= r[2] && x <= r[3]) }
  // logo gradient on default; other Moods run P.l (top-left) through P.m to P.d (bottom-right)
  const rgb = (s) => [1, 3, 5].map((i) => parseInt(s.slice(i, i + 2), 16))
  const tint = (mood, P, u, v) => { if (mood === "default") return agBody(mood, P, u, v)
    const t = Math.min(1, Math.max(0, 0.75 * v + 0.25 * u))
    return agHex(t < 0.5 ? agMix(rgb(P.l), rgb(P.m), t * 2) : agMix(rgb(P.m), rgb(P.d), t * 2 - 1)) }
moodState("antigravity", "complete", {
  frames: 4, fps: 4,
  draw: (c, { size, mood, P, e, f }) => {
    const big = size === 24, S = big ? S24 : S18, top = big ? 3 : 2, w = size - 2, x = 0, Y = 0, dy = 0
    // eyes sit where Todo's do; H = rows above the arch notch (shirt / bubbles)
    const ex = big ? [7, 13] : [4, 10], ew = 2, eh = big ? 3 : 2, ey = big ? 6 : 5, H = big ? 14 : 10
    const inB = (i, j) => has(S, i, j)
    for (const y in S) for (let i = 0; i < w; i++) if (has(S, i, +y))
      c.px(i, +y, !has(S, i, +y + 1) && mood === "default" ? P.d : tint(mood, P, i / (w - 1), (y - top) / (w - top - 1)))
    // arms; yellow (sitting) holds them a row lower
    const as = big ? 3 : 2, ay = (big ? 10 : 7) + (mood === "yellow" ? 1 : 0)
    for (const q of [0, w - as]) for (let i = 0; i < as; i++) for (let j = 0; j < as; j++) c.px(q + i, ay + j, tint(mood, P, q / (w - 1), (ay + j - top) / (w - top - 1)))
    // eyes
    const closed = mood !== "green" && mood !== "red" && mood !== "yellow" && mood !== "purple"
    const wavy = f % 2
    ex.forEach(px => {
      if (mood === "blue") return // face down: no face
      if (closed || mood === "purple") c.rect(px, ey + dy + (big ? 1 : 0), ew + (big ? 1 : 0), 1, e)
      else if (mood === "green") { c.rect(px, ey + dy, ew, 1, e); c.px(px, ey + dy + 1, e); c.px(px + ew - 1, ey + dy + 1, e) } // happy arcs
      else c.rect(px, ey + dy, ew, eh, e)
    })
    if (mood === "blue") for (let i = 0; i < w; i++) if (has(S, i, top + 2)) c.px(i, top + 2, P.d)
    const T = "#ffffff"
    const W = "#ffffff", G = "#8a5a2b", Zc = "#9ad0ff"
    const cx = x + (w >> 1)
    // ---- props ----
    if (mood === "default") {
      // Z Z Z rising, right side
      const zs = [[0, 0], [1, 1], [2, 2]]
      const z = (zx, zy, s) => {
        if (s === 2) { c.rect(zx, zy, 4, 1, Zc); c.px(zx + 2, zy + 1, Zc); c.px(zx + 1, zy + 2, Zc); c.rect(zx, zy + 3, 4, 1, Zc) }
        else { c.rect(zx, zy, 3, 1, Zc); c.px(zx + 1, zy + 1, Zc); c.rect(zx, zy + 2, 3, 1, Zc) }
      }
      // one Z rising beside the dome, clear of the head
      const t = f, zy = Math.round((big ? 4 : 3) - t * (big ? 1.5 : 1)), zx = big ? 18 : 13
      if (zy >= 0) z(zx, zy, big ? 2 : 1)
    } else if (mood === "red") {
      // beer mug in right hand, tilts up/down
      const up = f === 1 || f === 2
      const mx = big ? 19 : 13, my = (big ? 8 : 6) + (up ? -1 : 0)
      const mw = big ? 3 : 2, mh = big ? 5 : 4
      c.rect(mx, my + 1, mw, mh - 1, "#f2b01e"); c.rect(mx, my, mw, 1, "#ffffff")
      c.px(mx + mw, my + 2, "#d8d8d8"); if (big) c.px(mx + mw, my + 3, "#d8d8d8")
      if (up) c.px(mx, my - 1, "#ffffff")
    } else if (mood === "blue") {
      // white flag held up, waving
      const px = w - 1, top = big ? 1 : 0
      c.rect(px, top, 1, big ? 8 : 6, "#8b6b3a")
      const fw = big ? 5 : 4, fh = big ? 3 : 2, off = f % 2
      c.rect(px - fw, top + off % 2 * 0, fw, fh, W)
      c.px(px - fw, top + fh - 1 + off, W)
    } else if (mood === "green") {
      const cols = ["#ff4d6d", "#ffd23f", "#3ec1f0", "#b06bff", "#ffffff"]
      const pts = big ? [[2, 1], [6, 0], [10, 2], [14, 0], [18, 2], [20, 5], [1, 6], [8, 4], [16, 5], [4, 3]] : [[1, 0], [4, 1], [8, 0], [12, 1], [14, 3], [0, 4], [6, 3], [10, 3]]
      pts.forEach(([px, py], i) => { const qy = (py + f * (big ? 2 : 1) + i % 2) % (big ? 8 : 6); if (!has(S, px, qy)) c.px(px, qy, cols[i % 5]) })
    } else if (mood === "yellow") {
      const bx = big ? 17 : 12, by = (big ? 0 : 0) + (f === 1 || f === 3 ? 1 : 0)
      const bw = big ? 4 : 3, bh = big ? 5 : 4, bc = "#ff4d6d"
      c.rect(bx, by, bw, bh, bc); c.px(bx + 1, by + 1, "#ffb3c1")
      c.px(bx + (bw >> 1), by + bh, bc)
      c.rect(bx + (bw >> 1), by + bh + 1, 1, (big ? 9 : 6) - bh - by - 0, "#dddddd")
    } else if (mood === "purple") {
      // hawaiian shirt over body: fixed colours
      const sy = ey + dy + (big ? 3 : 2), sh = Y + H - sy; for (let j = sy; j < Y + H; j++) for (let i = 1; i < w - 1; i++) if (inB(i, j - Y)) c.px(x + i, j, "#1fa6a0")
      for (let i = 0; i < w - 2; i += 3) { const q = sy + (sh > 2 ? (i / 3) & 1 : 0); if (inB(1 + i, q - Y)) c.px(x + 1 + i, q, "#ff5d8f"); if (big && inB(2 + i, sy + 2 + ((i / 3) & 1) - Y)) c.px(x + 2 + i, sy + 2 + ((i / 3) & 1), "#ffd23f") }
            // collar V
      c.px(cx - 1, sy, "#ffffff"); c.px(cx, sy, "#ffffff")
      // eyes drawn over shirt would hide; redraw
      ex.forEach(px => c.rect(px, ey + dy + (big ? 1 : 0), ew + (big ? 1 : 0), 1, e))
      // tropical drink with umbrella and straw
      const mx = big ? 19 : 13, my = (big ? 8 : 6) + (f === 1 || f === 2 ? -1 : 0)
      c.rect(mx, my + 1, big ? 3 : 2, big ? 4 : 3, "#ff6b3d"); c.px(mx, my + 1, "#ffd23f")
      c.px(mx + 1, my - 1, "#ff4d6d"); c.px(mx + (big ? 2 : 1), my, "#ffffff")
      if (big) { c.px(mx + 1, my - 2, "#ff4d6d") }
    } else if (mood === "teal") {
      const bc = "#bfe9ff"
      const mx = cx, my = Y + (big ? 6 : 4)
      for (let i = 0; i < 3; i++) {
        const t = (f + i * 1.33) % 4, by = Math.round((big ? 7 : 4) - t * (big ? 2 : 1.2))
        const bxx = w - (big ? 3 : 2) + (i & 1)
        if (t < 3.4 && by >= 0) { c.px(bxx, by, bc); if (big && i === 0) c.px(bxx + 1, by, bc) }
      }
    }
  },
})
}
