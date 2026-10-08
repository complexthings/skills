# Stippling

Stippling here means **dots and ticks** — that is the phrase the source drawings use, and it
belongs in the prompt. A tick is not a dot: it is a very short directional dash. The mixture of
the two is what separates this mark from mechanical dot screen.

## The mark

A field of round dots mixed with short dashes, roughly half and half with the ticks slightly in
the majority. Within any one patch the ticks share a loose common direction; across the drawing
that direction changes with the surface. Dot sizes vary.

The mark's defining property is that it has **no continuous edge**. The same quantity of ink
laid as lines reads harder than laid as dots, which is why this is the mark for soft, granular
and atmospheric subjects.

It is slow to draw by hand. That cost is why the source uses it where softness matters and
reaches for parallel lines everywhere else — useful context when deciding which technique a
subject wants.

## Tonal control

Density alone: more marks per unit area is darker. There is no second dial. Two consequences
worth holding:

1. **The tonal range is finer than any line technique.** Dots give the smallest available step
   between one tone and the next, which is why stone surfaces use them for close control.
2. **The dark end is limited.** A dot field cannot reach true black without becoming a solid
   blot. Deep darks in a stippled area come from tapered strokes placed among the dots.

Edges are a density control too. A stippled area should thin out into white rather than stop on
a boundary — the dissolve is how the mark says "mist", "sand" or "cloud" instead of "patch".

## Where it works on natural subjects

- **Cloud and sky.** The cloud body itself, and the sky field around outlined white clouds.
- **Mountain planes.** The primary texturing mark for a mountain surface.
- **Stone.** Fine surface tone where a plane needs a subtle step, not a whole second pass.
- **Flower petals.** Dots and ticks read as delicacy; a continuous line reads as a hard edge.
- **Water's broken edge.** The ragged front of a wave and the mist thrown back from it.
- **Sand and shore**, and **spring foliage** scattered on bare twigs.
- **Sky on a snow drawing**, specifically so white sky stops competing with white snow.

It is the wrong mark for a flat plane that needs even grey quickly — a ground plane or a bank
face wants parallel lines — and for anything whose direction the viewer must read, since a dot
field carries almost no direction.

## Prompt language

- "pen and ink, texture built from dots and short ticks, no continuous lines"
- "dots vary in size; the short ticks in each area share a loose common direction"
- "density varied inside the form: dense at the base, thinning to bare paper at the top"
- "the dotted area dissolves into white at its edges, no hard boundary"
- "pure black ink on white paper, no grey wash, no colour, no photographic rendering"

Say **dots and ticks**. "Stippling" alone pulls image models toward a uniform round-dot screen,
which is the main failure this technique has.

### `gpt-image-2`

`gpt-image-2` has two reliable defaults to counter. It produces a perfectly even random
field that reads as paper grain, so name the variation as structure ("density clearly varied
across the form, dense in the shadowed area, sparse in the lit area"). And it renders round dots
only, so name the tick explicitly and separately ("a mixture of round dots and very short dashes,
the dashes more numerous"). It also renders dot fields with clean geometric boundaries; ask for
the dissolve in the same sentence as the field.

## Failure modes

| What comes back | What to add |
| --- | --- |
| Even random field, reads as noise or paper grain | "density clearly varied across the form, with light and dark regions" |
| All dots identical in size | "dots of varied size, some heavier than others" |
| Pure round dots, mechanical | "a mixture of round dots and very short directional dashes" |
| Dot field with a hard geometric edge | "the dots thin out and dissolve into bare white paper at the edges" |
| Halftone or printed screen look | "hand-drawn ink dots, irregularly placed, no regular grid or halftone" |
| Grey wash where the dots should be | "individual visible ink dots, no grey tone, no airbrush" |
| Ticks pointing every direction at random | "within each area the short dashes share one loose direction" |

## Contact sheet

[stippling.png](stippling.png) — left half is the mixed dot-and-tick field at three
densities with dissolving edges; right half is a cloud bank built from dots and ticks with
density varied inside each cloud, sky left white, smaller clouds toward the horizon.
