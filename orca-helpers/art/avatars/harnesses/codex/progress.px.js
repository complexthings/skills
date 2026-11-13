// Codex progress (In Progress): the cloud types behind a fixed grey keyboard, bobbing a pixel, cursor blinking,
// a lit key moving each frame. The keyboard hides the feet. Props never tint.
moodState("codex", "progress", {
  frames: 4, fps: 6,
  draw: (c, { size, mood, P, f }) => {
    const S = size === 18, b = f % 2 // bob: down on odd frames
    const g = codexCloud(c, { x: 1, y: (S ? 3 : 4) + b, w: S ? 14 : 20, h: S ? 9 : 12, P: mood === "default" ? CODEX_P : P,
      tilt: f === 1 ? 1 : f === 3 ? -1 : 0, feet: false, glyph: f < 2 ? "prompt" : "blink" })
    const T = g.y, R = g.x + g.w - 1, gy = (S ? 6 : 8) + b // cloud top/right edge, glyph row (tilt-proof)
    // hats and headgear rest on the cloud top
    if (mood === "blue") { // headphones: band over the top, cups on the sides
      const hp = "#2B2F36", hl = "#7C8594"
      c.rect(3, T - 1, g.w - 4, 1, hp); c.rect(4, T - 2, g.w - 6, 1, hl)
      c.rect(0, gy - 1, 2, S ? 4 : 5, hp); c.rect(R, gy - 1, 2, S ? 4 : 5, hp)
    }
    if (mood === "green") { // party hat
      const pk = "#FF5FA2", ye = "#FFD23F", m = S ? 7 : 10
      c.px(m, T - 4, ye); c.rect(m, T - 3, 2, 1, pk); c.rect(m - 1, T - 2, 4, 1, ye); c.rect(m - 2, T - 1, 6, 1, pk)
    }
    if (mood === "purple") { // fedora
      const hat = "#2A2A33", band = "#7A1F3D", w = S ? 8 : 10, x = S ? 4 : 6
      c.rect(x, T - 3, w, 2, hat); c.rect(x, T - 1, w, 1, band); c.rect(x - 2, T, w + 4, 1, hat)
    }
    if (mood === "teal") { // beanie
      const bn = "#E8744F", bl = "#F5B08F", x = S ? 4 : 5, w = S ? 8 : 12
      c.rect(x + w / 2 - 1, T - 3, 2, 1, bl); c.rect(x, T - 2, w, 1, bn); c.rect(x - 1, T - 1, w + 2, 1, bn); c.rect(x - 1, T, w + 2, 1, bl)
    }
    if (mood === "yellow" || mood === "purple") { // shades on the brow, above the >_
      const gl = mood === "yellow" ? "#15151A" : "#0B0B0F", hi = mood === "yellow" ? "#FFFFFF" : "#9AA0AA", y = gy - 2, lw = S ? 3 : 4
      const L = S ? 3 : 4, Rx = S ? 10 : 14
      c.rect(L, y, lw, 2, gl); c.rect(Rx, y, lw, 2, gl); c.rect(L + lw, y, Rx - L - lw, 1, gl); c.px(L, y, hi); c.px(Rx, y, hi)
    }
    // keyboard (fixed colours) over the cloud's bottom
    const ky = S ? 12 : 16, kh = S ? 4 : 6, kw = S ? 14 : 20, kx = 1
    c.rect(kx, ky, kw, kh, "#5A616B"); c.rect(kx, ky + kh - 1, kw, 1, "#3B4048")
    const kr = S ? [ky + 1, ky + 2] : [ky + 1, ky + 3]
    kr.forEach(y => { for (let x = kx + 1; x < kx + kw - 1; x += 2) { c.px(x, y, "#C9CED6"); if (!S) c.px(x, y + 1, "#C9CED6") } })
    const lit = (S ? [[3, 0], [9, 1], [5, 1], [11, 0]] : [[3, 0], [13, 1], [7, 1], [11, 0]])[f]
    c.px(kx + lit[0], kr[lit[1]], "#4FA8E8"); if (!S) c.px(kx + lit[0], kr[lit[1]] + 1, "#4FA8E8")
    if (mood === "teal") { // coffee on the keyboard's right corner, steam drifting
      const cw = S ? 3 : 4, ch = S ? 3 : 4, cx = S ? 12 : 17, cy = S ? 13 : 18
      c.rect(cx, cy, cw, ch, "#F4F1EA"); c.rect(cx, cy + ch - 1, cw, 1, "#C9BFAE"); c.rect(cx, cy, cw, 1, "#6B3F26")
      c.px(cx + 1 + b, cy - 1, "#FFFFFF"); c.px(cx + 2 - b, cy - 2, "#DDEFF0")
    }
    if (mood === "red") { // cursing glyphs, different each frame
      const G = { "#": ["#.#", "###", "#.#"], "!": [".#.", ".#.", "..."], "@": ["###", "#.#", "##."], "%": ["#.#", ".#.", "#.#"], "$": ["##.", ".##", "##."] }
      const sets = [["#", "!"], ["@", "%"], ["!", "$"], ["%", "#"]][f]
      rows(c, 0, 0, G[sets[0]], { "#": "#FFD23F" }); rows(c, S ? 13 : 19, 0, G[sets[1]], { "#": "#FFFFFF" })
    }
  }
})
