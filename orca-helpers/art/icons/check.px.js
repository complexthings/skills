pal({ k: "#063300", G: "#0e8a00", g: "#1cd000", l: "#8dff6e", w: "#ffffff", d: "#0a5c00" })

// 1: bold chunky check, dark outline, highlight stroke
sprite("check_1", { w: 16, h: 16, outline: "k" },
  line(2, 8, 6, 12, "g", 4), line(6, 12, 13, 3, "g", 4),
  line(2, 7, 6, 11, "l", 1), line(6, 11, 13, 2, "l", 1),
  line(3, 10, 6, 13, "G", 1))

// 2: white check in filled green circle badge
sprite("check_2", { w: 18, h: 18 },
  circ(8.5, 8.5, 8, "k"), circ(8.5, 8.5, 7, "g"),
  clip([8.5, 8.5, 7], rect(0, 11, 18, 8, "G")),
  line(4, 9, 7, 12, "w", 2), line(7, 12, 12, 5, "w", 2))

// 3: white check in rounded square
sprite("check_3", { w: 18, h: 18 },
  rect(1, 0, 16, 18, "k"), rect(0, 1, 18, 16, "k"),
  rect(2, 1, 14, 16, "g"), rect(1, 2, 16, 14, "g"),
  rect(2, 14, 14, 2, "G"), rect(1, 14, 16, 1, "G"),
  line(4, 9, 7, 12, "w", 2), line(7, 12, 12, 5, "w", 2))

// 4: thin crisp check with dark-green shade edge
sprite("check_4", { w: 18, h: 18 },
  line(2, 10, 6, 14, "d", 2), line(6, 14, 14, 4, "d", 2),
  line(2, 9, 6, 13, "g", 2), line(6, 13, 14, 3, "g", 2),
  line(2, 8, 6, 12, "l", 1), line(6, 12, 14, 2, "l", 1))

// 5: check with small sparkle
sprite("check_5", { w: 16, h: 16, outline: "k" },
  line(1, 9, 5, 13, "g", 3), line(5, 13, 11, 6, "g", 3),
  line(1, 8, 5, 12, "l", 1), line(5, 12, 11, 5, "l", 1),
  hline(13, 1, 1, "w"), vline(13, 0, 3, "w"), hline(12, 1, 3, "w"))
