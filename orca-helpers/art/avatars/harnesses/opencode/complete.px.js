// OpenCode complete: the work is done. Props use fixed colours; body/arms/legs use P.
moodState("opencode", "complete", {
  frames: 4, fps: 4,
  draw: (c, { size, mood, P, e, f }) => {
    const big = size === 24
    // same O-mark as Todo/Progress: tall light frame, dark screen, two legs
    const g = big
      ? { x: 3, w: 16, y: 4, h: 11, ly: 15, lh: 3, legs: [5, 14], lw: 3, ax: [0, 19], aw: 3, ay: 8, ah: 3, ex: [7, 13], ew: 2, eh: 3, ey: 6 }
      : { x: 2, w: 12, y: 3, h: 8, ly: 11, lh: 2, legs: [3, 10], lw: 2, ax: [0, 14], aw: 2, ay: 6, ah: 2, ex: [4, 10], ew: 2, eh: 2, ey: 5 }
    // slumped moods drop the head 1px (like Todo teal); hand-held props raise the right arm
    const dy = mood === "default" || mood === "yellow" || mood === "teal" || mood === "blue" ? 1 : 0
    const raise = mood === "red" || mood === "purple" || mood === "blue" ? (big ? 4 : 3) : 0
    const { x, w, y, h, ly, lh, legs, lw, ax, aw, ay, ah, ex, ew, eh, ey } = g
    const Y = y + dy
    // legs (sitting: shorter)
    const sit = mood === "yellow"
    legs.forEach(lx => c.rect(lx, ly + (sit ? 1 : 0), lw, sit ? lh - 1 : lh, P.d))
    c.rect(x, Y, w, ly - Y, P.m)
    c.rect(x, Y, w, 1, P.l)
    c.rect(x, ly - 1, w, 1, P.d)
    // arms
    c.rect(ax[0], ay + dy, aw, ah, P.m); c.rect(ax[1], ay + dy - raise, aw, ah, P.m)
    // dark screen inset (fixed colours), blue is face down
    if (mood !== "blue") {
      const sx = x + (big ? 2 : 1), sw = w - (big ? 4 : 2), sy0 = Y + 1, sh0 = ly - 2 - sy0
      c.rect(sx, sy0, sw, sh0, "#16171a"); if (big) c.rect(sx, sy0, sw, 1, "#000000"); c.rect(sx, sy0 + sh0 - 1, sw, 1, "#2c2d31")
    }
    // eyes
    const closed = mood !== "green" && mood !== "red" && mood !== "yellow" && mood !== "purple"
    ex.forEach(px => {
      if (mood === "blue") return // face down: no face
      if (closed || mood === "purple") c.rect(px, ey + dy + 1, ew, 1, e)
      else if (mood === "green") { c.rect(px, ey + dy, ew, 1, e); c.px(px - 1, ey + dy + 1, e); c.px(px + ew, ey + dy + 1, e) } // happy arcs
      else c.rect(px, ey + dy, ew, eh, e)
    })
    if (mood === "blue") c.rect(x + 1, Y + 2, w - 2, 1, P.d) // face down: show top of head only
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
      // ponytail: 16px has room for one Z; 22px gets two, half a loop apart
      const n = big ? 2 : 1
      for (let i = 0; i < n; i++) {
        const t = (f + i * 2) % 4, zy = Math.round((big ? 3 : 2) - t * (big ? 1 : 0.7)), zx = (big ? 14 : 11) + i * 3 + (t >> 1)
        if (zy >= 0) z(zx, zy, big ? 2 : 1)
      }
    } else if (mood === "red") {
      // beer mug in right hand, tilts up/down
      const up = f === 1 || f === 2
      const mx = big ? 19 : 14, my = (big ? 0 : 0) + (up ? 0 : 1)
      const mw = big ? 3 : 2, mh = big ? 4 : 3
      c.rect(mx, my + 1, mw, mh - 1, "#f2b01e"); c.rect(mx, my, mw, 1, "#ffffff")
      if (up) c.px(mx + 1, my - 1 < 0 ? my : my - 1, "#ffffff")
    } else if (mood === "blue") {
      // white flag held up, waving
      const px = big ? 20 : 15, top = 0
      c.rect(px, top, 1, big ? 6 : 4, "#8b6b3a")
      const fw = big ? 5 : 4, fh = big ? 3 : 2, off = f % 2
      c.rect(px - fw, top + off % 2 * 0, fw, fh, W)
      c.px(px - fw, top + fh - 1 + off, W)
    } else if (mood === "green") {
      const cols = ["#ff4d6d", "#ffd23f", "#3ec1f0", "#b06bff", "#ffffff"]
      const pts = big ? [[2, 1], [6, 0], [10, 2], [14, 0], [18, 2], [20, 5], [1, 6], [8, 4], [16, 5], [4, 3]] : [[1, 0], [4, 1], [8, 0], [12, 1], [14, 3], [0, 4], [6, 3], [10, 3]]
      pts.forEach(([px, py], i) => c.px(px, (py + f * (big ? 2 : 1) + i % 2) % (big ? 8 : 6), cols[i % 5]))
    } else if (mood === "yellow") {
      const bx = big ? 18 : 13, by = (big ? 0 : 0) + (f === 1 || f === 3 ? 1 : 0)
      const bw = big ? 4 : 3, bh = big ? 5 : 4, bc = "#ff4d6d"
      c.rect(bx, by, bw, bh, bc); c.px(bx + 1, by + 1, "#ffb3c1")
      c.px(bx + (bw >> 1), by + bh, bc)
      c.rect(bx + (bw >> 1), by + bh + 1, 1, (big ? 9 : 7) - bh - by - 1, "#dddddd")
    } else if (mood === "purple") {
      // hawaiian shirt over body: fixed colours
      const sy = ey + dy + (big ? 3 : 2), sh = Y + h - sy; c.rect(x + 1, sy, w - 2, sh, "#1fa6a0")
      for (let i = 0; i < w - 2; i += 3) { c.px(x + 1 + i, sy + (sh > 2 ? (i / 3) & 1 : 0), "#ff5d8f"); if (big) c.px(x + 2 + i, sy + 2 + ((i / 3) & 1), "#ffd23f") }
            // collar V
      c.px(cx - 1, sy, "#ffffff"); c.px(cx, sy, "#ffffff")
      // eyes drawn over shirt would hide; redraw
      ex.forEach(px => c.rect(px, ey + dy + 1, ew, 1, e))
      // tropical drink with umbrella and straw
      const mx = big ? 19 : 14, my = (big ? 1 : 1) + (f === 1 || f === 2 ? 0 : 1)
      c.rect(mx, my + 1, big ? 3 : 2, big ? 4 : 3, "#ff6b3d"); c.px(mx, my + 1, "#ffd23f")
      c.px(mx + 1, my - 1, "#ff4d6d"); c.px(mx + (big ? 2 : 1), my, "#ffffff")
      if (big) { c.px(mx + 1, my - 2, "#ff4d6d") }
    } else if (mood === "teal") {
      const bc = "#bfe9ff"
      const mx = cx, my = Y + (big ? 6 : 4)
      for (let i = 0; i < 3; i++) {
        const t = (f + i * 1.33) % 4, by = Math.round((big ? 7 : 4) - t * (big ? 2 : 1.2))
        const bxx = mx + (big ? 4 : 3) + (i & 1)
        if (t < 3.4 && by >= 0) { c.px(bxx, by, bc); if (big && i === 0) c.px(bxx + 1, by, bc) }
      }
    }
  },
})
