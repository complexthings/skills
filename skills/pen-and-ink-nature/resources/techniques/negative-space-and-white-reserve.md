# Negative space and white reserve

There is no mark. That is the technique.

Pen and ink has no white ink. Every bright thing in these drawings — snow, cloud, a water
highlight, a waterfall, backlit foliage, the round side of a twig — is untouched paper that was
deliberately left alone and deliberately bounded. Reserve is planned before the first mark, not
recovered after.

Half the source drawings are organised around reserve even though it is named once. Put a
reserve clause — what stays untouched, and what darkens around it — in every prompt.

## The mark

Shaped, bounded paper. Two properties make white read as a subject rather than as unfinished
work:

- **A boundary.** The white needs something to end against — a darkened edge, a toned field, a
  ragged run of marks. Unbounded white reads as blank.
- **A surround dark enough to define it.** A white shape reads brighter as the field around it
  gets darker. This is the only brightness control the medium has.

Two related moves the corpus uses constantly:

- **White reserve** — leaving a shape untouched because it is bright: snow, a cloud body, a
  waterfall, the centre streak of a twig.
- **Separation margin** — leaving a thin white gap around an element so it stays in front of
  what is behind it: twigs against a bush, flowers against stones, one wave behind another,
  branches crossing foliage. With no colour available, the white margin is the only way to state
  overlap.

## Tonal control

Inverted. You control white by choosing what **not** to mark, and by the density of everything
around it.

Two corpus warnings pull in opposite directions, and both are real:

- **Too little white** and the elements merge into a dark mess. The corpus repeatedly warns
  against filling everything in.
- **Too much white** and the image loses continuity and falls apart into disconnected pieces.

Between them sits the working rule: darken *around* a bright subject rather than toning the
subject itself. To make a waterfall brighter, darken the background behind it. To make a
mountain heavier, add a background tone that reduces its white. To stop a white sky competing
with white snow, tone the sky with dots and ticks — that is the corpus's stated reason for the
sky marks on a snow-peak drawing, and it is a reserve decision, not a sky decision.

## Where it works

- **Snow peaks.** The exemplar. Almost the entire paper is left bare; snow *is* the paper. The
  drawing is ragged darkening along the ridges, sparse wavy contour lines inside, and a toned
  sky. Contrast a rock mountain, whose interior is worked with cuts and planes — a snow peak's
  interior is reserved and the drawing lives on its edges.
- **Clouds.** Either outlined and left white against a toned sky, or given a wavy white streak
  running between cloud bodies to read as sunrise or sunset glow.
- **Water.** A bright stretch of water read against a darkened wooded backdrop. A waterfall left
  white with the background deliberately darkened behind it.
- **Foliage.** White gaps between drawn leaf masses read as background foliage, and that
  contrast is what produces depth in a crown.
- **Thin branches and twigs.** The central white streak that makes a two-tone branch round.
- **Flowers against a dark background** — draw the background around them and leave the blooms
  untouched.
- **Paths.** Parallel lines run in from both edges with white left down the middle to lead the
  eye.

## Where it fails

Nowhere as a principle, but two situations need care.

A subject with no darker surround has nothing to read against. White snow against a white sky is
invisible until the sky is toned. Plan the surround at the same time as the reserve.

Large reserved areas across a whole composition break it into disconnected islands. Layered
scenes need some continuity of tone between the layers or the eye cannot travel them.

## Prompt language

Model-agnostic. State the white as a positive instruction — say what is left untouched:

- "the snow is left as bare white paper, untouched, no texture inside it"
- "the paper is left white; the drawing lives on the ridge edges"
- "darken the background behind the waterfall so the falling water stays bright white"
- "leave a thin white gap where the twig crosses the bush behind it"
- "a streak of untouched white down the centre of each branch"
- "white gaps left between the foliage masses"

Two fragments do most of the work. **"left as bare white paper"** is what stops a model
texturing a bright subject. **"darken the background behind it"** is how you ask for brightness
in a medium that cannot add any.

Always say white "paper", not "white", so the model does not read it as a white fill layer.

### `gpt-image-2`

`gpt-image-2` fills bright areas with light grey texture by default. That single behaviour is
the main thing to prompt against, and it is worth two lines every time:

- "pure black ink on white paper; no grey, no wash, no gradient, no colour"
- "the snow / cloud / waterfall is completely untouched paper — zero marks inside it"

It also closes separation gaps, drawing overlapping elements as if they touch. Ask for the gap
explicitly: "a visible white margin separates the front element from what is behind it".

If the result is close but muddy, ask it to remove marks rather than add them: "erase the
texture inside the white areas and leave them blank".

## Failure modes

| Symptom | Correcting phrase |
| --- | --- |
| A reserved subject rendered as light grey texture — the most common model failure | "completely untouched white paper, no marks inside it" |
| White with no boundary; the drawing reads as unfinished | "the white shape is bounded by darkened, ragged edges" |
| So much white the image fragments into pieces | "add background tone between the layers to hold the scene together" |
| Everything filled in; elements merge into a dark mass | "leave white gaps between overlapping elements" |
| Overlapping elements touching, front and back unreadable | "a thin white margin where one element crosses another" |
| White sky competing with white snow | "tone the sky with dots and ticks so the snow stays the brightest thing" |

The first row is worth checking on every generation. A model that renders snow as pale grey has
produced a drawing that is technically close and stylistically wrong, and no amount of added
detail fixes it — the correction is subtractive.

## Contact sheet

[negative-space-and-white-reserve.png](negative-space-and-white-reserve.png)
