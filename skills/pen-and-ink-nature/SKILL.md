---
name: pen-and-ink-nature
description: Write image-generation prompts (for gpt-image-2, Nano Banana / Gemini Image or a similar model) for pen-and-ink nature and landscape illustration — the hand-drawn line-art look built from parallel lines, dots and ticks, tapered darks and reserved white paper. Use whenever a request asks for a natural or landscape image in pen and ink, ink drawing, line art, etched, engraved, woodcut or black-and-white hatched style, including a request that only says "black ink line drawing" — trees and foliage, water, rock and mountain, sky and cloud, ground and flowers, fences, or a full seasonal landscape. When such a scene features an animal or a person, use it for the landscape around them only. Do not use it for photographic, painted, coloured or grey-wash images, or for buildings, products or other non-landscape subjects.
---

# Pen-and-ink nature illustration

This skill produces **a prompt for an image model**, not code and not a drawing. Its output is
text: a prompt naming the marks, the tonal steps, the reserved white and the irregularity that
make an image read as a hand-drawn pen-and-ink nature study.

Return the finished prompt as plain text, ready to paste, one prompt per requested image. When
the request names no image model, write for `gpt-image-2` (see Model notes). Add a short note
after the prompt only when part of the request falls outside the scope below.

## Scope

Covered: landscape and botanical subjects only — trees, bark, branches, foliage, water in all
its states, stone, mountains, snow peaks, sky and cloud, grass, ground, paths, flowers,
seasonal scenes, wooden posts and fences.

Not covered: **fauna and human figures.** The source corpus contains essentially none, and
guidance invented without a source would be worse than a stated gap. For an animal or a figure
in this style, say the skill does not cover it and offer the landscape around it.

Also outside the style: colour, grey wash, airbrush, pencil, photographic rendering, line
weight varied by pressure, and any nib or paper vocabulary. The entire control surface here is
**how many marks, where, and in what direction.**

## Vocabulary

Use these words in prompts. They are the source drawings' own terms, and they steer image
models better than the generic art-glossary equivalents.

| Say this | Not this | Why |
|---|---|---|
| **tone** | value | "Value" never appears in the source; tone is the whole system |
| **parallel lines** | hatching, shading | "Shading" pulls models toward smooth grey |
| **dots and ticks** | stippling | A tick is a very short directional dash; the mixture is the mark |
| **tapered dark** | thick stroke | Pointed at both ends, thick in the middle — the main source of true black |
| **contour lines** | cross-contour | Curved lines that report the surface under them |
| **reserved white** | highlight | Untouched paper, deliberately shaped and bounded |
| **irregular** | organic, natural | The source states irregularity as an instruction, and models default against it |

Four principles sit under all of it:

1. **Suggestion over description.** A few well-chosen marks that imply a texture beat many that
   transcribe it. Cover part of the ground, not all of it. Leave edges unfinished.
2. **Deliberate irregularity.** Even spacing, straight edges and repeating patterns are
   failures. This is exactly what image models get wrong, so name it in every prompt.
3. **White is the separator.** With no white ink, the only way to hold one element in front of
   another is a thin margin of bare paper around it.
4. **Distance is size and density, not blur.** Farther elements are smaller, carry fewer marks
   and drop tonal steps.

## Tonal building — the cross-cutting concern

This sits above every individual technique. Get it into the prompt before choosing a mark.

**Tone is built by count and proximity, never by a darker pen.** Every darkening instruction is
more strokes, closer strokes, or a second set of parallel lines at an angle. There is no second
pen and no pressure variation.

**The tone-count rule.** Any rounded form gets a fixed number of tonal steps, chosen by how much
room it occupies on the paper:

- **Three tones** — dark, middle, light — when the form is wide enough to hold three bands. A
  near tree trunk is roughly a dark third, a middle third and a near-bare third. A foliage mass
  grades light at the top to dark at the bottom, because the light is overhead.
- **Two tones** — dark and light only — when the form is too narrow for three. Thin branches,
  twigs, saplings, distant trunks: darken the top edge and the bottom edge, the bottom more, and
  leave a streak of untouched paper down the centre. That white streak *is* the roundness.
- **One tone** — a solid tapered dark — for anything smaller: end twigs, far branches, reflected
  twig tips.

The steps are relative. A heavier overall setting reads as older, rougher, heavier weather; a
lighter setting reads as sunlit. What must hold is the ordering and the contrast between
adjacent bands.

In a prompt, **name the number of tonal steps and where the lightest one sits** rather than
asking for "shading".

## Prompt template

Fill the slots, drop any that do not apply, and keep the clauses in this order. Density and
irregularity clauses belong in the same sentence as the mark they govern, not stranded at the
end.

```
[SUBJECT + COMPOSITION] in pen and ink, pure black ink on white paper, no grey wash, no
colour, no photographic rendering.

[MARKS] Each element names its own mark: parallel lines / dots and ticks / tapered darks /
continuous looping scribble / soft broken contour lines — with the angle or direction it
runs in.

[TONE] The number of tonal steps across each form and where the lightest sits: "three
distinct densities across the trunk — dark third, middle third, near-white third".

[WHITE] What is left as bare paper and what surrounds it: "the snow is untouched white
paper; only the ridge edges are darkened".

[DEPTH] What shrinks and thins with distance: "the far trees are smaller, carry fewer marks
and drop to solid tapered darks".

[IRREGULARITY] Always present: "every mark hand-drawn, uneven in length and spacing, edges
ragged rather than clean, no ruled or mechanical repetition".
```

The subject files each carry a worked prompt fragment. Start from the one that matches and edit
it — that is faster and more accurate than building from this template cold.

## Model notes

**`gpt-image-2` — primary.** Three defaults to counter in every prompt:

1. It drifts to grey. Repeat "pure black ink on white paper" in the same sentence as the mark,
   not only at the end.
2. It rules its lines. Name irregularity as a positive property — "each line wavering slightly,
   unequal in length, drawn by hand".
3. It fills bright areas with light grey texture. When something should be reserved white, say
   it is untouched paper and say what is left blank.

Per-technique corrections live in each technique file under its `gpt-image-2` heading.

**Nano Banana / Gemini Image — secondary.** It holds line quality and hand irregularity better
than `gpt-image-2` but composes more loosely, so state the composition and the layering order
explicitly ("foreground bush, taller trees behind it, pines behind those, then mountain and
sky"). It also tends to add colour or a paper texture unasked; negate both by name. Prompts
written from the template transfer without rewriting — tighten the composition clause, keep
everything else.

## Routing

Read only what the request reaches. One technique file plus one subject file answers most
requests.

### Techniques — how a mark is made

| File | Reach for it when |
|---|---|
| [hatching](resources/techniques/hatching.md) | Any area of even grey: planes, ground, sky behind clouds, still water, bark along a trunk |
| [crosshatching](resources/techniques/crosshatching.md) | Pushing one plane of a stone or post a step darker; weathered timber. Narrow use |
| [stippling](resources/techniques/stippling.md) | Dots and ticks: clouds, mountain surfaces, stone, petals, sand, mist, spring growth |
| [contour lines](resources/techniques/contour-lines.md) | Declaring a surface's shape: inclined ground, petals, snow-peak surfaces, a river's bend |
| [scribble strokes](resources/techniques/scribble-strokes.md) | Mid-distance vegetation where the individual leaf does not matter |
| [directional and tapered strokes](resources/techniques/directional-and-tapered-strokes.md) | Bark, branches, grass, pine needles, mountain cuts, ripples, waves — and all true black |
| [negative space and white reserve](resources/techniques/negative-space-and-white-reserve.md) | Snow, waterfalls, highlights, cloud whites, separation margins between overlapping elements |

Each technique file ends with a contact sheet: the raw mark at three densities beside the same
mark on a real subject.

### Subjects — what makes a thing read as itself

| File | Covers |
|---|---|
| [trees](resources/subjects/trees.md) | Trunks, bark, branches, deciduous foliage, pine foliage |
| [water](resources/subjects/water.md) | Still water, moving water, flow toward the viewer, waterfalls, rivers, streams, shoreline, waves |
| [rock and mountain](resources/subjects/rock-and-mountain.md) | Stones, mountains, mountain ranges, snow peaks |
| [sky and clouds](resources/subjects/sky-and-clouds.md) | Cloud outlines, filled skies, formations, sunrise glow, night sky |
| [ground and flowers](resources/subjects/ground-and-flowers.md) | Grass, ground plane, paths, wild flowers, flowers close up |
| [composite scenes](resources/subjects/composite-scenes.md) | Full landscapes, seasonal scenes, layering, tonal casting, wooden posts and fences |

## Scale

These are small drawings — roughly 5×4 to 7×5 inches. That is why the marks are coarse and the
coverage is sparse. A prompt that asks for photographic density of detail is asking for a
different medium.

## Attribution

Style studied from `pendrawings.me` by Rahul Jain. See [ATTRIBUTION.md](ATTRIBUTION.md).
