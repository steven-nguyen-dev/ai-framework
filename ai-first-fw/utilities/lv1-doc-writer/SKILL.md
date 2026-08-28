---
name: lv1-doc-writer
description: House style and structure standards for authoring, rewriting, or reviewing technical documents and HLDs.
disable-model-invocation: true
version: 0.0.2
---

# Technical document authoring

House style for any technical document, plus the HLD-specific layer in §B. Diagram and colour
rules are **not** here — they are in `lv1-diagram-maker`, which governs every diagram in every
document.

Derived from the `integration-design.md` rewrite of 2026-08-09.

| § | Read when |
|---|---|
| A1 Voice | writing any sentence |
| A2 Self-containment | deciding whether to link out |
| A3 Provenance | stating a fact you did not derive yourself |
| A4 Ship checklist | before handing it over |
| A5 How the work is run | starting the job, or being told the result is wrong |
| B1–B5 | the document is a high-level design |

---

## A. Any technical document

### A1. Voice

- **No self-explanation.** No "what this document is", no "why this was written", no methodology, no reading-flow justification.
- **Scope is one sentence**, at the top, and it states scope, not a hook.
- **Bullets and tables carry the content.** Write a paragraph only when it makes a single point in three sentences or fewer.
- **One fact per bullet**, lead with the load-bearing clause in bold.
- **Measurable over adjectival**: "82 partner modules" not "many modules".

### A2. Self-containment

Decide once, per document set, and apply it to every document in the set.

- **Self-contained** — no links, no "see X", no cross-document section references. Each document stands alone for a reader who has only that file.
- The cost is real. Two documents at adjacent levels will state the same summary twice. Accept it deliberately, keep the duplicate to a summary line in one and the evidence in the other, or drop the self-containment requirement.
- Provenance in the source section is not a cross-reference. Removing it to satisfy self-containment makes the document claim first-hand verification it does not have.

### A3. Provenance

- **Every fact is traceable** to one of four: derived from source, quoted from a named document, stated by a human, or marked missing.
- **Quote wire-format facts, never infer them** — endpoints, payload shapes, field names, status values, auth.
- **Declare sections compiled from other documents as second-hand**, with the dates of the material and its own sample-size limits.
- **The source section records the boundary of what was checked**, including an explicit not-verified clause. It is not a bibliography.
- **Delete a pointer to a file that no longer exists**, do not carry it forward. Keep the finding IDs, drop the dead link, and say the evidence is no longer reachable.

### A4. Ship checklist

Every row must pass. Diagram rows are in `lv1-diagram-maker` and must pass too.

| # | Check |
|---|---|
| 1 | No sentence explains the document to itself |
| 2 | Contents rows match real headings, in document order |
| 3 | Every link resolves — or, under self-containment, there are none |
| 4 | No one-row table; no bullet list whose items repeat the same fields |
| 5 | Source states what was read, when, what is second-hand, and what was not verified |
| 6 | Checked who cites `<doc> §N` before renumbering |
| 7 | Drafted in `local-library/.manuscript/`, promoted only after review |

### A5. How the work is run

- **Interview before writing.** Ask only about the decisions that change the output, and state a default for anything left unanswered.
- **Deliver drafts for review**, not finished files in place.
- **When challenged, re-check the disputed thing itself** before defending or conceding. A passing validator defended the first colour scheme in this spec's history. It was still wrong.

---

## B. High-level design documents only

### B1. Reading order

Breadth before depth, three levels, in this order:

1. **Whole-system components** — the boxes, their roles, their instances.
2. **Per-area design** — one section per area, each a complete small HLD of that area.
3. **Mechanisms** — the shared machinery every area rides on.

Rules:

- **Each level is resolvable without the next.** A reader who stops after level 1 has a correct, if coarse, model.
- **Level 2 sections are parallel.** Same sub-structure, same order, same vocabulary for every area, so areas can be compared by reading across.
- **A section is not an area unless it has its own diagram.** A table of module names is an inventory, not a design.
- Source, verification and scope notes are the last section, never the first.

### B2. Abstraction contract

State the level once, in the components section, and hold it everywhere:

- **Name the white box, and declare its contents black boxes.** Example from the JPluger doc: the integration layer is the white box, holding exactly three components (connector, bus, integration service), and everything inside those three is closed.
- **Infrastructure is one component.** The bus is a box; publishers and subscribers belong to the components that own them. No message lifecycle, no offsets, no serialization at this level.
- **Name a class, topic or config key only when the component cannot be identified without it.**
- **The completion test.** A reader finishes able to draw the component diagram and place a new integration in it. Not able to debug a message.
- Do not delete detail that fails this test. Move it to a companion document at the level below.

### B3. Flow taxonomy

- **Enumerate the flows once, as a small closed set**, and describe every area in those same terms. Three worked for JPluger: OUT, IN-pull, IN-push.
- **The taxonomy is fixed.** Every area section instantiates the same set; where an area lacks one, say so rather than omit it.
- **Name the flows in the reader's language, not the code's**, when the code's own labels are inconsistent, but record the collision. The JPluger topics label the OMS-to-integration direction "inbound" and the reverse "outbound", the opposite of the document's own OUT.
- **State exceptions with the flow**, do not bury them in an area. Authentication bypassing the bus is a property of OUT.

### B4. Design and flaws

- **Every numbered section splits `N.1 Design` and `N.2 Flaws`.** Consistent across the whole document, including sections where the flaws list is short.
- **Never mix the two in one block.** No warning markers inside the design prose, and none inside diagrams.
- **A diagram shows what the code does; the flaws sub-section says why that is wrong.** "Acknowledges, then processes" is design. "Therefore delivery is at-most-once" is a flaw.
- **A flaw lives with the thing it is a flaw of**, not in a global appendix. A cross-cutting index duplicates and drifts.
- **Give each flaw a stable ID** where evidence lives elsewhere, and state what a reader would wrongly assume if they did not know it.
- **Flaws are point-in-time.** Say so once, and delete an entry when it is fixed.

### B5. HLD ship checklist

In addition to A4:

| # | Check |
|---|---|
| 1 | Sections run whole-system → per-area → mechanisms → source |
| 2 | Every numbered section has `N.1 Design` and `N.2 Flaws`, and nothing mixes the two |
| 3 | Every area section has its own diagram, not just a table |
| 4 | Every area instantiates the same flow taxonomy, with gaps stated explicitly |

---

## Known gaps

The source spec deferred these to a house-style document that was never written. This document does
not cover them. Do not guess: ask, or decide and record the decision.

- heading rules
- the `## At a glance` opening anchor — what it must contain
- shape → format (which kind of content becomes a table, a list, a diagram)
- the rewrite checklist, as distinct from the ship checklist above
