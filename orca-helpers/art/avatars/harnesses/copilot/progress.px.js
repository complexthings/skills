// GitHub Copilot progress (In Progress): the Writing typing loop, the Copilot helmet behind a fixed grey keyboard. Props never tint.
moodState("copilot", "progress", {
  frames: 4, fps: 6,
  draw: (c, { size, mood, P, e, f }) => {
    const S = size === 18
    const bx = S ? 2 : 3, bw = S ? 12 : 16
    const ky = S ? 11 : 15, kh = S ? 4 : 6, kw = S ? 14 : 20, kx = 1
    // the shared Copilot head (todo.px.js); the keyboard covers its chin
    const [fx, fy] = copilotHead(c, size, P, S ? 2 : 3)
    // eyes on the faceplate; s = shade lens, g = shade frame, W = glint
    const EY = S ? {
      default: [".e....e.", ".e....e.", ".e....e."],
      red:     ["e......e", ".ee..ee.", ".ee..ee."],
      sleepy:  ["........", "........", ".ee..ee."],
      green:   ["........", ".e....e.", "e.e..e.e"],
      shades:  ["gggggggg", "sWs..sWs", "sss..sss"],
    } : {
      default: ["..ee....ee..", "..ee....ee..", "..ee....ee..", "..ee....ee.."],
      red:     ["ee........ee", ".eee....eee.", "..ee....ee..", "..ee....ee.."],
      sleepy:  ["............", "............", ".eeee..eeee.", "............"],
      green:   ["............", "..ee....ee..", ".e..e..e..e.", "............"],
      shades:  ["gggggggggggg", ".sWss..sWss.", ".ssss..ssss.", ".ssss..ssss."],
    }
    const ek = mood === "blue" || mood === "teal" ? "sleepy" : mood === "yellow" || mood === "purple" ? "shades" : mood === "red" || mood === "green" ? mood : "default"
    rows(c, fx, fy - 1, EY[ek], { e, s: "#05060A", g: "#8A93A6", W: mood === "yellow" ? "#FFFFFF" : "#9AA0AA" })
    // props
    if (mood === "blue") {
      const hp = "#2B2F36", hl = "#7C8594"
      if (S) { c.rect(3, 0, 10, 1, hl); c.rect(2, 1, 12, 1, hp); c.rect(1, 2, 1, 4, hp); c.rect(14, 2, 1, 4, hp); c.rect(0, 6, 2, 5, hp); c.rect(14, 6, 2, 5, hp); c.px(0, 6, hl); c.px(15, 6, hl) }
      else { c.rect(5, 0, 12, 1, hl); c.rect(3, 1, 16, 1, hp); c.rect(2, 2, 1, 7, hp); c.rect(19, 2, 1, 7, hp); c.rect(0, 9, 3, 6, hp); c.rect(19, 9, 3, 6, hp); c.px(0, 9, hl); c.px(1, 9, hl); c.px(20, 9, hl); c.px(21, 9, hl) }
    }
    if (mood === "green") {
      const pk = "#FF5FA2", ye = "#FFD23F"
      if (S) { c.px(7, 0, ye); c.rect(7, 1, 2, 1, pk); c.rect(6, 2, 4, 1, ye); c.rect(5, 3, 6, 1, pk) }
      else { c.rect(10, 0, 2, 1, ye); c.rect(10, 1, 2, 1, pk); c.rect(9, 2, 4, 1, ye); c.rect(9, 3, 4, 1, pk); c.rect(8, 4, 6, 1, ye); c.rect(7, 5, 8, 1, pk) }
    }
    if (mood === "purple") {
      const hat = "#2A2A33", band = "#7A1F3D"
      if (S) { c.rect(4, 0, 8, 2, hat); c.rect(4, 2, 8, 1, band); c.rect(1, 3, 14, 1, hat) }
      else { c.rect(6, 0, 10, 3, hat); c.rect(6, 3, 10, 1, band); c.rect(2, 4, 18, 2, hat) }
    }
    if (mood === "teal") {
      const bn = "#E8744F", bl = "#F5B08F"
      if (S) { c.px(7, 0, bl); c.px(8, 0, bl); c.rect(4, 1, 8, 1, bn); c.rect(3, 2, 10, 2, bn); c.rect(3, 3, 10, 1, bl) }
      else { c.rect(10, 0, 2, 1, bl); c.rect(6, 1, 10, 1, bn); c.rect(4, 2, 14, 2, bn); c.rect(3, 4, 16, 2, bl); c.rect(3, 4, 16, 1, bn) }
    }
    // keyboard (fixed colours)
    c.rect(kx, ky, kw, kh, "#5A616B"); c.rect(kx, ky + kh - 1, kw, 1, "#3B4048")
    const kr = S ? [ky + 1, ky + 2] : [ky + 1, ky + 3]
    kr.forEach(y => { for (let x = kx + 1; x < kx + kw - 1; x += 2) c.px(x, y, "#C9CED6"); if (!S) for (let x = kx + 1; x < kx + kw - 1; x += 2) c.px(x, y + 1, "#C9CED6") })
    const lit = (S ? [[3, 0], [9, 1], [5, 1], [11, 0]] : [[3, 0], [13, 1], [7, 1], [11, 0]])[f]
    c.px(kx + lit[0], kr[lit[1]], "#4FA8E8"); if (!S) c.px(kx + lit[0], kr[lit[1]] + 1, "#4FA8E8")
    // paws, tapping alternately
    const pw = S ? 2 : 3, ph = S ? 2 : 3, py = ky - ph + 1
    ;[[bx + 1, f % 2], [bx + bw - 1 - pw, 1 - f % 2]].forEach(([x, a]) => { c.rect(x, py + a, pw, ph, P.m); c.rect(x, py + a + ph - 1, pw, 1, P.d); c.px(x, py + a, P.l) })
    // teal: coffee in front, steam
    if (mood === "teal") {
      const cx = S ? 7 : 10, cy = S ? 12 : 16, cw = S ? 3 : 4
      c.rect(cx, cy, cw, S ? 3 : 4, "#F4F1EA"); c.rect(cx, cy + (S ? 2 : 3), cw, 1, "#C9BFAE"); c.px(cx + cw, cy + 1, "#F4F1EA"); c.rect(cx, cy, cw, 1, "#6B3F26")
      const sx = cx + 1 + (f % 2), sy = cy - 1 - (f >> 1)
      c.px(sx, cy - 1, "#FFFFFF"); c.px(cx + 1 + ((f + 1) % 2), cy - 2, "#DDEFF0"); if (!S) c.px(sx, cy - 3, "#FFFFFF")
    }
    // red: cursing glyphs, fixed colours, different each frame
    if (mood === "red") {
      const G = { "#": ["#.#", "###", "#.#"], "!": [".#.", ".#.", "..."], "@": ["###", "#.#", "##."], "%": ["#.#", ".#.", "#.#"], "$": ["##.", ".##", "##."] }
      const sets = [["#", "!"], ["@", "%"], ["!", "$"], ["%", "#"]][f], cols = ["#FFD23F", "#FFFFFF"]
      if (S) { rows(c, 0, 0, G[sets[0]], { "#": cols[0] }); rows(c, 13, 0, G[sets[1]], { "#": cols[1] }) }
      else { rows(c, 0, 1, G[sets[0]], { "#": cols[0] }); rows(c, 19, 1, G[sets[1]], { "#": cols[1] }); rows(c, f % 2 ? 9 : 10, 0, G[sets[(f + 1) % 2]], { "#": cols[(f + 1) % 2] }) }
    }
  }
})
