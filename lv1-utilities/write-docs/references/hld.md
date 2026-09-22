# The high-level design layer

Applies on top of `house-style.md` where the note is a high-level design.

## §1 Reading order

Breadth before depth, three levels, in this order:

1. **Whole-system components** — the boxes, their roles, their instances.
2. **Per-area design** — one section per area, each a complete small design of that area.
3. **Mechanisms** — the shared machinery every area rides on.

- **Each level resolves without the next.** A reader who stops after level 1 holds a correct, if
  coarse, model.
- **Level 2 sections are parallel** — same sub-structure, same order, same vocabulary for every
  area, so areas compare by reading across.
- **A section is an area only where it carries its own diagram.** A table of module names is an
  inventory.
- `## Source` and `## Open questions` stay last.

## §2 Abstraction contract

Stated once, in the components section, and held everywhere.

- **Name the white box, and declare its contents black boxes.** In the JPluger design the
  integration layer is the white box, holding exactly three components — connector, bus, integration
  service — and everything inside those three is closed.
- **Infrastructure is one component.** The bus is a box; publishers and subscribers belong to the
  components that own them. No message lifecycle, no offsets, no serialization at this level.
- **Name a class, topic or config key only where the component cannot be identified without it.**
- **The completion test.** A reader finishes able to draw the component diagram and place a new
  integration in it — not able to debug a message.
- Detail that fails the test moves to a companion note at the level below.

## §3 Flow taxonomy

- **Enumerate the flows once, as a small closed set**, and describe every area in those same terms.
  Three carried the JPluger design: OUT, IN-pull, IN-push.
- **The taxonomy is fixed.** Every area section instantiates the same set; where an area lacks one,
  the note says so rather than omitting it.
- **Name the flows in the reader's language, not the code's**, where the code's own labels are
  inconsistent, and record the collision. The JPluger topics label the OMS-to-integration direction
  "inbound" and the reverse "outbound", the opposite of that design's own OUT.
- **State an exception with the flow it belongs to.** Authentication bypassing the bus is a property
  of OUT.

## §4 Design and flaws

- **Every numbered section splits `N.1 Design` and `N.2 Flaws`**, across the whole note, including
  sections whose flaws list is short.
- **Each block holds one of the two.** Design prose and diagrams carry no warning markers.
- **A diagram shows what the code does; the flaws sub-section says why that is wrong.**
  "Acknowledges, then processes" is design. "Therefore delivery is at-most-once" is a flaw.
- **A flaw lives with the thing it is a flaw of.** A cross-cutting index duplicates and drifts.
- **Give each flaw a stable ID** where its evidence lives elsewhere, and state what a reader would
  wrongly assume without it.
- **Flaws are point-in-time.** State that once, and delete an entry when it is fixed.

## §5 HLD ship checklist

In addition to `house-style.md` §6.

| # | Check |
|---|---|
| 1 | Sections run whole-system → per-area → mechanisms → source → open questions |
| 2 | Every numbered section carries `N.1 Design` and `N.2 Flaws`, and each block holds one of them |
| 3 | Every area section carries its own diagram |
| 4 | Every area instantiates the same flow taxonomy, with gaps stated explicitly |
