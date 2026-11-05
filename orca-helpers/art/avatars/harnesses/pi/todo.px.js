// Pi Todo: still, the standing "P" with a Mood expression (bowl tint only; stem leg, "i" and "!" are fixed colours).
{
  const F18 = {
    default: ["........", "........", ".ee..ee.", ".ee..ee."],
    red:     [".ee..ee.", ".ee..ee.", "........", ".oooooo.", "..oooo.."],
    blue:    ["........", "........", ".ee..ee.", "........", ".o....o.", "..oooo.."],
    green:   ["........", ".e....e.", "e.e..e.e", "........", ".o....o.", "..oooo.."],
    yellow:  ["........", ".ee..ee.", ".eW..eW.", "........", "...oo...", "...oo..."],
    purple:  ["........", "........", "..ee..ee", "........", ".......o", "...oooo."],
    teal:    ["........", "e.e..e.e", ".e....e.", "........", "...oo..."],
  }
  const F24 = {
    default: ["............", "............", "..ee....ee..", "..ee....ee..", "..ee....ee.."],
    red:     ["..ee....ee..", "..ee....ee..", "..ee....ee..", "..ee....ee..", "............", "...oooooo...", "....oooo...."],
    blue:    ["............", "............", "............", ".eee....eee.", "............", "...o....o...", "....oooo...."],
    green:   ["............", "..ee....ee..", ".e..e..e..e.", "............", "..o......o..", "...oooooo...", "............"],
    yellow:  ["............", ".eee....eee.", ".eWe....eWe.", ".eee....eee.", "............", ".....oo.....", ".....oo....."],
    purple:  ["............", "............", "...eee...eee", "...eee...eee", "...........o", "....oooooo..", "............"],
    teal:    ["............", "............", ".e..e..e..e.", "..ee....ee..", "............", "....oooo....", "............"],
  }
  const BL = "#4D9ABF", BD = "#35738F", Y = "#F1BE58", YD = "#C9952F", GL = "#FFF0A0", RED = "#E53935"
  moodState("pi", "todo", { frames: 1, draw: (c, { size, mood, P, e }) => {
    const map = { e, o: e, W: "#ffffff" }
    if (size === 18) {
      c.rect(0, 1, 10, 8, P.m); c.rect(0, 1, 10, 1, P.l); c.rect(0, 8, 10, 1, P.d)
      c.px(9, 1, "_"); c.px(9, 8, "_")
      c.rect(0, 9, 3, 6, BL); c.rect(2, 9, 1, 6, BD); c.rect(0, 14, 3, 1, BD)
      c.rect(12, 7, 2, 2, Y); c.px(12, 7, GL); c.px(13, 8, YD)
      c.rect(12, 10, 2, 5, Y); c.rect(13, 10, 1, 5, YD); c.rect(12, 14, 1, 1, YD)
      rows(c, 1, 2, F18[mood], map)
      if (mood === "yellow") { c.px(13, 0, RED); c.px(13, 1, RED); c.px(13, 3, RED) }
    } else {
      c.rect(0, 1, 14, 12, P.m); c.rect(0, 1, 14, 1, P.l); c.rect(0, 12, 14, 1, P.d)
      c.px(13, 1, "_"); c.px(12, 1, "_"); c.px(13, 2, "_"); c.px(13, 12, "_"); c.px(12, 12, "_"); c.px(13, 11, "_")
      c.rect(0, 13, 4, 9, BL); c.rect(3, 13, 1, 9, BD); c.rect(0, 20, 4, 2, BD)
      c.rect(16, 8, 4, 3, Y); c.px(16, 8, GL); c.px(19, 8, "_"); c.px(19, 10, YD); c.rect(16, 10, 3, 1, Y)
      c.rect(16, 12, 4, 10, Y); c.rect(19, 12, 1, 10, YD); c.rect(16, 20, 4, 2, YD)
      c.px(16, 15, e); c.px(18, 15, e); c.px(16, 16, e); c.px(18, 16, e)
      rows(c, 1, 2, F24[mood], map)
      if (mood === "yellow") { c.rect(17, 0, 2, 3, RED); c.rect(17, 4, 2, 2, RED) }
    }
  } })
}
