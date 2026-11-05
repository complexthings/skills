// Claude Code mascot ("Clawd") avatars. Canvas 46x62 + 1px outline = 48x64.
pal({k:"#2b1710", m:"#D97757", d:"#B85C3E", l:"#F0A283", e:"#1e120e", w:"#FFF4E6",
 g:"#9B9B9B", h:"#6E6E6E", j:"#C4C4C4", n:"#4A4A4A",
 y:"#F5C842", Y:"#C98F1C", Z:"#FFF0A0", R:"#E0443C", B:"#4FA8E8",
 S:"#C9CED6", s:"#8A929E", t:"#5A616B", p:"#F4A6B8", o:"#8B5A2B", O:"#6B4220", c:"#9FB6C4"})

const rows = (c, x, y, g, map = {}) => g.forEach((r, j) => [...r].forEach((ch, i) => { if (ch !== ".") c.px(x + i, y + j, map[ch] || ch) }))
const EYES = {
  sq: ["eeee","eeee","eeee","eeee"], tall: ["eee","eee","eee","eee","eee"], wide: ["eeeeee","eeeeee","eeeeee"],
  happy: ["....",".ee.","e..e"], closed: ["....","....","eeee"], half: ["....","....","eeee","eeee"],
  sad: ["...e","..ee","eeee","eeee"], x: ["e..e",".ee.",".ee.","e..e"],
}
const MOUTH = { smile: ["e....e",".eeee."], frown: [".eeee.","e....e"], flat: ["eeee"], o: ["ee","ee"], open: ["eeeeee",".eeee."] }
const rev = (g) => g.map((r) => [...r].reverse().join(""))

// shared base character
function clawd(c, o = {}) {
  const { w = 34, h = 22, legH = 8, dx = 0, dy = 0, eye = "sq", ex = 0, ey = 0, mouth = null, gl = false, blush = false,
    P = ["m", "d", "l"], legs = [0, 0, 0, 0], aL = {}, aR = {}, arms = true, inset = 7, eyeY = 6, dith = false } = o
  const [m, d, l] = P
  const bx = Math.round((46 - w) / 2) + dx, by = 58 - legH - h + dy
  const lx = [bx + 3, bx + 10, bx + w - 15, bx + w - 8]
  lx.forEach((x, i) => {
    c.rect(x, by + h - 1, 5, legH + 1 - legs[i], m)
    c.rect(x, by + h + legH - legs[i] - 2, 5, 2, d)
  })
  c.rect(bx, by, w, h, m)
  c.rect(bx, by, w, 2, l); c.rect(bx, by + 2, 1, h - 5, l)
  c.rect(bx + w - 2, by + 2, 2, h - 2, d); c.rect(bx, by + h - 3, w, 3, d)
  if (dith) { c.dither(bx + 2, by + 2, w - 4, 3, m, l, 0.35); c.dither(bx + 2, by + h - 6, w - 4, 3, m, d, 0.35) }
  c.px(bx, by, "_"); c.px(bx + w - 1, by, "_")
  if (arms) [[-1, aL], [1, aR]].forEach(([s, a]) => {
    const x = s < 0 ? bx - 4 : bx + w, ah = a.h ?? 6, ay = by + (a.y ?? 9)
    c.rect(x, ay, 4, ah, m); c.rect(x, ay + ah - 2, 4, 2, d); c.px(x + (s < 0 ? 0 : 3), ay, l)
  })
  const E = EYES[eye], EW = E[0].length, y0 = by + eyeY + ey
  rows(c, bx + inset + ex, y0, E, { e: "e" })
  rows(c, bx + w - inset - EW + ex, y0, eye === "sad" ? rev(E) : E, { e: "e" })
  if (gl) { c.px(bx + inset + ex, y0, "w"); c.px(bx + w - inset - EW + ex, y0, "w") }
  if (blush) { c.rect(bx + inset - 1 + ex, y0 + 6, 3, 2, "p"); c.rect(bx + w - inset - 2 + ex, y0 + 6, 3, 2, "p") }
  if (mouth) { const M = MOUTH[mouth]; rows(c, bx + w / 2 - M[0].length / 2 + ex, by + eyeY + 9 + (o.my || 0), M, { e: "e" }) }
  return { bx, by }
}
function crown(c, x, y, tilt = 0, sweep = -99) {
  const R = ["yy......yyy......yy", "yyy.....yyy.....yyy", "yZyy...yyZyy...yyZy", "yyyyyyyyyyyyyyyyyyy",
    "yyyRyyyyyByyyyyRyyy", "YYYYYYYYYYYYYYYYYYY"]
  R.forEach((r, j) => [...r].forEach((ch, i) => {
    if (ch === ".") return
    const s = Math.round(tilt * (5 - j) / 5)
    c.px(x + i + s, y + j, (i + j * 2 - sweep >= 0 && i + j * 2 - sweep < 3) ? (ch === "R" || ch === "B" ? "w" : "Z") : ch)
  }))
}
function spark(c, x, y, s) { if (s === 1) c.px(x, y, "w"); if (s === 2) { c.px(x, y, "w"); [[1,0],[-1,0],[0,1],[0,-1]].forEach(([a, b]) => c.px(x + a, y + b, "Z")) } }
const dash = (c, x, y, len, col) => { for (let i = 0; i < len; i++) if (i % 5 !== 3) c.px(x + i, y, col) }

const S = (name, fn) => sprite(name, { w: 46, h: 62, outline: "k" }, fn)
const A = (name, frames, fps, fn) => anim(name, { w: 46, h: 62, outline: "k", frames, fps }, (c) => fn(c, c.phase * Math.PI * 2, c.frame))

// ---- default ----
S("default_1", (c) => clawd(c))
S("default_2", (c) => clawd(c, { w: 28, h: 26, legH: 6, eye: "tall", gl: true, inset: 6, eyeY: 7, dith: true, aL: { y: 11 }, aR: { y: 11 } }))
S("default_3", (c) => clawd(c, { w: 36, h: 18, legH: 9, eye: "wide", inset: 8, eyeY: 5, blush: true, mouth: "smile", my: -2 }))

// ---- selected (dancing) ----
A("selected_1", 6, 8, (c, k, f) => {
  const hop = Math.round(4 * Math.abs(Math.sin(k))), up = f % 2 === 0
  clawd(c, { h: hop ? 22 : 20, dy: -hop, eye: "happy", mouth: "smile",
    aL: up ? { y: -5, h: 8 } : { y: 12, h: 5 }, aR: up ? { y: 12, h: 5 } : { y: -5, h: 8 } })
})
A("selected_2", 8, 8, (c, k) => {
  const s = Math.round(5 * Math.sin(k)), a = Math.round(3 * Math.sin(k * 2)), fl = Math.cos(k) > 0
  clawd(c, { dx: s, eye: "sq", gl: true, mouth: "open", legs: fl ? [2, 0, 2, 0] : [0, 2, 0, 2], aL: { y: 4 + a }, aR: { y: 4 - a } })
})
A("selected_3", 8, 8, (c, k, f) => {
  const p = Math.round(2 * Math.sin(k)), note = ["..ee", "..e.", "..e.", ".ee.", ".ee."]
  clawd(c, { dy: Math.round(Math.sin(k * 2)), eye: "happy", mouth: "smile", aL: { y: -6 + p, h: 9 }, aR: { y: -6 - p, h: 9 } })
  rows(c, 9, 20 - 2 * f, note, { e: "y" }); rows(c, 33, 20 - 2 * ((f + 4) % 8), note, { e: "y" })
})

// ---- main orchestrator (crown) ----
A("main_1", 6, 6, (c, k, f) => {
  const dy = Math.round(Math.sin(k)), { by } = clawd(c, { dy, eye: "sq", gl: true })
  crown(c, 13, by - 5)
  const spots = [[14, by - 7], [23, by - 7], [31, by - 7]], sp = spots[Math.floor(f / 2)]
  spark(c, sp[0], sp[1], f % 2 ? 2 : 1)
})
A("main_2", 6, 5, (c, k, f) => {
  const b = Math.round(1.5 * Math.sin(k)), { by } = clawd(c, { dy: b, eye: "happy", mouth: "smile", aL: { y: 5, h: 5 }, aR: { y: 5, h: 5 } })
  crown(c, 13, by - 5 + (f === 2 || f === 3 ? 1 : 0) - (f === 0 ? 1 : 0))
  spark(c, f % 2 ? 6 : 38, by - 8, 2); spark(c, f % 2 ? 40 : 4, by - 3, 1)
})
A("main_3", 8, 8, (c, k, f) => {
  const t = Math.round(2 * Math.sin(k)), { by } = clawd(c, { eye: "wide", gl: true, inset: 8, ex: t, eyeY: 7, mouth: "smile", my: 1 })
  crown(c, 13, by - 5, t, f * 4 - 4)
})

// ---- disabled (gray, sad) ----
const G = ["g", "h", "j"]
S("disabled_1", (c) => clawd(c, { P: G, h: 18, legH: 6, eyeY: 5, eye: "sad", mouth: "frown", my: -2, aL: { y: 8, h: 8 }, aR: { y: 8, h: 8 } }))
S("disabled_2", (c) => { clawd(c, { P: G, h: 20, legH: 7, eye: "half", eyeY: 6, mouth: "flat", my: -2, aL: { y: 10, h: 7 }, aR: { y: 10, h: 7 } }); c.rect(14, 42, 2, 4, "c"); c.px(14, 46, "c") })
S("disabled_3", (c) => {
  clawd(c, { P: G, w: 36, h: 18, legH: 6, eye: "closed", eyeY: 5, mouth: "frown", my: -2, aL: { y: 8, h: 8 }, aR: { y: 8, h: 8 } })
  c.circ(15, 13, 4, "j"); c.circ(24, 10, 5, "j"); c.circ(31, 14, 4, "j"); c.rect(15, 14, 17, 4, "j"); c.rect(15, 17, 17, 2, "g")
  ;[[17, 21], [24, 23], [30, 20]].forEach(([x, y]) => c.vline(x, y, 3, "c"))
})

// ---- writing ----
A("writing_1", 4, 6, (c, k, f) => {
  clawd(c, { eye: "half", ex: f < 2 ? -1 : 1, eyeY: 6, arms: false })
  c.rect(3, 44, 40, 12, "S"); c.box(3, 44, 40, 12, "s"); c.rect(1, 56, 44, 3, "t"); c.circ(23, 50, 2, "m")
  ;[[7, f % 2], [34, 1 - f % 2]].forEach(([x, a]) => { c.rect(x, 40 + a, 5, 5, "m"); c.rect(x, 43 + a, 5, 2, "d"); c.box(x, 40 + a, 5, 5, "d") })
})
A("writing_2", 6, 6, (c, k, f) => {
  const px = Math.round(2 * Math.sin(k)), len = 8 + f * 3
  clawd(c, { eye: "half", ey: 0, mouth: null, aR: { y: 9 } })
  c.rect(6, 47, 34, 13, "w"); c.box(6, 47, 34, 13, "g")
  dash(c, 9, 50, 28, "t"); dash(c, 9, 53, 22, "t"); dash(c, 9, 56, len, "t")
  const tx = 9 + len + px
  c.line(39, 41, tx + 7, 44, "m", 3); c.line(tx, 56, tx + 7, 45, "y", 2); c.px(tx, 56, "k")
})
A("writing_3", 6, 4, (c, k, f) => {
  const done = Math.floor(f / 2), row = Math.min(done, 2), ry = 46 + row * 5
  clawd(c, { eye: "half", ex: 0, arms: false })
  c.rect(11, 40, 24, 20, "o"); c.box(11, 40, 24, 20, "O"); c.rect(18, 38, 10, 4, "s"); c.rect(13, 43, 20, 15, "w")
  for (let i = 0; i < 3; i++) {
    const y = 45 + i * 5; c.box(15, y, 3, 3, "n"); dash(c, 20, y + 1, 11, "t")
    if (i < done) { c.px(15, y + 1, "R"); c.px(16, y + 2, "R"); c.px(17, y + 1, "R"); c.px(18, y, "R"); c.px(19, y - 1, "R") }
  }
  c.rect(7, 46, 5, 8, "m"); c.rect(7, 52, 5, 2, "d")
  const bob = f % 2
  c.line(39, 40, 33, ry - 4 + bob, "m", 3); c.line(28, ry + bob, 34, ry - 6 + bob, "y", 2); c.px(28, ry + bob, "k")
})

// ---- waiting ----
A("waiting_1", 4, 4, (c, k, f) => {
  clawd(c, { eye: "sq", ex: f === 2 ? -1 : 2, mouth: "flat", my: 0, aR: { y: 9 } })
  const b = f % 2, tip = [[32, 35], [34, 37], [32, 39], [30, 37]][f]
  c.line(39, 38 + b, 33, 37 + b, "m", 4)
  c.rect(29, 34 + b, 7, 7, "n"); c.rect(30, 35 + b, 5, 5, "w"); c.px(32, 37 + b, "e"); c.px(tip[0], tip[1] + b, "e")
})
A("waiting_2", 4, 4, (c, k, f) => {
  const dn = f % 2 === 1
  clawd(c, { eye: "half", ex: f < 2 ? -2 : 2, mouth: "flat", legs: [0, 0, 0, dn ? 0 : 3], aL: { y: 10 }, aR: { y: 10 } })
  if (dn) { c.px(40, 58, "y"); c.px(41, 56, "y"); c.px(40, 54, "y") }
})
A("waiting_3", 8, 6, (c, k, f) => {
  clawd(c, { eye: "sq", ey: -1, mouth: "flat", legs: [0, 0, 0, f % 2 ? 0 : 2], aR: { y: -8, h: 12 } })
  c.circ(23, 12, 8, "w"); c.ring(23, 12, 8, "n")
  ;[[23, 5], [23, 19], [16, 12], [30, 12]].forEach(([x, y]) => c.px(x, y, "n"))
  c.line(23, 12, 23 + Math.round(5 * Math.sin(k)), 12 - Math.round(5 * Math.cos(k)), "e")
  c.line(23, 12, 26, 12, "R")
})
