The glossary's opening, its Legend, and the rules for writing an entry. The opening is copied into
`GLOSSARY.md`; everything below it stays here.

## The opening — copy verbatim, filling `<the thing>`

````markdown
Concept system for <the thing>. Each entry gives the one designation to use for a concept, and the
designations that must not be used.

An entry belongs here when a reader who resolves the designation from ordinary language, or from
another context in this organisation, arrives at the wrong code. Anything unlisted carries its
ordinary meaning.

Cite an entry by designation and number — "connector (1.3)". A number never changes meaning.

## Legend

| Line | Carries |
|---|---|
| `**1.2 term ‹subject field›**` | one concept; the subject field separates senses of one designation |
| `SET term ‹sense› ‹sense›` | one designation with several senses, declared once for the set |
| definition | a phrase that substitutes for the term in a sentence |
| `ADMITTED` / `DEPRECATED` | another designation for **this** concept — allowed in a stated register, or wrong |
| `CONFUSABLE` | a designation naming a **different** concept |
| `BROADER` `NARROWER` `PART OF` `PARTS` `COORDINATE` `RELATED` | concept relations |
| `NOTE` / `EXAMPLE` / `GAP` | true but not definitional / an instance / what no source states |

`DEPRECATED` is the wrong word for this concept; `CONFUSABLE` is the right word for another one.
Read one as the other and this file turns harmful: a designation you avoid gets replaced by this
headword, and a reference to the other concept silently becomes a reference to this one.
````

## One field, one test

The Legend says what each field carries. A field earns its content by one further test:
**delete-and-check** — omit the line, ask what lookup now returns the wrong answer, and keep it only
if there is one. Content that fails its own field's test moves to the field whose test it passes;
content that passes none is deleted. The definition's test is stricter: it substitutes for the term
in a running sentence and leaves it true.

`NOTE` is the residue and keeps only what delete-and-check keeps — the last field to try, not the
first. `GAP` is the one field that earns content by absence: a characteristic the reader will need
that no consulted source settles, so the next reader inherits the question rather than an invention.

## The gate resolves, the writer judges

The gate resolves designations against each other across every document. Everything visible inside a
single entry is yours:

- **A definition stands on its own terms.** It opens with something other than its own term, no two
  definitions define each other, it runs to one sentence, and it closes without a full stop.
- **A list of one drops its numbering.** One note is `NOTE`, not `NOTE 1`.
- **Field text identical across set members** sits on the `SET` line, once.

Three turn on judgement no checker could reach:

1. **Intensional definition.** Superordinate concept first, then only the characteristics that
   delimit this concept from its coordinates.
2. **A delimiting negative is definitional.** "which speaks the Anchanto product's contract and
   never calls a partner" is one sentence and belongs in the definition. A contrast with a *named
   neighbour* goes to `CONFUSABLE` — the distinction the gate cannot make for you. Carry the
   negative on a verb, as that example does; a definition opening `not …` or `is not …` trips the
   gate's negative-definition error however delimiting it is.
3. **Part of speech is preserved.** A noun term takes a noun-phrase definition; an adjectival term
   takes a subject field of the form ‹of a …› and an adjectival definition.

## Three forms

**A table, where a section is uniform.** Entries carrying a definition and nothing else are rows.
The number stays in the row, so citations survive.

```markdown
| # | designation | definition |
|---|---|---|
| 7.1 | `CONN` | an area's connector deployable, `connector/<area>-connector` |
| 7.2 | `AREACORE` | an area's core module |
```

**A full entry, where the concept carries a trap.** Pull these out of the table — they are what a
reader came for. Where the trap is a behaviour as well as a word, this entry carries the definition
and the gotchas file carries the `Do:`.

**A `SET` line, where one designation has several senses.** One line names the whole set, each
member carries its own subject field, and field text identical across members sits on the set line,
once.

```markdown
SET write-back ‹result leg› ‹partner direction› ‹credential refresh›
```
