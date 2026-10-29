# Directional and tapered strokes

Two rules the corpus treats as one family, and between them they account for more marks in
these drawings than every other technique combined.

- **Directional**: texture runs along the form's own direction. Bark strokes run along the
  trunk. Water lines run along the flow. Grass rises from its root.
- **Tapered**: the stroke starts and ends in a point, heaviest in the middle. The heaviest
  version is the **tapered dark**, and it is the main source of true black in this style.

## The mark

A stroke pointed at both ends. The point is the whole character of the mark — a blunt-ended
dash reads as a mechanical tick, not as ink laid down by a moving pen.

Direction is not decoration. The same tapered stroke means three different things depending on
its angle across a mountain body: angled reads as a slice, vertical reads as a deep cut,
horizontal reads as a path or ledge. Set the angle deliberately.

### Sub-marks

Each of these is a distinct visual, and naming the right one in a prompt beats describing a
generic stroke:

| Sub-mark | What it looks like | Used for |
| --- | --- | --- |
| Wandering bark line | Slightly meandering, along the trunk's length, never straight | Bark grooves |
| Tapered crevice | A pointed dark gouge | Trunks, posts, stones, mountains |
| Grass stroke | Short, slightly curved, sitting on a root | Grass, ground cover |
| Pine needle stroke | Short, curved, angled outward and down, mirrored either side of centre | Pine foliage |
| Surface cut | Tapered, pointed at both ends, varied size | Mountain and rock bodies |
| Water stroke | A horizontal wavy line | Still and moving water |
| Ripple stroke | A curve growing larger as it travels from its source | Water flowing toward the viewer |

The wander in the bark line is not optional. The corpus is emphatic that a straight line will
not read as bark.

## Tonal control

**Weight and count.** A cluster of tapered darks is the darkest tone available short of solid
fill, and the corpus reaches for it rather than for layered crosshatch when it needs near-black.

**Length is a distance cue.** The same mark drawn shorter reads as farther away. Uniform stroke
length across a receding field flattens the depth completely, which is why the corpus shrinks
grass, needles and cuts with distance.

This is also the technique that carries the tone-count rule for narrow forms. A thin branch or
twig gets two tones: darken the top edge and the bottom edge, the bottom more, and leave a
streak of untouched paper down the centre. That white streak is the roundness — see
[`negative-space-and-white-reserve.md`](negative-space-and-white-reserve.md). Smaller still —
end twigs, far branches, reflected twig tips — and it drops to one tone: a solid tapered dark.

## Where it works

Everywhere. Bark, branches, wooden posts, grass, pine needles, mountain cuts, stone edge
roughness, falling water, waves, ripples and twig silhouettes all sit in this family. If a
natural subject has a direction, this is the technique that states it.

Two places it does the decisive work:

- **Trunks.** The wandering bark line plus tapered crevices is what makes a toned cylinder read
  as a tree. More and heavier crevices read as an older, rougher tree.
- **Grounding.** A few grass strokes at the base of a trunk or post stop it looking pasted onto
  the paper.

## Where it fails

Subjects with no coherent direction. A foliage mass, a cloud, a mist field — putting
directional strokes there imposes a grain the subject does not have.
[`scribble-strokes.md`](scribble-strokes.md) and dots and ticks cover those.

Large even areas are the other miss. Filling a whole sky or a stone face with tapered strokes
is slow and reads as texture rather than as tone; parallel lines do that job.

## Prompt language

Model-agnostic. Always name the direction relative to the form:

- "short tapered strokes, pointed at both ends, ink pen, hand-drawn"
- "bark texture running along the length of the trunk, wandering lines, never straight"
- "grass strokes rising from a root, shorter toward the back of the scene"
- "pine needles angled outward and downward, leaning right on the right side of the tree and
  left on the left"
- "tapered dark crevices in the trunk body, pointed at both ends"

The single most useful fragment is **"pointed at both ends"**. Without it, models produce
uniform-width dashes and the whole style collapses.

For depth, state the length gradient outright: "strokes shorten with distance".

### `gpt-image-2`

`gpt-image-2` produces blunt, uniform strokes by default and tends toward a regular grain.

- "pure black ink on white, no grey, no shading"
- "each stroke tapers to a point at both ends, thick in the middle"
- "stroke lengths and angles vary; the spacing is irregular"

For a trunk, ask for the tone bands explicitly — "three tonal bands across the trunk: a dark
third, a middle third, and a near-white third" — because the model otherwise tones the trunk
evenly and the roundness disappears.

## Failure modes

| Symptom | Correcting phrase |
| --- | --- |
| Blunt-ended dashes instead of tapers | "every stroke comes to a point at both ends" |
| Uniform stroke length across a receding field | "strokes get shorter and lighter with distance" |
| Strokes running across the form | "texture runs along the length of the trunk / along the flow of the water" |
| A branch joint filled solid black | "darken the joint slightly, never solid black" |
| A perfectly straight bark line | "the line wanders; no straight edges anywhere" |
| Even grain, mechanical repetition | "stroke direction and length vary; no repeating pattern" |

The joint row matters more than it looks. Attachment points between branch and trunk are where
models reach for solid black, and the corpus specifically forbids it — a filled joint reads as a
hole rather than as a junction.

## Contact sheet

[directional-and-tapered-strokes.png](directional-and-tapered-strokes.png)
