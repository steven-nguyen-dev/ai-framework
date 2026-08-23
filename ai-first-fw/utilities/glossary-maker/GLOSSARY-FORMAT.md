`GLOSSARY.md`'s opening and the rules for an entry. The opening is copied out; the rules stay here.
Numbering and citation live in [AUDIT-BRIEF.md](./AUDIT-BRIEF.md).

## The opening — copy verbatim, filling `<the thing>`

````markdown
Concept system for <the thing>. Each entry gives the one designation to use for a concept, and the
designations that must not be used.

An entry belongs here when a reader who resolves the designation from ordinary language, or from
another context in this organisation, arrives at the wrong code. The reader already knows the general
case: whatever broad technical and business knowledge resolves correctly is not listed here, however
heavily this project uses it. Anything unlisted carries its ordinary meaning.

Cite an entry by designation and number — "<designation> (1.3)". A number never changes meaning.

## Legend

| Line | Carries |
|---|---|
| `**1.2 term ‹subject field›**` | one concept; the subject field separates senses of one designation |
| `SET term ‹sense› ‹sense›` | one designation with several senses, declared once for the set |
| definition | a phrase that substitutes for the term in a sentence |
| `ADMITTED` / `DEPRECATED` | another designation for **this** concept — allowed in a stated register, or wrong |
| `CONFUSABLE` | a designation naming a **different** concept |
| `RELATED` | a live headword the reader may have wanted instead |
| `NOTE` / `GAP` | true but not definitional / what no source states |

Replace a `DEPRECATED` designation with this headword. Follow a `CONFUSABLE` one to the concept it
names.
````

## One field, one test

**Delete-and-check:** omit the line and ask what lookup now returns the wrong answer. No answer, no
line. Content that fails its own field's test moves to the field whose test it passes.

The definition's test is stricter: it substitutes for the term in a running sentence and leaves it
true. `NOTE` is the last field to try, not the first — an instance goes there, not in a field of its own.
`GAP` is the one field that earns content by absence — a characteristic the reader needs that no consulted source settles, written as the open
question rather than a guess.

## Sections

Five to eight `## N` sections, each named after the reader's question rather than the code layout —
*The layer* · *Modules and code* · *Products and platforms* · *Business vocabulary* · *Auth, config
and infrastructure* · *Shorthand designations* is a set that has worked.

## Writer's rules

- **A definition stands alone.** It opens with something other than its own term, no two definitions
  define each other, it runs to one sentence, and it closes without a full stop.
- **Intensional definition.** Superordinate concept first, then only the characteristics that delimit
  this concept from its coordinates.
- **A delimiting negative is definitional**, carried on a verb: "which speaks the Anchanto product's
  contract and never calls a partner". A contrast with a *named neighbour* goes to `CONFUSABLE`
  instead. A definition opening `not …` or `is not …` is a negative definition however delimiting it
  is, and the judging pass returns it as a `fix`.
- **Part of speech is preserved.** A noun term takes a noun-phrase definition; an adjectival term
  takes a subject field of the form ‹of a …› and an adjectival definition.
- **A list of one drops its numbering** — `NOTE`, not `NOTE 1`.
- **Field text identical across set members** sits on the `SET` line, once.

## Three forms

**A row**, where a section is uniform and its entries carry a definition and nothing else. The number
stays in the row, so citations survive.

```markdown
| # | designation | definition |
|---|---|---|
| 7.1 | `CONN` | an area's connector deployable, `connector/<area>-connector` |
```

**A full entry**, where the concept carries a trap. Pull these out of the table. Where the trap is a
behaviour as well as a word, this entry carries the definition and the gotchas file carries the `Do:`.

**A `SET` line**, where one designation has several senses. One line names the set; each member carries
its own subject field.

```markdown
SET write-back ‹result leg› ‹partner direction› ‹credential refresh›
```
