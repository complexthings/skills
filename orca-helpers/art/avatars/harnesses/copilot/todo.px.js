// The Copilot Wave Band head, shared by todo, progress and complete (they load in that order):
// wide dome, light goggles with navy lenses and a bridge on top, round ear cups, a navy faceplate.
// Only the helmet takes the Mood (P). Returns the faceplate's eye-grid origin. No legs.
const CP_NV = "#14193A", CP_GF = "#E8DDFF"
const copilotHead = (c, size, P, Y, { ad = 0, plate = true } = {}) => {
  const big = size === 24
  if (!big) {
    c.rect(4, Y + 1, 8, 1, P.l); c.rect(3, Y + 2, 10, 1, P.l); c.rect(2, Y + 3, 12, 8, P.m); c.rect(2, Y + 3, 12, 1, P.l)
    c.rect(2, Y + 10, 12, 1, P.d); c.rect(3, Y + 11, 10, 1, P.d)
    for (const x of [0, 14]) { c.rect(x, Y + 5 + ad, 2, 5, P.d); c.px(x + (x ? 1 : 0), Y + 5 + ad, P.l) }
    for (const x of [3, 9]) { c.rect(x, Y, 4, 3, CP_GF); c.px(x, Y, "_"); c.px(x + 3, Y, "_"); c.rect(x + 1, Y + 1, 2, 1, CP_NV) }
    c.rect(7, Y + 1, 2, 1, CP_GF)
    if (plate) { c.rect(3, Y + 4, 10, 6, CP_NV); c.rect(4, Y + 10, 8, 1, CP_NV) }
    return [4, Y + 5]
  }
  c.rect(6, Y + 1, 10, 1, P.l); c.rect(4, Y + 2, 14, 1, P.l); c.rect(3, Y + 3, 16, 13, P.m); c.rect(3, Y + 3, 16, 1, P.l)
  c.rect(3, Y + 15, 16, 1, P.d); c.rect(4, Y + 16, 14, 1, P.d)
  for (const x of [0, 19]) { c.rect(x, Y + 7 + ad, 3, 6, P.d); c.px(x + (x ? 2 : 0), Y + 7 + ad, P.l); c.px(x + (x ? 0 : 2), Y + 12 + ad, P.m) }
  for (const x of [4, 13]) { c.rect(x, Y, 5, 4, CP_GF); c.px(x, Y, "_"); c.px(x + 4, Y, "_"); c.rect(x + 1, Y + 1, 3, 2, CP_NV) }
  c.rect(9, Y + 1, 4, 1, CP_GF)
  if (plate) { c.rect(4, Y + 6, 14, 8, CP_NV); c.rect(5, Y + 14, 12, 1, CP_NV) }
  return [5, Y + 7]
}
// Copilot Todo: still, the default helmet with a Mood expression on the visor (body tint only;
// faceplate, eyes, goggle lenses and the "!" are fixed colours).
{
  // visor grids (inside the navy visor); e = cyan eye, o = mouth (cyan), W = white glint
  const V18 = {
    default: ["........", ".e....e.", ".e....e.", ".e....e.", "........"],
    red:     ["ee....ee", "ee....ee", "........", "..oooo..", "...oo..."],
    blue:    ["........", "........", ".ee..ee.", "..o..o..", "...oo..."],
    green:   ["........", ".e....e.", "e.e..e.e", "..o..o..", "...oo..."],
    yellow:  ["........", "ee....ee", "eW....eW", "........", "...oo..."],
    purple:  ["........", "........", "..ee..ee", "......o.", "....ooo."],
    teal:    ["........", "e.e..e.e", ".e....e.", "........", "..oooo.."],
  }
  const V24 = {
    default: ["............", "..ee....ee..", "..ee....ee..", "..ee....ee..", "..ee....ee..", "............"],
    red:     [".eee....eee.", ".eee....eee.", ".eee....eee.", "............", "...oooooo...", "....oooo...."],
    blue:    ["............", "............", ".eee....eee.", "............", "...o....o...", "....oooo...."],
    green:   ["............", "..ee....ee..", ".e..e..e..e.", "............", "..o......o..", "...oooooo..."],
    yellow:  ["............", ".eee....eee.", ".eWe....eWe.", ".eee....eee.", ".....oo.....", ".....oo....."],
    purple:  ["............", "............", "...eee...eee", "...eee...eee", "...........o", "....oooooo.."],
    teal:    ["............", "............", ".e..e..e..e.", "..ee....ee..", "............", "....oooo...."],
  }
  moodState("copilot", "todo", { frames: 1, draw: (c, { size, mood, P, e }) => {
    const map = { e, o: e, W: "#ffffff" }
    const sag = mood === "teal", up = mood === "red", big = size === 24
    const [fx, fy] = copilotHead(c, size, P, (big ? 2 : 1) + (sag ? 1 : 0), { ad: up ? -1 : sag ? 1 : 0 })
    rows(c, fx, fy, (big ? V24 : V18)[mood], map)
    if (mood === "yellow") {
      if (big) { c.rect(20, 0, 2, 3, "#E53935"); c.rect(20, 4, 2, 2, "#E53935") }
      else { c.px(14, 0, "#E53935"); c.px(14, 1, "#E53935"); c.px(14, 3, "#E53935") }
    }
  } })
}
