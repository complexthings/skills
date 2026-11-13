// Antigravity Todo: still, the standing "A" with a Mood expression (body gradient: logo on default, P.l to P.d on other Moods; "!" is a fixed colour).
{
  // face grids per size and mood; e = eye colour, o = mouth (eye colour), W = white glint
  const F18 = {
    default: [".........." , ".ee....ee.", ".ee....ee."],
    red:     [".ee....ee.", ".ee....ee.", ".ee....ee.", "..........", "..oooooo..", "...oooo..."],
    blue:    ["..........", "..........", ".ee....ee.", "..........", "..o....o..", "...oooo..."],
    green:   ["..........", "..e....e..", ".e.e..e.e.", "..........", "..o....o..", "...oooo..."],
    yellow:  ["..........", ".ee....ee.", ".eW....eW.", "..........", "....oo....", "....oo...."],
    purple:  ["..........", "..........", "..ee....ee", "..........", ".......o..", "....oooo.."],
    teal:    ["..........", ".e.e..e.e.", "..e....e..", "..........", "....oo...."],
  }
  const F24 = {
    default: ["............", "..ee....ee..", "..ee....ee..", "..ee....ee.."],
    red:     ["..ee....ee..", "..ee....ee..", "..ee....ee..", "..ee....ee..", "............", "...oooooo...", "....oooo...."],
    blue:    ["............", "............", "............", ".eee....eee.", "............", "...o....o...", "....oooo...."],
    green:   ["............", "..ee....ee..", ".e..e..e..e.", "............", "..o......o..", "...oooooo...", "............"],
    yellow:  ["............", ".eee....eee.", ".eWe....eWe.", ".eee....eee.", "............", ".....oo.....", ".....oo....."],
    purple:  ["............", "............", "...eee...eee", "...eee...eee", "...........o", "....oooooo..", "............"],
    teal:    ["............", "............", ".e..e..e..e.", "..ee....ee..", "............", "....oooo....", "............"],
  }
  // body spans per row: [x0, x1] or [x0, x1, x2, x3] (inner arch notch between), hand-drawn per size
  const S18 = { 2: [5, 10], 3: [4, 11], 4: [3, 12], 5: [3, 12], 6: [2, 13], 7: [2, 13], 8: [2, 13], 9: [2, 13],
    10: [2, 6, 9, 13], 11: [2, 5, 10, 13], 12: [2, 5, 10, 13], 13: [1, 5, 10, 14], 14: [0, 4, 11, 15], 15: [0, 4, 11, 15] }
  const S24 = { 3: [8, 13], 4: [6, 15], 5: [5, 16], 6: [4, 17], 7: [4, 17], 8: [3, 18], 9: [3, 18], 10: [3, 18], 11: [3, 18],
    12: [3, 18], 13: [3, 18], 14: [3, 9, 12, 18], 15: [3, 8, 13, 18], 16: [3, 8, 13, 18], 17: [2, 7, 14, 19], 18: [2, 6, 15, 19],
    19: [1, 5, 16, 20], 20: [0, 4, 17, 21], 21: [0, 4, 17, 21] }
  const has = (S, x, y) => { const r = S[y]; return !!r && (x >= r[0] && x <= r[1] || r.length > 2 && x >= r[2] && x <= r[3]) }
  // logo gradient on default; other Moods run P.l (top-left) through P.m to P.d (bottom-right)
  const rgb = (s) => [1, 3, 5].map((i) => parseInt(s.slice(i, i + 2), 16))
  const tint = (mood, P, u, v) => { if (mood === "default") return agBody(mood, P, u, v)
    const t = Math.min(1, Math.max(0, 0.75 * v + 0.25 * u))
    return agHex(t < 0.5 ? agMix(rgb(P.l), rgb(P.m), t * 2) : agMix(rgb(P.m), rgb(P.d), t * 2 - 1)) }
  moodState("antigravity", "todo", { frames: 1, draw: (c, { size, mood, P, e }) => {
    const map = { e, o: e, W: "#ffffff" }, teal = mood === "teal", up = mood === "red"
    const S = size === 18 ? S18 : S24, n = size - 4, top = size === 18 ? 2 : 3, W = size - 2
    for (const y in S) for (let x = 0; x < W; x++) if (has(S, x, +y)) {
      const v = (y - top) / (W - top - 1)
      c.px(x, +y, !has(S, x, +y + 1) && mood === "default" ? P.d : tint(mood, P, x / (W - 1), v))
    }
    const as = size === 18 ? 2 : 3, ay = size === 18 ? (up ? 6 : teal ? 8 : 7) : (up ? 8 : teal ? 11 : 10)
    for (const x of [0, W - as]) for (let i = 0; i < as; i++) for (let j = 0; j < as; j++)
      c.px(x + i, ay + j, tint(mood, P, x / (W - 1), (ay + j - top) / (W - top - 1)))
    if (size === 18) {
      rows(c, 3, teal ? 5 : 4, F18[mood], map)
      if (mood === "yellow") { c.px(14, 0, "#E53935"); c.px(14, 1, "#E53935"); c.px(14, 3, "#E53935") }
    } else {
      rows(c, 5, teal ? 6 : 5, F24[mood], map)
      if (mood === "yellow") { c.rect(20, 0, 2, 3, "#E53935"); c.rect(20, 4, 2, 2, "#E53935") }
    }
  } })
}
