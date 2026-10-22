// Pi: a narrow coral "P" (bowl body over one blue stem leg) beside a tiny yellow "i" companion, reading "Pi".
harness({
  id: "pi", P: { m: "#F09082", d: "#C96B5E", l: "#F8B3A8" }, e: "#2b1710", w: 26, dx: -6,
  legs(c, ctx) {
    const { bx, by, h, legH, C } = ctx, top = by + h - 1
    c.rect(bx, top, 10, legH + 1, C("#4D9ABF")); c.rect(bx, top + legH - 1, 10, 2, C("#35738F"))
  },
  deco(c, ctx) {
    const { bx, by, w, h, C, o, state } = ctx
    ;[[w - 1, 0], [w - 2, 0], [w - 1, 1], [w - 1, h - 1], [w - 2, h - 1], [w - 1, h - 2]].forEach(([x, y]) => c.px(bx + x, by + y, "_"))
    // the i: rounded dot over a short stem, x 37..44, bobbing/tapping with the P
    const lift = (o.legs || [])[3] || 0, sad = state === "disabled"
    const y = (o.dy || 0) + (sad ? 2 : 0) - lift, Y = C("#F1BE58"), D = C("#C9952F"), e = C("#2b1710"), x = 38
    c.rect(x + 1, 33 + y, 4, 4, Y); [[1, 33], [4, 33], [1, 36], [4, 36]].forEach(([a, b]) => c.px(x + a, b + y, "_")); c.px(x + 2, 34 + y, "#FFF0A0")
    c.rect(x, 41 + y, 6, 17 - y, Y); c.rect(x + 5, 41 + y, 1, 17 - y, D); c.rect(x, 56, 6, 2, D)
    if (state === "selected" || state === "main") { c.px(x + 1, 45 + y, e); c.px(x + 4, 45 + y, e); c.rect(x + 2, 47 + y, 2, 1, e) }
    else if (sad || state === "writing" || state === "waiting") { c.rect(x + 1, 46 + y, 2, 1, e); c.rect(x + 4, 46 + y, 1, 1, e) }
    else { c.rect(x + 1, 44 + y, 1, 2, e); c.rect(x + 4, 44 + y, 1, 2, e) }
    if (sad) c.px(x + 1, 47 + y, "#9FB6C4")
  },
})
for (const s of ["todo", "progress", "complete"]) include(`pi/${s}.px.js`)
