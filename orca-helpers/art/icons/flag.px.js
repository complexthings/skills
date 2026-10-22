pal({ k: "#141414", w: "#f4f4f4", e: "#6f8aa3", b: "#00a1ff", B: "#0a68b0", h: "#8fd4ff" })

// Waving cloth: column i is shifted by amp*sin(phase - i*wl); cell = checker size; hFn(i) = height at column i.
function cloth(c, x0, y0, cols, h, cell, amp, wl, opt = {}) {
  const k = c.phase * Math.PI * 2
  const ph = opt.ph || 0
  for (let i = 0; i < cols; i++) {
    const damp = amp * Math.min(1, (i + 1) / 3) // pinned at the pole
    const dy = Math.round(damp * Math.sin(k - i * wl + ph))
    const hh = opt.hFn ? opt.hFn(i) : h
    const top = y0 + dy + (opt.yFn ? opt.yFn(i) : 0)
    for (let j = 0; j < hh; j++) {
      const edge = j === 0 || j === hh - 1 || i === cols - 1
      const chk = (Math.floor(i / cell) + Math.floor(j / cell)) % 2
      c.px(opt.rev ? x0 + cols - 1 - i : x0 + i, top + j, edge ? "e" : chk ? "w" : "k")
    }
    // keep the dark checks readable: edge pixel above/below covers the outline
  }
}
function pole(c, x, y0, y1, w = 1) {
  for (let i = 0; i < w; i++) c.line(x + i, y0, x + i, y1, i ? "B" : "b")
  c.px(x, y0 - 1 < 0 ? 0 : y0 - 1, "h")
}

// 1: classic, fine 2px checks
anim("flag_1", { w: 18, h: 18, frames: 6, fps: 7 }, (c) => {
  pole(c, 2, 1, 17, 2)
  cloth(c, 4, 3, 13, 9, 2, 1.0, 0.8)
})
// 2: coarse 3x3 checks, bigger swing
anim("flag_2", { w: 18, h: 18, frames: 6, fps: 7 }, (c) => {
  pole(c, 2, 1, 17, 2)
  cloth(c, 4, 3, 12, 9, 3, 1.8, 0.55)
})
// 3: long sine ripple, pole at bottom-left, flag streams out
anim("flag_3", { w: 18, h: 18, frames: 8, fps: 8 }, (c) => {
  pole(c, 1, 0, 17, 2)
  cloth(c, 3, 5, 15, 7, 2, 2.2, 0.62, { yFn: (i) => Math.round(i * 0.1) })
})
// 4: pennant, tapers to a waving tip
anim("flag_4", { w: 18, h: 18, frames: 6, fps: 7 }, (c) => {
  pole(c, 2, 1, 17, 2)
  const h = (i) => 12 - Math.round(i * 0.7)
  cloth(c, 4, 2, 14, 0, 2, 1.1, 0.6, { hFn: h, yFn: (i) => Math.round((12 - h(i)) / 2) })
})
// 5: two small crossed flags
anim("flag_5", { w: 18, h: 18, frames: 6, fps: 7 }, (c) => {
  c.line(4, 17, 10, 3, "b"); c.line(13, 17, 7, 3, "B")
  c.line(5, 17, 11, 3, "B"); c.line(14, 17, 8, 3, "b")
  pole(c, 10, 2, 3); pole(c, 7, 2, 3)
  cloth(c, 11, 2, 6, 6, 2, 1, 0.9)
  cloth(c, 1, 2, 6, 6, 2, 1, 0.9, { ph: 2, rev: 1 })
})
for (let n = 1; n <= 5; n++) sprite(`flag_${n}_still`, { w: 18, h: 18 }, stamp(`flag_${n}`, 0, 0, { frame: 0 }))
