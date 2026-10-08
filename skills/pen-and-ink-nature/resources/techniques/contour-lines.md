# Contour lines

A curved line that reports the shape of the surface under it. Contour lines are the
difference between a trunk, a stone or a wave reading as a solid form and reading as a flat
shape with texture on it.

## The mark

A single curved stroke whose curvature follows the surface, drawn freehand so the curve is
never mechanically regular. Lines run in sets, roughly parallel to each other, all bending the
same way the form bends.

Two variants, and the choice between them is the whole file:

- **Continuous** — an unbroken curve. Reads as firm and hard-edged. Correct for rock, snow
  ridges, ground planes and water surfaces.
- **Soft** — the same curve made of broken segments, dashes or dots. Reads as delicate.
  Correct for petals, mist edges and anything that should not have a hard boundary. The corpus
  is explicit here: an unbroken line on a petal destroys the petal.

Contour lines differ from parallel lines (see [`hatching.md`](hatching.md)) in what sets the
angle. Parallel lines take one angle across a whole plane. Contour lines change angle
continuously because the surface does.

## Tonal control

Contour lines are a form device first and a tonal device second, but the tone is real and the
corpus uses it: **more lines, closer together, on the part of the surface curving away from the
light.** Sparse on the lit side, dense on the turning side, and the form appears.

That gives the same three controls as any other mark here — count, proximity, and where you
stop. There is no heavier pen and no pressure change.

The hard ceiling: contour lines eat white. The corpus warns against overworking inclined
ground for exactly this reason. On a snow peak the interior line count is the mood dial — more
lines makes the peak heavier and less soft, and past a point the snow stops reading as snow.
Stop while the paper still dominates.

## Where it works

- **Inclined ground** beside a stream or below a waterfall. The angle of the lines declares the
  angle of the ground, and nothing else in the drawing has to say it.
- **Undulating middle ground** in a landscape — curved rather than straight ground lines give
  the plane its rise and fall.
- **Snow peaks.** Sparse wavy lines inside the peak tone the surface and describe its form in
  one pass. This is the corpus's showcase use.
- **Tree trunks**, as curved lines running across the trunk rather than along it — an
  alternative to the wandering bark line when roundness matters more than bark.
- **Petals**, in the soft broken variant.
- **River water** following the river's bend, so the water surface reads as lying flat and
  moving.

## Where it fails

Anything with no coherent surface to follow. Foliage masses, mist and spray have no continuous
form for the curve to report, so contour lines there read as arbitrary squiggles. Use
[`scribble-strokes.md`](scribble-strokes.md) or dots and ticks instead.

Flat planes are the other miss. A vertical rock face or a still-water surface wants parallel
lines at one angle; bending them invents a curvature the form does not have.

## Prompt language

Model-agnostic. Name the surface, then the curve's job:

- "curved lines following the form of the surface, ink pen, hand-drawn, no ruler"
- "sparse curved lines across the peak, closer together where the surface turns away from the
  light, most of the paper left white"
- "broken dotted contour lines describing the petal's curve, soft, no hard outline"
- "the line angle declares the slope of the ground"

Two phrases carry most of the weight. **"following the form"** is what separates this from
hatching in a model's output. **"curvature changes across the surface"** stops the model
drawing a set of identical arcs.

### `gpt-image-2`

`gpt-image-2` defaults to even, evenly-spaced arcs and to grey fill between them. Two
corrections, both worth stating up front:

- "pure black ink on white paper, no grey, no wash, no colour"
- "line spacing varies; some lines break and restart; no two curves identical"

For the soft variant, ask for the break explicitly — "dashed and dotted, the line breaks
repeatedly" — because the model treats a broken line as an error and closes it.

## Failure modes

| Symptom | Correcting phrase |
| --- | --- |
| Curves contradict the form — arcs bending the wrong way | "every curve follows the direction the surface bends" |
| Even, ruled, identical arcs | "hand-drawn, uneven spacing, no two lines the same length" |
| Hard continuous lines on a soft subject | "broken, dotted contour lines; the outline never closes" |
| So many lines the white is gone | "sparse — leave most of the paper untouched" |
| Grey gradient instead of separated lines | "pure black line work, no grey tone, no blur" |

The first and fourth are the expensive ones. Curvature that contradicts the form makes the
drawing wrong rather than merely plain, and a lost white field cannot be recovered by adding
anything — see [`negative-space-and-white-reserve.md`](negative-space-and-white-reserve.md).

## Contact sheet

[contour-lines.png](contour-lines.png)
