// GitHub Copilot complete: the work is done. Props use fixed colours; only the helmet and ear cups use P,
// the navy faceplate and cyan eyes stay fixed. Same Mood props as the Claude pilot, no legs.
moodState("copilot", "complete", {
  frames: 4, fps: 4,
  draw: (c, { size, mood, P, e, f }) => {
    const big = size === 24
    // the shared Copilot head (todo.px.js) at full Todo proportions, low in the frame to leave room for props
    const dy = mood === "default" || mood === "yellow" || mood === "teal" || mood === "blue" ? 1 : 0
    const Y = (big ? 3 : 2) + dy, x = big ? 3 : 2, w = big ? 16 : 12, h = big ? 17 : 12
    const shirt = mood === "purple", face = mood !== "blue"
    const [fx, fy] = copilotHead(c, size, P, Y, { plate: face })
    if (!face) { c.rect(x + 1, Y + (big ? 8 : 6), w - 2, 1, P.d); c.rect(x + 1, Y + (big ? 11 : 8), w - 2, 1, P.d) } // face down: back of the helmet only
    else {
      const EY = big ? {
        closed: ["............", "............", ".eee....eee."],
        green:  ["............", "..ee....ee..", ".e..e..e..e."],
        open:   ["..ee....ee..", "..ee....ee..", "..ee....ee..", "..ee....ee.."],
      } : {
        closed: ["........", "........", ".ee..ee."],
        green:  ["........", ".e....e.", "e.e..e.e"],
        open:   [".e....e.", ".e....e.", ".e....e."],
      }
      const ek = mood === "default" || mood === "teal" || shirt ? "closed" : mood === "green" ? "green" : "open"
      rows(c, fx, fy - (shirt ? 1 : 0), EY[ek], { e })
    }
    const W = "#ffffff", Zc = "#9ad0ff"
    // ---- props ----
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
        const t = (f + i * 2) % 4, zy = Math.round((big ? 5 : 4) - t * (big ? 1.5 : 1)), zx = (big ? 12 : 9) + i * 3 + (t >> 1)
        if (zy >= 0) z(zx, zy, big ? 2 : 1)
      }
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
      const px = big ? 18 : 13, top = big ? 1 : 0
      c.rect(px, top, 1, big ? 8 : 6, "#8b6b3a")
      const fw = big ? 5 : 4, fh = big ? 3 : 2, off = f % 2
      c.rect(px - fw, top + off % 2 * 0, fw, fh, W)
      c.px(px - fw, top + fh - 1 + off, W)
    } else if (mood === "green") {
      const cols = ["#ff4d6d", "#ffd23f", "#3ec1f0", "#b06bff", "#ffffff"]
      const pts = big ? [[2, 1], [6, 0], [10, 2], [14, 0], [18, 2], [20, 5], [1, 6], [8, 4], [16, 5], [4, 3]] : [[1, 0], [4, 1], [8, 0], [12, 1], [14, 3], [0, 4], [6, 3], [10, 3]]
      pts.forEach(([px, py], i) => c.px(px, (py + f * (big ? 2 : 1) + i % 2) % (big ? 8 : 6), cols[i % 5]))
    } else if (mood === "yellow") {
      const bx = big ? 17 : 12, by = (big ? 0 : 0) + (f === 1 || f === 3 ? 1 : 0)
      const bw = big ? 4 : 3, bh = big ? 5 : 4, bc = "#ff4d6d"
      c.rect(bx, by, bw, bh, bc); c.px(bx + 1, by + 1, "#ffb3c1")
      c.px(bx + (bw >> 1), by + bh, bc)
      c.rect(bx + (bw >> 1), by + bh + 1, 1, (big ? 9 : 6) - bh - by - 0, "#dddddd")
    } else if (mood === "purple") {
      // hawaiian shirt over body: fixed colours
      const sy = Y + (big ? 11 : 8), sh = Y + h - sy; c.rect(x + 1, sy, w - 2, sh, "#1fa6a0")
      for (let i = 0; i < w - 2; i += 3) { c.px(x + 1 + i, sy + (sh > 2 ? (i / 3) & 1 : 0), "#ff5d8f"); if (big) c.px(x + 2 + i, sy + 2 + ((i / 3) & 1), "#ffd23f") }
            // collar V
      c.px(cx - 1, sy, "#ffffff"); c.px(cx, sy, "#ffffff")
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
        const bxx = mx + (big ? 4 : 3) + (i & 1)
        if (t < 3.4 && by >= 0) { c.px(bxx, by, bc); if (big && i === 0) c.px(bxx + 1, by, bc) }
      }
    }
  },
})
