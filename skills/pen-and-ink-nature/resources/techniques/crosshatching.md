# Crosshatching

Crosshatching is a **second set of parallel lines laid over the first at an angle**. In this
style it is a narrow, specific tool, not a general way to build darkness.

## Scope

The source drawings barely use it. They name it once, as an alternative for toning a stone's
side, and the behaviour otherwise appears under the phrase "another set of parallel lines".
Their answer to "this needs to be darker" is usually a denser single pass or a cluster of
tapered darks. Treat crosshatching as the right mark for two subjects — worked stone and
weathered wood — and reach for [`hatching.md`](hatching.md) or the tapered dark everywhere else.

## The mark

One pass of parallel lines, then a second pass across it at an angle. Both passes are freehand
and neither is a ruled grid. The crossings are uneven, the angle between passes wanders, and
some crossings are missed entirely. That looseness is the whole difference between drawn stone
and printed fabric.

## Tonal control

Each pass is one step darker. The working range is **one pass, two passes, or a heavier second
pass** — three steps, and that is the top of the range. Deeper black comes from a solid tapered
dark laid beside the crosshatched area, not from a third and fourth crossing pass.

Angle between passes is a texture control rather than a tonal one. A shallow angle keeps the
lattice open and directional; a near-right angle closes it into a mesh and reads mechanical.
Favour shallow and uneven.

## Where it works on natural subjects

- **Stone.** Deepening one face after the first pass is down. A three-quarter stone reads as
  solid when its left face, right face and top each carry a different pass count.
- **Mountain planes.** Pushing one plane from two tones to three, same move as stone at scale.
- **Weathered wood.** A post or a fence rail, where the loose crossings read as splitting grain.
  Here the irregularity is the subject, not just an anti-mechanical safeguard.

It fails on organic, soft or moving subjects. Foliage, water, snow, cloud, petals and grass all
reject it — a lattice implies a woven or cut surface, which is exactly what those subjects are
not. If a prompt returns crosshatched water, the fix is a different technique, not a better
crosshatch.

## Prompt language

- "pen and ink, two sets of parallel lines crossing at a shallow angle, loose and uneven"
- "the shadowed face carries a second pass of lines; the lit face carries one pass only"
- "crossings irregular, some lines missing, never a regular grid or mesh"
- "pure black ink on white paper, no grey wash, no colour"

Name the pass count rather than the darkness: "one pass here, two passes there" gives the model
a countable instruction where "darker on the left" gives it a licence to reach for grey.

### `gpt-image-2`

`gpt-image-2`'s default crosshatch is a clean ruled mesh, and it is a strong default —
one word of correction rarely beats it. Two things that do: describe the passes as separate
drawing actions ("first a set of lines running one way, then a second set drawn across them by
hand"), and forbid the grid by naming the positive alternative in the same breath ("crossings
uneven and scattered, the two directions at a shallow wandering angle"). It also tends to
crosshatch the whole subject uniformly; state which face gets the second pass and which stays
at one.

## Failure modes

| What comes back | What to add |
| --- | --- |
| Regular mesh, screen or fabric texture | "loose uneven crossings, wandering angle, some crossings missing" |
| Passes at a right angle | "the second set crosses at a shallow angle, roughly thirty degrees" |
| Four or more passes, area gone black | "at most two passes; the darkest accents are solid tapered strokes, not more crossings" |
| Crosshatch applied to foliage or water | Drop the technique for that element and name its own mark instead |
| Uniform crosshatch over every face | "one pass on the lit face, two on the shadowed face, top face nearly bare" |
| Ruler-straight lines | "hand-drawn lines, each wavering slightly, unequal in length" |

## Contact sheet

[crosshatching.png](crosshatching.png) — left half is one pass, two passes and a heavier
second pass; right half is a three-quarter-view stone with the shadowed face carrying the
second pass, irregular darkened edges, and a few tapered crevices.
