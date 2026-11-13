# Icon brief (shared by every option file)

Draw with pxl: `node .claude/skills/claude-pxl/bin/pxl.js` (read `.claude/skills/claude-pxl/SKILL.md`
and the Animation section of `reference.md`). Sources live here, one `<type>.px.js` per icon type;
build with `node .claude/skills/claude-pxl/bin/pxl.js build orca-helpers/art/icons/<type>.px.js`,
which writes into the shared `orca-helpers/art/icons/out/`.

- Transparent background, no text inside the icon, readable at 1x.
- Band colors: blue `#00a1ff` (active), green `#1cd000` (complete), gray `#959595` on dark /
  `#595959` on light (upcoming). Darker/lighter shades of the same hue are fine for 2-3 tone depth.
- Every icon must read on both a dark (#1e1e1e) and a light (#ffffff) background.
- Option names: `<type>_1` .. `<type>_N` (N = 3..5). Animated ones are `anim(...)`, seamless loops.
- Animated types also export frame 0 as a still: `sprite("<type>_N_still", { w, h }, stamp("<type>_N", 0, 0, { frame: 0 }))`.
