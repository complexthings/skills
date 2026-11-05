// Claude Todo: still, the standing Clawd with a Mood expression (body tint only; "!" is a fixed colour).
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
  moodState("claude", "todo", { frames: 1, draw: (c, { size, mood, P, e }) => {
    const map = { e, o: e, W: "#ffffff" }
    const teal = mood === "teal", up = mood === "red"
    if (size === 18) {
      const T = teal ? 4 : 3, ay = up ? 3 : teal ? 7 : 6
      c.rect(2, T, 12, 11 - T, P.m); c.rect(2, T, 12, 1, P.l); c.rect(2, 10, 12, 1, P.d)
      c.rect(0, ay, 2, 2, P.m); c.rect(14, ay, 2, 2, P.m)
      for (const x of [3, 5, 10, 12]) c.rect(x, 11, 1, 2, P.d)
      rows(c, 3, T + 1, F18[mood], map)
      if (mood === "yellow") { c.px(14, 0, "#E53935"); c.px(14, 1, "#E53935"); c.px(14, 3, "#E53935") }
    } else {
      const T = teal ? 5 : 4, ay = up ? 4 : teal ? 9 : 8
      c.rect(3, T, 16, 15 - T, P.m)
      c.rect(3, T, 16, 1, P.l); c.rect(3, 14, 16, 1, P.d)
      c.rect(0, ay, 3, 3, P.m); c.rect(19, ay, 3, 3, P.m)
      for (const x of [4, 7, 14, 17]) c.rect(x, 15, 2, 3, P.d)
      rows(c, 5, T + 1, F24[mood], map)
      if (mood === "yellow") { c.rect(20, 0, 2, 3, "#E53935"); c.rect(20, 4, 2, 2, "#E53935") }
    }
  } })
}
