---
name: doodl-craft
description: Draw pictures with the doodl_* tools — drafts edited stroke by stroke with a preview after each edit, published as doodl drawings in your own repo. Covers the round pen, tapers, paint order and the look-then-fix loop. Use whenever drawing, remixing or publishing a doodl.
---

# drawing with doodl

doodl drawings are pictures made of pen strokes, saved as
`tech.waow.doodl.drawing` records in your own repo and viewable at
`https://doodl.waow.tech/l/<did>/<rkey>`. Use lexidraw for diagrams, boxes and
arrows; use doodl for a drawing of something.

The `doodl_*` tools stay out of your tool list until you ask for them. Call
`search_tools(queries=["doodl"])` to reveal them; they are callable from your
next step.

## the loop

1. `doodl_new_draft` with a title and a first handful of strokes. It returns
   the draft's uri, the stroke names, and a preview image.
2. Look at the preview. Name what is wrong in plain words: "the head floats
   off the neck", "the tail tip is a blunt block".
3. `doodl_edit_draft` fixes it by stroke name: `update` changes a stroke,
   `add` puts new ones on top (or under one, with `before`), `remove` drops
   them. Several changes go in one call. Each call returns a new preview.
4. Repeat until it reads clearly. Three to six edits is normal.
5. `doodl_publish_draft` saves the drawing and returns its share url.

Drafts are public records too, so delete one you abandon with
`doodl_delete_draft`. `doodl_remix_drawing` opens someone's drawing as your
own draft; publishing it credits theirs.

## the pen

The canvas is 1024 by 1024, origin top left. Every stroke is a round stamp
dragged along a line, so every stroke is a rounded tube and every end is
round. There are no fills: paint an area with one wide stroke or several
overlapping ones. Widths top out at 400.

- A body is one wide stroke along its spine. `taper: [[0, 230], [0.4, 200],
  [1, 125]]` narrows it from hip to neck; `t` runs from 0 at the stroke's
  start to 1 at its end.
- A point (a tail tip, a beak) is a short stroke tapering to about 18.
- Curves are SVG path data in `d`; a move inside `d` lifts the pen.
- An eye or a nose is one point with a size: `points: [[440, 286]]`.

## paint order

Later strokes cover earlier ones. Paint back to front: background, shadow,
far limbs, body, markings over the body, then small dark details last. To
slip a forgotten stroke underneath, add it with `before` set to the stroke it
should sit under.

## colour

doodl's palette: `#212529` ink, `#ffffff`, `#e03131` red, `#f08c00` orange,
`#f2c200` yellow, `#2f9e44` green, `#1c7ed6` blue, `#7048e8` violet,
`#e64980` pink. Any hex colour works; a slightly darker shade of the body
colour reads as a marking.
