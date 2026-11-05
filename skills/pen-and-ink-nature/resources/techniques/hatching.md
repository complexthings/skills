# Hatching

Hatching is **parallel lines** — that is the phrase the source drawings use, it is the phrase
that belongs in an image prompt, and it is the workhorse that lays almost every area of even
grey in this style.

## The mark

A run of roughly parallel strokes, drawn freehand. Lengths and intervals are slightly unequal
because a hand made them. Each run sits at one angle, and the angle carries meaning on its own:

| Angle on a form | What the viewer reads |
| --- | --- |
| Vertical | A deep vertical cut, a bank face, a still-water reflection |
| Horizontal | A ledge, a path, a ground plane, a cloud body |
| Angled | A tilted plane |

Same mark, three readings, purely from direction. Set the angle before you set the density.

## Tonal control

Two controls, both about count and position — never a darker pen and never more pressure.

1. **Spacing.** More lines in the same span reads darker. This is the primary dial.
2. **Shortening.** Progressively shorten the lines toward one end and the band fades out.
   This is how a plane dies away instead of stopping on a hard edge.

Stay off the ceiling: past a certain density the lines fuse into solid black and the surface
disappears. When an area needs to go darker than dense hatching allows, the style's answer is a
second pass at an angle (see `crosshatching.md`) or a cluster of tapered darks, not more lines
in the same direction.

## Where it works on natural subjects

Strong on anything with a readable plane: mountain flanks and mountain background tone, ground
planes, the depth face of a river bank, still water and its reflections, a stone's side faces,
sky behind outlined clouds, distant foliage masses read as one grey shape, and bark running
along a trunk.

Weak where the subject has no plane to declare. Foliage close enough that individual leaf
clusters matter, broken water, mist, snow surfaces and flower petals all fight hatching — the
regularity of the run contradicts the subject's disorder. Those want scribble, dots and ticks,
or reserved white instead.

Scale rule: for the same subject at greater distance, use fewer and shorter lines. Distance in
this style is coded by density and size, not by blur.

## Prompt language

Model-agnostic phrasing. Name the mark, the angle, the density and the fade, in that order.

- "pen and ink, parallel lines, hand-drawn lines of slightly uneven length and spacing"
- "vertical parallel lines, closely spaced, on the shadowed plane; wider spacing on the lit plane"
- "the line band fades out by shortening the lines toward its lower edge, no hard boundary"
- "pure black ink on white paper, no grey wash, no colour, no photographic rendering"

Say **parallel lines** rather than "hatching" or "shading". "Shading" pulls image models toward
smooth grey; "parallel lines" pulls them toward discrete strokes.

### `gpt-image-2`

`gpt-image-2` renders hatching mechanically even by default — a ruled fill rather
than a drawn one. Two additions carry most of the correction: name the irregularity as a
positive property ("each line slightly wavering, unequal in length, drawn by hand"), and name
the tonal steps as a count rather than as an adjective ("three separate line densities: sparse,
medium, dense, visibly stepped"). It also drifts to grey; repeat "pure black ink on white
paper" in the same sentence as the mark, not only at the end of the prompt.

## Failure modes

| What comes back | What to add |
| --- | --- |
| Ruled, machine-even lines | "hand-drawn lines, uneven spacing, each line wavering slightly" |
| Every line the same length | "lines of varied length, the band ragged along its edges" |
| The band ends on a hard straight edge | "the line band fades by shortening the lines toward one end" |
| Dense area fused into solid black | "keep white paper visible between the lines even in the darkest area" |
| Smooth grey instead of strokes | "individual visible pen strokes, no grey wash, no airbrush" |
| One flat density over the whole subject | "three distinct densities across the form: dark third, middle third, near-white third" |

## Contact sheet

[hatching.png](hatching.png) — left half is the mark at three densities with one band
showing the shorten-to-fade taper; right half is a mountain flank whose planes each carry
parallel lines at their own angle.
