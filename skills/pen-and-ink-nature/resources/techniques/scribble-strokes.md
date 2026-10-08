# Scribble strokes

A continuous, unlifted, wandering loop. The corpus's fastest way to fill a mass of vegetation
where the individual leaf does not matter. The pen never leaves the paper, and that is both the
technique's advantage and the source of its one characteristic failure.

## The mark

One stroke that loops back over itself repeatedly, wandering as it goes, drawn without lifting.
The loops are uneven in size and spacing because the hand is moving quickly.

Two near-neighbours the corpus uses alongside it, worth naming because they are visually
distinct and prompt differently:

- **The leaf stroke** — an individual small open loop, shaped like a single leaf seen from a
  distance. Drawn one at a time, not continuously. This is the base mark for deciduous foliage
  at close range.
- **Loopy lines** — a connected chain of loops running in one direction. Between the leaf
  stroke and full scribble in looseness.

All three share one property that separates them from every line technique in this skill: they
have **no dominant direction**. That directionlessness is what makes them read as foliage
rather than bark. See [`directional-and-tapered-strokes.md`](directional-and-tapered-strokes.md)
for the opposite case.

## Tonal control

Two dials, and they combine:

- **How tightly wound the loop is.** A tight loop puts more ink in the same span.
- **How much the loops overlap.** More overlap is darker.

Tighter and more overlapped is darker; open and loose is lighter. As everywhere in this skill,
tone is count and proximity — there is no second pen.

The corpus's foliage rule sets the direction of the gradient: **light at the top, dark at the
bottom**, because the light is overhead. A scribble mass with even tone throughout is flat, and
flat foliage reads as a shrub-shaped smudge.

Distance is coded the usual way — a farther mass is smaller, looser and carries fewer marks.

## Where it works

- **Deciduous foliage masses.** The primary use. Organise the crown into masses with white gaps
  between them, not one continuous field.
- **Pine trees in a quick winter landscape**, where the needle structure would be too slow.
- **Riverside and mid-distance vegetation**, paired with tapered darks for the trunks and
  branches showing through.
- **Foreground bushes** in a layered composite scene.

## Where it fails

Anywhere the viewer can resolve individual structure. A near tree in the foreground wants leaf
strokes or defined foliage masses; scribble at that distance reads as scribble. Water, snow,
rock and cloud never take it — the corpus does not use it there and the result looks like an
accident.

The other failure is scale. A scribble mass smaller than roughly a fingernail on the page
collapses into a blot. At that size, use a solid tapered dark instead.

## Prompt language

Model-agnostic:

- "continuous looping scribble, pen never lifted, ink on white"
- "foliage mass built from loose open loops, uneven loop sizes"
- "lighter and more open at the top of the mass, denser and darker at the bottom"
- "the edge of the mass is broken with small swirls and short ticks, no straight boundary"

That last fragment is the important one and it belongs in almost every scribble prompt. It is
the fix for the technique's signature failure, described below.

For the leaf-stroke variant, ask for "small open loops at varied sizes and angles, scattered,
not touching" rather than "scribble".

### `gpt-image-2`

`gpt-image-2` renders scribble reasonably but does two things wrong by default. It closes the
mass into a clean silhouette, and it fills the loops with grey.

- "pure black ink lines on white paper, white shows through between the loops, no grey fill"
- "irregular ragged outline; the mass has no smooth edge anywhere"
- "white gaps left between separate foliage masses"

If the model returns one dense blob, ask for fewer, larger loops before you ask for anything
else — density is the parameter it overshoots.

## Failure modes

| Symptom | Correcting phrase |
| --- | --- |
| Hard defined edge around the mass — the signature failure | "break the boundary with small swirls and tick marks along the edge" |
| Uniform tone across the whole mass | "light at the top, dark at the bottom of each mass" |
| One continuous field instead of separate masses | "distinct foliage masses with white gaps between them" |
| Loops so tight the mass fills solid black | "open loops, white paper visible inside the mass" |
| Regular repeating loop pattern | "loop size and spacing vary throughout; no repeating pattern" |

The first row is the one the corpus names directly. Scribble naturally terminates in a clean
outline, that outline reads as stiff, and stiffness kills the foliage effect. Swirls and ticks
along the boundary are the stated fix, so put them in the first prompt rather than the repair
prompt.

## Contact sheet

[scribble-strokes.png](scribble-strokes.png)
