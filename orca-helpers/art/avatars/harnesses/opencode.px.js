// OpenCode: the blocky "O" mark, on two legs. Light frame body, dark square screen with light eyes and mouth.
harness({
  id: "opencode", P: { m: "#d4d4d4", d: "#8f8f8f", l: "#f5f5f5" }, e: "#f5f5f5", outline: "#0a0a0a",
  // Two legs only; the waiting foot tap (o.legs[3]) lifts the right leg.
  legs(c, { bx, by, w, h, legH, m, d, o }) {
    const lift = (o.legs || [])[3] || 0
    ;[[bx + 5, 0], [bx + w - 13, lift]].forEach(([x, up]) => {
      c.rect(x, by + h - 1, 8, legH + 1 - up, m)
      c.rect(x, by + h + legH - up - 2, 8, 2, d)
    })
  },
  deco(c, { bx, by, w, h, d, C, eyes, E, e, o }) {
    c.rect(bx + 5, by + 4, w - 10, h - 8, C("#16171a"))
    c.rect(bx + 5, by + 4, w - 10, 1, C("#000000"))
    c.rect(bx + 5, by + h - 5, w - 10, 1, C("#2c2d31"))
    eyes.forEach(([x, y]) => rows(c, x, y, E, { e }))
    if (o.mouth) { const M = MOUTH[o.mouth]; rows(c, bx + w / 2 - M[0].length / 2 + (o.ex || 0), by + 15 + (o.my || 0), M, { e }) }
  },
})
for (const s of ["todo", "progress", "complete"]) include(`opencode/${s}.px.js`)
