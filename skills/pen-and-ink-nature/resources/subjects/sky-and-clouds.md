# Sky and clouds

Cloud outlines, filled skies, cloud formations, sunrise glow, night sky.

## What makes sky read as sky

**A cloud has to read lighter than anything else on the paper.** Dots carry the same quantity of
ink as lines but read softer, because there is no continuous edge anywhere in a dot field. That is
why the default cloud is drawn with dots and ticks and the default sky is left white.

Two further tests:

- **Cloud edges are wavy.** A cloud with a smooth or geometric boundary reads as a balloon.
- Sky is the one subject where **doing less is usually correct**. Most skies in this style are
  either untouched or carry a single light field.

Cloud density is the mood dial for the whole picture. Heavier density pulls the sky forward and
darkens the scene; a light sky pushes it back and keeps the landscape as the subject.

## Techniques this subject uses

| Part | Technique | Role here |
|---|---|---|
| Cloud body | [stippling](../techniques/stippling.md) | Dots and ticks, density varied inside each cloud. The default |
| Sky field | [hatching](../techniques/hatching.md) | Horizontal or angled parallel lines behind outlined clouds, or across the whole sky |
| Heavy cloud | [hatching](../techniques/hatching.md) | Horizontal parallel lines give a darker, heavier cloud than dots |
| White clouds | [negative space and white reserve](../techniques/negative-space-and-white-reserve.md) | Clouds outlined and left as bare paper against a toned sky |
| Sunrise glow | [negative space and white reserve](../techniques/negative-space-and-white-reserve.md) | A reserved wavy white streak between cloud bodies |
| Cloud outline | [contour lines](../techniques/contour-lines.md) | The wavy boundary itself, kept open and airy |

Mechanics live in those files. What follows is the build order.

## Structural approach

Four routes, in increasing involvement. Pick the lowest one that serves the picture.

1. **Outline only.** Draw cloud outlines and leave the sky implied. Enough whenever the sky is not
   the subject. Keep the outline open and airy — do not close every shape.
2. **Outlined clouds, filled sky.** Draw the outlines, then fill the sky behind them with parallel
   lines or dots. The clouds are now negative space; nothing is drawn inside them.
3. **Clouds drawn directly.** Build the cloud bodies from dots and ticks and leave the sky white.
   **This is the default.** Dots read lighter than lines, and lightness is what a cloud needs.
4. **Full formation.** Lay a background field of dots or fine horizontal lines across the whole
   sky, then build clouds by increasing density locally. Reach for this when the sky is the
   subject.

Rules that apply across all four:

- Dots and lines mix freely in one sky. A cloud toned with dots can sit above a horizon band of
  fine horizontal lines.
- Horizontal parallel lines make a heavier, darker cloud than dots. Keep the cloud's edge wavy
  while laying them, or the band squares off the shape.
- Perspective is size: smaller clouds near the horizon, larger ones overhead and closer.
- A wavy white streak running bottom to top between cloud bodies reads as a sunrise or sunset
  glow. It is reserved, not drawn.
- A night sky is high overall density plus a specific tonal distribution — dark across the field
  with the lighter areas placed deliberately, not scattered.

Where the landscape below carries a lot of reserved white — snow peaks especially — tone the sky
so that its white stops competing. See [rock-and-mountain.md](rock-and-mountain.md).

## Prompt fragment

```
A sky of cumulus clouds in pen and ink, pure black ink on white paper, no grey wash and no
colour. The cloud bodies are built from mixed dots and short ticks, with density varied
inside each cloud — denser along the underside, dissolving to bare paper along the top. The
sky itself is left white. Cloud edges are wavy and irregular with no smooth or geometric
boundary and no hard outline around the dot field. Clouds are smaller near the horizon and
larger overhead. Marks vary in size, ticks share a loose direction within each patch, and the
whole field is hand-drawn rather than evenly distributed.
```

For an outlined-cloud sky, replace the body clause: *clouds are drawn as open wavy outlines and
left as untouched white paper, and the sky behind them is filled with horizontal parallel lines,
denser toward the horizon.*

For a sunrise, add: *a wavy white streak is reserved between the cloud bands, running from the
horizon upward, reading as the glow of a low sun.*

## Failure modes

| Symptom | Correction |
|---|---|
| Clouds read as heavy or solid | Switch from lines to dots and ticks and cut the density |
| Cloud edges look cut out | Dissolve the dot field at the boundary instead of ending it on a line |
| Dot field reads as paper grain | Vary mark size, mix ticks with dots, vary density inside the cloud |
| Sky flattens the landscape | Leave the sky white unless the sky is the subject |
| Clouds all the same size | Smaller at the horizon, larger overhead |
| Glow streak looks drawn | Reserve it; darken the cloud bodies on either side instead |
