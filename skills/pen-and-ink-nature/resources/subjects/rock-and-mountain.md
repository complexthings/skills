# Rock and mountain

Stones, mountains and mountain ranges, snow peaks.

## What makes rock read as rock

**A stone is a box form before it is a texture.** Solidity comes first: distinct planes, each
toned separately, with one side overall darker than the other under an assumed light. Texture is
what makes the box stop being a box — but texture applied to an undefined form gives a grey blob.

The same logic scales up. A mountain is a set of planes or a field of surface cuts; a snow peak is
the inversion of both, where the interior is reserved white and the drawing lives on its edges.

Two rules cut across all three:

- **Vertical planes are darker than horizontal ones**, because a horizontal plane faces an
  overhead sun. A horizontal plane can be left white.
- Every edge is irregular. A clean straight edge on rock is the fastest way to lose the subject.

## Techniques this subject uses

| Part | Technique | Role here |
|---|---|---|
| Plane tone | [hatching](../techniques/hatching.md) | Parallel lines at each plane's own angle, shortened at the far end to fade the plane out |
| Third tone | [crosshatching](../techniques/crosshatching.md) | A second pass at an angle takes a face from two tones to three |
| Fine surface | [stippling](../techniques/stippling.md) | Dots and ticks; the finest tonal control available on stone, and the primary texture on mountains |
| Cuts and crevices | [directional and tapered strokes](../techniques/directional-and-tapered-strokes.md) | Tapered marks pointed at both ends, from the edges inward and in the body |
| Snow peak surface | [contour lines](../techniques/contour-lines.md) | Slightly wavy interior lines that tone and describe the form at once |
| Snow | [negative space and white reserve](../techniques/negative-space-and-white-reserve.md) | Snow is the untouched paper; nothing is drawn to make it |

Mechanics live in those files. What follows is the build order.

## Structural approach

### Stones

1. Draw a box in three-quarter view: left face, right face, top.
2. Make every edge irregular. The box is scaffolding, not an outline to keep.
3. Pick a light direction and make one side overall darker than the other.
4. Tone each face separately. Parallel lines or dots and ticks both work and are interchangeable;
   fine dots give the most control.
5. Add a second set of parallel lines at an angle where a face needs a third tone.
6. Finish with the marks that make it stone rather than a box: irregularly darkened edges, tapered
   cuts running from the edges inward and across the body, and scattered dots, ticks and small
   crevices.

A rounded stone is the same construction with the plane changes softened — grade the tone
gradually and the distinct faces disappear. For a group, draw the front stone first, omit the
plane lines it hides, and shrink stones with distance. Stones belong in the foreground and pair
naturally with water and wooden posts.

### Mountains

Two approaches. Pick one per mountain; mixing them muddies the form.

**Plane-based.** Outline the mountain with distinct angle changes. Draw lines inward from those
transition points to define planes. Tone each plane separately at its own angle, verticals darker
than horizontals. A plane inside the body is a shape line plus parallel lines at the plane's
angle, the lines shortening toward the far end so the plane fades out instead of ending on a hard
edge.

**Surface-imperfection-based.** Cover the body with tapered cuts, pointed at both ends, varied in
size and orientation. Finish with tapered darks at the edges and small cuts to remove excess
white.

The angle of a cut changes what it reads as, with no change to the mark: angled reads as a slice,
vertical reads as a deep cut, horizontal reads as a path or ledge to the summit.

A background tone of parallel lines subdues the mountain's white and gives it weight. Reducing
white on purpose is the move that makes a mountain feel heavy.

For a range: darken the base of a rear mountain more than its top, which models the light and
separates it from the mountain in front at the same time. Distant mountains get fewer planes and
less detail. For blocky forms, draw the front block first and start the rear block's top from the
front block's edge; leaving a block's top line open lets it merge into the surrounding planes and
reads better than a closed box.

### Snow peaks

The clearest demonstration of white reserve in the whole style. Almost the entire paper stays
untouched. Snow **is** the paper.

1. Draw overlapping peak outlines, rear peaks smaller.
2. Add extra front peaks and a few additional planes for dimension.
3. **Darken the edges irregularly.** This is the move that makes the shape read as snow; do it
   before anything goes inside.
4. Build edge tone with more marks on those edge lines.
5. Add slightly wavy lines inside, sparse. They tone the surface and describe the peak's contour
   in one pass.
6. Tone the sky with dots and ticks — not for the sky's sake, but so white sky stops competing
   with white snow.

The count of interior lines is the mood dial. More lines takes away the soft fluffy quality and
makes the drawing heavier.

The contrast with a bare rock mountain is worth holding: a rock mountain's interior is **worked**
— cuts, planes, background tone. A snow peak's interior is **reserved**, and the drawing lives on
its edges.

## Prompt fragment

```
A group of snow peaks in pen and ink, pure black ink on white paper, no grey wash and no
colour. Overlapping peak outlines with the rear peaks smaller. The snow is untouched white
paper — nothing is drawn to represent it. Ridge edges are darkened irregularly with short
ragged marks, heavier where two peaks overlap. Sparse slightly wavy contour lines inside each
peak both tone the surface and describe its form; keep them few, so most of the interior stays
bare. The sky behind is toned with dots and ticks, denser near the horizon, so that the white
of the sky does not compete with the white of the snow. Hand-drawn irregularity throughout, no
ruled lines, no smooth grey shading.
```

For a foreground stone instead, swap the whole body of the fragment: *a stone in three-quarter
view with a left face, a right face and a top, every edge irregular, the left face toned with
parallel lines and the shadowed right face carrying a second pass at an angle for a third tone,
tapered cuts running from the edges inward, and scattered dots, ticks and small crevices across
the body.*

## Failure modes

| Symptom | Correction |
|---|---|
| Stone reads as a grey blob | Define and tone the planes before adding any texture |
| Stone reads as a drawn box | Add irregular edge darkening, tapered cuts and scattered crevices |
| Mountain planes end on hard edges | Shorten the parallel lines toward the far end so the plane fades |
| Mountain looks weightless | Add a background tone of parallel lines to subdue its white |
| Snow rendered as light grey texture | Snow is untouched paper; state that the drawing is edges only |
| Snow peak lost against the sky | Tone the sky with dots and ticks |
| Rear peaks compete with front ones | Fewer marks, smaller size, less detail with distance |
