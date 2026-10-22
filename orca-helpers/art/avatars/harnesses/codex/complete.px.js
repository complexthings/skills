// Codex complete: the work is done. The white check is the face in every Mood; the cloud
// squashes gently and props (fixed colours) float beside it or rest on it. No arms, no legs.
moodState("codex", "complete", {
  frames: 4, fps: 4,
  draw: (c, { size, mood, P, f }) => {
    const big = size === 24, N = size - 2, W = "#FFFFFF"
    const sq = f === 1 || f === 3 ? 1 : 0, h = (big ? 13 : 9) - sq
    const g = codexCloud(c, { x: 1, y: N - 3 - h, w: big ? 20 : 14, h, P: mood === "default" ? CODEX_P : P, glyph: "check", gdy: 1 })
    const R = g.x + g.w - 1, T = g.y, up = f === 1 || f === 2 ? 1 : 0
    if (mood === "default") {
      // sleeping: Zs drift up from the top-right bump
      const Zc = "#9AD0FF", z = (x, y) => rows(c, x, y, big ? ["ZZZZ", "..Z.", ".Z..", "ZZZZ"] : ["ZZZ", ".ZZ", "ZZ.", "ZZZ"], { Z: Zc })
      for (let i = 0; i < (big ? 2 : 1); i++) { const t = (f + i * 2) % 4, y = T - 4 - t + (big ? 1 : 2); if (y >= 0) z(R - (big ? 4 : 3) + i * 2 + (t >> 1), y) }
    } else if (mood === "red") {
      // beer mug resting on the right shoulder, tipping back for a sip
      const mx = R - (big ? 4 : 3), my = T - (big ? 4 : 3) - up
      rows(c, mx, my, big ? ["FFF.", "BBBH", "BBB.H", "BBBH"] : ["FF.", "BBH", "BBH"], { F: W, B: "#F2B01E", H: "#D8D8D8" })
      if (up) c.px(mx - 1, my, W)
    } else if (mood === "blue") {
      // white flag planted in the cloud's top-left, waving
      const px = g.x + (big ? 4 : 3), top = 0
      c.rect(px, top, 1, T - top + 2, "#8B6B3A")
      const fl = big ? (f % 2 ? ["WWWW.", "WWWWW", ".WWWW"] : ["WWWWW", "WWWWW", "WWWW."]) : (f % 2 ? ["WWW.", "WWWW"] : ["WWWW", "WWW."])
      rows(c, px + 1, top + (f % 2), fl, { W })
    } else if (mood === "green") {
      // confetti raining over and past the cloud
      const cols = ["#FF4D6D", "#FFD23F", "#3EC1F0", "#B06BFF", W], H = big ? 9 : 7
      const pts = big ? [[1, 1], [5, 0], [9, 3], [13, 1], [17, 4], [20, 0], [3, 5], [15, 7], [0, 8], [21, 6]] : [[0, 0], [3, 2], [7, 1], [10, 4], [13, 0], [15, 3], [1, 5], [14, 6]]
      pts.forEach(([x, y], i) => c.px(x, (y + f * 2) % H, cols[i % 5]))
    } else if (mood === "yellow") {
      // red balloon bobbing over the right side, string tied to the cloud
      const bx = R - (big ? 5 : 4), by = up, bw = big ? 4 : 3, bh = big ? 4 : 3
      c.rect(bx, by, bw, bh, "#FF4D6D"); c.px(bx + 1, by + 1, "#FFB3C1")
      c.rect(bx + (bw >> 1), by + bh, 1, T + 1 - by - bh, "#DDDDDD")
    } else if (mood === "purple") {
      // hawaiian print on the lower cloud (below the check), drink with umbrella on top
      const s0 = g.gy + (big ? 4 : 3)
      for (let j = s0; j < T + h; j++) for (let i = g.x + 2; i < R - 1; i++) {
        const k = (i + j * 2) % 5
        if (k === 0) c.px(i, j, "#FF5D8F"); else if (k === 3 && big) c.px(i, j, "#FFD23F")
      }
      const mx = R - (big ? 4 : 3), my = T - (big ? 4 : 3) - up
      rows(c, mx, my, big ? ["..U.", ".UUU", "OOYS", "OOO.", ".O.."] : [".U", "UUS", "OY.", "O.."].slice(0, 4), { U: "#FF4D6D", O: "#FF6B3D", Y: "#FFD23F", S: W })
    } else if (mood === "teal") {
      // bubbles rising off the top
      const bc = "#BFE9FF"
      for (let i = 0; i < 3; i++) {
        const t = (f + i * 1.33) % 4, y = Math.round(T - 1 - t * (big ? 1.6 : 1)), x = g.x + (big ? 6 : 4) + i * (big ? 4 : 3)
        if (y >= 0) { c.px(x, y, bc); if (big && i !== 1) c.px(x + 1, y, bc) }
      }
    }
  },
})
