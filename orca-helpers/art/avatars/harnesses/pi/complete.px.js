// Pi complete: the work is done. Bowl takes the Mood (P); stem, the "i" and every prop keep fixed colours.
moodState("pi", "complete", {
  frames: 4, fps: 4,
  draw: (c, { size, mood, P, e, f }) => {
    const big = size === 24, G = big ? 21 : 15
    const B = "#4D9ABF", BD = "#35738F", Y = "#F1BE58", YD = "#C9952F", YG = "#FFF0A0"
    // Upright like Todo: wide bowl over one tall stem, the i standing beside it.
    const bw = big ? 12 : 9, bh = big ? 8 : 6, bx = big ? 3 : 2
    const hop = mood === "green" ? (f === 1 || f === 2 ? -1 : 0) : 0
    const by = (big ? 7 : 5) + hop
    // ---- stem leg ----
    const sw = big ? 4 : 3; c.rect(bx, by + bh, sw, G - by - bh + 1, B); c.rect(bx + sw - 1, by + bh, 1, G - by - bh + 1, BD); c.rect(bx, G, sw, 1, BD)
    // ---- bowl ----
    c.rect(bx, by, bw, bh, P.m); c.rect(bx, by, bw, 1, P.l); c.rect(bx, by + bh - 1, bw, 1, P.d); c.rect(bx + bw - 1, by + 1, 1, bh - 1, P.d)
    c.px(bx + bw - 1, by, "_"); c.px(bx + bw - 1, by + bh - 1, "_")
    // ---- the i ----
    {
      const iw = big ? 3 : 2, ix = bx + bw + 2, sy = big ? 12 : 11, dotY = sy - iw - 1
      c.rect(ix, sy, iw, G - sy + 1, Y); c.rect(ix + iw - 1, sy, 1, G - sy + 1, YD); c.rect(ix, G, iw, 1, YD)
      c.rect(ix, dotY, iw, iw, Y); c.px(ix, dotY, YG)
    }
    // ---- face ----
    const W = "#ffffff", Zc = "#9ad0ff"
    const ex = big ? [bx + 2, bx + 7] : [bx + 1, bx + 5], ew = 2
    const dash = (y) => ex.forEach(x => c.rect(x, y, ew, 1, e))
    const ey = by + (big ? 3 : 2), mc = bx + (bw >> 1) - 1
    if (mood === "default") { dash(ey); c.rect(mc, ey + 2, 2, 1, e); if (big) { c.px(mc - 1, ey + 1, e); c.px(mc + 2, ey + 1, e) } }
    else if (mood === "teal") { dash(ey); c.rect(mc, ey + 2, 1, big ? 2 : 1, e); if (big) c.px(mc + 1, ey + 2, e) }
    else if (mood === "blue") { c.rect(bx + 1, by + 1, bw - 3, 2, P.d); ex.forEach(x => c.rect(x, ey + 1, ew, 1, e)) }
    else if (mood === "green") {
      ex.forEach(x => { c.rect(x, ey, ew, 1, e); c.px(x, ey + 1, e); if (big) c.px(x + 1, ey + 1, e) })
      c.rect(mc - 1, ey + 3, 4, 1, e) // grin
    }
    else if (mood === "purple") dash(ey)
    else ex.forEach(x => c.rect(x, ey, ew, big ? 3 : 2, e)) // red, yellow: open
    // ---- props ----
    if (mood === "default") {
      const z = (zx, zy) => {
        if (big) { c.rect(zx, zy, 4, 1, Zc); c.px(zx + 2, zy + 1, Zc); c.px(zx + 1, zy + 2, Zc); c.rect(zx, zy + 3, 4, 1, Zc) }
        else { c.rect(zx, zy, 3, 1, Zc); c.px(zx + 1, zy + 1, Zc); c.rect(zx, zy + 2, 3, 1, Zc) }
      }
      for (let i = 0; i < (big ? 2 : 1); i++) {
        const t = (f + i * 2) % 4, zy = Math.max(0, by - (big ? 5 : 4) - Math.round(t * (big ? 0.5 : 0.4)))
        z(bx + bw - (big ? 3 : 2) + i * 4 + (t >> 1) - (big ? 4 : 0), zy)
      }
    } else if (mood === "teal") {
      const mx = bx + (big ? 3 : 3), my = by - 1
      for (let i = 0; i < 3; i++) {
        const t = (f + i * 1.33) % 4, y = Math.round(my - t * (big ? 2.2 : 1.8)), x = mx + (i & 1) + (big && i === 2 ? 1 : 0)
        if (t < 3.4 && y >= 0) { c.px(x, y, "#bfe9ff"); if (big && i === 0) c.px(x + 1, y, "#bfe9ff") }
      }
    } else if (mood === "blue") {
      const px = bx + (big ? 2 : 1), top = big ? 1 : 1, off = f % 2, fw = big ? 5 : 4, fh = big ? 3 : 2
      c.rect(px, top, 1, by - top, "#8b6b3a"); c.px(px, by - 1, P.m) // arm holds the pole
      c.rect(px + 1, top, fw, fh, W); c.px(px + fw, top + fh - 1 + off, W); c.px(px + 1, top + fh, off ? W : "_")
    } else if (mood === "green") {
      const cols = ["#ff4d6d", "#ffd23f", "#3ec1f0", "#b06bff", "#ffffff"]
      const pts = big ? [[2, 1], [6, 0], [10, 2], [14, 0], [18, 2], [20, 5], [1, 6], [8, 4], [16, 5], [4, 3]] : [[1, 0], [4, 1], [8, 0], [12, 1], [14, 3], [0, 4], [6, 3], [10, 3]]
      pts.forEach(([px, py], i) => c.px(px, (py + f * (big ? 2 : 1) + i % 2) % (big ? 8 : 6), cols[i % 5]))
      // arms up
      c.rect(bx - 1, by + (f & 1) - 1, 1, big ? 3 : 2, P.m); c.rect(bx + bw, by + ((f + 1) & 1) - 1, 1, big ? 3 : 2, P.m)
    } else if (mood === "yellow") {
      const bby = f === 1 || f === 3 ? 1 : 0, balx = bx + (big ? 2 : 2), bwd = big ? 4 : 3, bht = big ? 4 : 3, bc = "#ff4d6d"
      c.rect(balx, bby, bwd, bht, bc); c.px(balx + 1, bby + 1, "#ffb3c1"); c.px(balx + (bwd >> 1), bby + bht, bc)
      c.rect(balx + (bwd >> 1), bby + bht + 1, 1, by - bby - bht - 1, "#dddddd")
      c.px(balx + (bwd >> 1), by - 1, P.m)
    } else if (mood === "red") {
      const up = f === 1 || f === 2, mw = big ? 3 : 2, mh = big ? 5 : 3, mx = big ? 1 : 0, my = by + 2 + (up ? -1 : 0)
      c.rect(bx - (big ? 1 : 1), by + 3, 1, big ? 2 : 1, P.m); if (big) c.rect(bx - 1, by + 3, 1, 2, P.m)
      c.rect(mx, my + 1, mw, mh, "#f2b01e"); c.rect(mx, my, mw, 1, W)
      if (big) { c.px(mx - 1, my + 2, "#d8d8d8"); c.px(mx - 1, my + 3, "#d8d8d8") }
      if (up) c.px(mx, my - 1, W)
    } else if (mood === "purple") {
      const sy = by + (big ? 4 : 3), sh = by + bh - sy
      c.rect(bx + 1, sy, bw - 3, sh, "#1fa6a0")
      for (let i = 0; i < bw - 3; i += 2) { c.px(bx + 1 + i, sy + 1 + ((i >> 1) & 1), "#ff5d8f"); if (big && i % 4 === 0) c.px(bx + 2 + i, sy + 2, "#ffd23f") }
      c.px(bx + (bw >> 1) - 1, sy, W); c.px(bx + (bw >> 1), sy, W)
      const up = f === 1 || f === 2, mx = big ? 1 : 0, my = by + 3 + (up ? -1 : 0)
      c.rect(bx - 1, by + 4, 1, big ? 2 : 1, P.m)
      c.rect(mx, my + 1, big ? 3 : 2, big ? 4 : 2, "#ff6b3d"); c.px(mx, my + 1, "#ffd23f")
      c.px(mx + 1, my - 1, "#ff4d6d"); c.px(mx + (big ? 2 : 1), my, W); if (big) c.px(mx + 1, my - 2, "#ff4d6d")
    }
  },
})
