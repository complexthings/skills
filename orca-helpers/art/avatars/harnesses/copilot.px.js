// GitHub Copilot: the mascot. Purple-to-blue dome helmet, pilot goggles pushed up on the
// forehead, navy face visor with tall cyan pill eyes, round blue ear cups.
function copilotDeco(c, { bx, w, by, h, C, o, eyes }) {
  const P1 = C("#9B6CF0"), P2 = C("#7E63EA"), B1 = C("#5B6EE6"), B2 = C("#3F6AD8"), BD = C("#2F4FB0")
  const NV = C("#14193A"), RIM = C("#5FA8F5"), GR = C("#C9B3FF"), GL = C("#3A2A78"), GS = C("#E8DDFF")
  const CY = C("#12F0F5"), EC = C("#3A7BEA"), ECD = C("#2552B8")
  // Helmet shading, purple at the top to blue at the bottom
  for (let j = 0; j < h; j++) c.rect(bx, by + j, w, 1, j < h * 0.25 ? P1 : j < h * 0.5 ? P2 : j < h * 0.75 ? B1 : B2)
  c.rect(bx, by + h - 2, w, 2, BD)
  // Dome: round the top corners
  ;[[0, 5], [1, 3], [2, 2], [3, 1], [4, 1]].forEach(([j, n]) => { c.rect(bx, by + j, n, 1, "_"); c.rect(bx + w - n, by + j, n, 1, "_") })
  // Ear cups
  ;[bx - 1, bx + w - 4].forEach((x) => { c.rect(x + 1, by + 9, 3, 7, EC); c.rect(x, by + 10, 5, 5, EC); c.rect(x + 1, by + 14, 3, 2, ECD); c.px(x + 1, by + 10, GS) })
  // Visor
  const vx = bx + 5, vy = by + 8, vw = w - 10, vh = h - 11
  c.rect(vx + 1, vy, vw - 2, vh, RIM); c.rect(vx, vy + 1, vw, vh - 2, RIM)
  c.rect(vx + 2, vy + 1, vw - 4, vh - 2, NV); c.rect(vx + 1, vy + 2, vw - 2, vh - 4, NV)
  // Goggles on the forehead
  const gy = by + 2
  ;[bx + 7, bx + w - 16].forEach((x) => {
    c.rect(x + 1, gy, 7, 6, GR); c.rect(x, gy + 1, 9, 4, GR)
    c.rect(x + 2, gy + 1, 5, 4, GL); c.rect(x + 1, gy + 2, 7, 2, GL); c.px(x + 2, gy + 1, GS); c.px(x + 3, gy + 1, GS)
  })
  c.rect(bx + 16, gy + 2, w - 32, 2, GR)
  // Eyes: tall cyan pills, per-state shapes
  const ey = vy + 1 + (o.ey || 0)
  eyes.forEach(([x0], i) => {
    const x = x0 + (i ? -3 : 4)
    if (o.eye === "happy") { c.rect(x - 1, ey + 3, 1, 2, CY); c.rect(x, ey + 2, 3, 1, CY); c.rect(x + 3, ey + 3, 1, 2, CY) }
    else if (o.eye === "half") { c.rect(x, ey + 4, 3, 3, CY); c.rect(x + 1, ey + 7, 1, 1, CY); c.rect(x, ey + 4, 3, 1, C("#0B8F94")) }
    else { c.rect(x, ey + 1, 3, 6, CY); c.rect(x + 1, ey, 1, 8, CY); c.px(x + 1, ey + 1, C("#E6FFFF")) }
  })
  if (o.mouth === "smile") { const mx = bx + w / 2 - 2; c.px(mx - 1, ey + 6, CY); c.rect(mx, ey + 7, 4, 1, CY); c.px(mx + 4, ey + 6, CY) }
}
harness({ id: "copilot", P: { m: "#5B6EE6", d: "#2F4FB0", l: "#9B6CF0" }, e: "#12F0F5", deco: copilotDeco })
for (const s of ["todo", "progress", "complete"]) include(`copilot/${s}.px.js`)
