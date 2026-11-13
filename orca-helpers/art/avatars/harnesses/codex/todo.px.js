// Codex Todo: still, waiting to start. Each Mood is told with the cloud's squash/tilt, feet,
// the white ">_" and at most one tiny fixed-colour prop outside the cloud.
{
  // Per mood: dh (squash -/stretch +), dy, tilt, feet, glyph, gdx, gdy.
  const M = {
    default: {},
    red: { dh: -1, dy: 1, tilt: 1, feet: [0, 0], gdy: 1 },  // hunched forward, steaming
    blue: { dh: -2, dy: 2, glyph: "dim", gdy: 1 },          // slumped low, a tear
    green: { dh: 1, dy: -1, feet: [1, 1] },                 // perked up on tiptoe, a sparkle
    yellow: { dh: 2, dy: -1, feet: [2, 0], gdy: -1 },       // jolted tall, "!"
    purple: { tilt: -1, gdx: 2 },                           // leaning back, prompt glancing aside
    teal: { dh: -2, dy: 2, tilt: -1, glyph: "dim", gdy: 1 }, // drooped and drowsy, a "z"
  }
  moodState("codex", "todo", { frames: 1, draw: (c, { size, mood, P }) => {
    const S = size === 18, m = M[mood], h = (S ? 10 : 14) + (m.dh || 0), y = (S ? 2 : 3) + (m.dy || 0)
    const g = codexCloud(c, { x: 1, y, w: S ? 14 : 20, h, P: mood === "default" ? CODEX_P : P, tilt: m.tilt, feet: m.feet ?? true, glyph: m.glyph || "prompt", gdx: m.gdx, gdy: m.gdy })
    const R = "#FF5A4E", B = "#CFEFFF"
    if (mood === "red") rows(c, S ? 13 : 18, 0, S ? ["R.R", ".R.", "R.R"] : ["R..R", ".RR.", ".RR.", "R..R"], { R })
    if (mood === "blue") rows(c, 0, S ? 6 : 8, S ? [".B", "BB"] : [".B.", "BBB", ".B."], { B })
    if (mood === "green") spark(c, S ? 14 : 19, 1, 2)
    if (mood === "yellow") rows(c, S ? 15 : 20, 0, S ? ["Y", "Y", ".", "Y"] : ["YY", "YY", "YY", "..", "YY"], { Y: R })
    if (mood === "teal") rows(c, S ? 12 : 17, 0, S ? ["ZZZ", ".Z.", "ZZZ"] : ["ZZZZ", "..Z.", ".Z..", "ZZZZ"], { Z: "#E8F4FF" })
    return g
  } })
}
