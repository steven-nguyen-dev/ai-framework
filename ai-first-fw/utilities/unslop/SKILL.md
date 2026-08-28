---
name: unslop
description: Strip AI tells from a technical document, SKILL.md or README without inventing facts. Use on "unslop this", "remove AI tells", "clean up this doc", "de-slop", or before shipping any AI-drafted markdown.
version: 0.1.1
---

# unslop

Edit a technical document, a `SKILL.md` or a README. Marketing copy, blog prose and chat transcripts are out of scope.

The whole run is judged by one test, the **source test**: every word in the output traces to a word in the input or to a rule in §2. No edit adds a fact, number, date or name the input did not carry.

## §0 Never touch

Leave byte-identical:

- fenced code blocks, inline code, and everything inside them
- identifiers: field names, API paths, env vars, file paths, CLI flags, package names
- quoted source text, log output, terminal transcripts
- frontmatter keys and values, except `version`, which must be bumped per the repo Versioning Policy
- URLs, link targets, citation strings
- table headers that name a schema field
- any span preceded by `<!-- verbatim -->`

Every rule below applies to prose only.

## §1 Pass order

Run in order, do not interleave.

| Pass | Does | Rules |
|---|---|---|
| 1 Mechanical | find and replace, no judgment | M1-M6 |
| 2 Sentence | one sentence at a time | S1-S12 |
| 3 Structure | whole document | T1-T7 |
| 4 Report | change log, then ship checklist | §3, §4 |

Stop after pass 3. A further creative pass invents.

Over 800 words, run passes 1-3 per section, then §4 once on the whole file.

## §2 Rules

### Pass 1, mechanical

| # | Tell | Fix |
|---|---|---|
| M1 | curly quotes and apostrophes | straight `'` and `"` |
| M2 | title case heading | sentence case |
| M3 | decorative emoji in a heading or bullet | delete |
| M4 | fancy synonym | utilize, leverage → use. facilitate → help. numerous → many. in the event that → if. in order to → to. due to the fact that → because. additionally, moreover, furthermore → and, or delete. firstly, secondly → 1., 2., or delete |
| M5 | filler opener | delete: "It is important to note that", "It's worth noting", "Importantly,", "That said," where nothing was said, "Let's dive in", "In today's fast-paced world" |
| M6 | chatbot residue | delete: "I hope this helps", "Let me know if", "Of course!", "Certainly!", "Great question", "You're absolutely right", "Found the smoking gun" |

### Pass 2, sentence

| # | Tell | Fix |
|---|---|---|
| S1 | puffery | pivotal, testament to, evolving landscape, indelible mark, deeply rooted, groundbreaking, renowned, seamless, robust, comprehensive, best-in-class, game-changer, at scale → state what happened, or cut |
| S2 | AI vocabulary | crucial → needed, or cut. delve → read, examine. enhance → improve, or the mechanism. garner → get. interplay → how X and Y interact. intricate → complex, or the count. showcase → show. underscore → show. tapestry, vibrant → cut. streamline, empower, unlock, elevate → the verb the thing performs |
| S3 | fancy "is" | serves as, stands as, boasts, features → is, has |
| S4 | superficial -ing tail | "..., highlighting / ensuring / reflecting / fostering X" → a new sentence naming who does X, or cut |
| S5 | vague attribution | "Experts believe", "Industry reports suggest", "Some critics argue" → the source named in the input, else cut the claim |
| S6 | "not just X, but Y" | state Y |
| S7 | feeling in place of mechanism | "stays close at hand", "SQL you can read" → the call, the file, the failure. If it cannot be restated as an instruction, fact or number the input already carries, cut it. If the sentence would read the same in another project's docs, cut it |
| S8 | passive voice | "queries are validated" → "the compiler validates queries". Keep passive only where the input never names the actor |
| S9 | adverb propping a weak verb | "runs quickly" → "is fast", or the number if the input has one. No number in the input, cut the adverb and keep the verb |
| S10 | dense sentence | one idea per sentence, split at the clause a reader backtracks over |
| S11 | hedge stack | "could potentially possibly be argued that it might" → "may" |
| S12 | minimizer | simply, just, "all you need to do" → delete |

### Pass 3, structure

| # | Tell | Fix |
|---|---|---|
| T1 | forced triad, or every list 3-5 items | the real count |
| T2 | template shape: Overview, Benefits, Challenges, Conclusion; equal-length sections | the sections the content needs |
| T3 | inline-header list restating its own line, "**Performance:** Performance improved..." | prose. A bold lead-in ending in a period followed by new detail stays |
| T4 | opener restates the request, closer repeats the opener, "Key takeaways", "TL;DR", "The future looks bright" | delete both ends, open on the first fact |
| T5 | synonym cycling for one referent | pick one term, repeat it |
| T6 | false range, "from X to Y" not on a scale | list the items |
| T7 | boldface on every proper noun or acronym | bold only the load-bearing clause |

### Punctuation

Em dashes, parentheses and colons stay. Cap them.

| Mark | Limit | Over the limit |
|---|---|---|
| em dash | 1 per paragraph | the second becomes a period or a comma |
| mid-sentence colon | 0. Before a list or example, unlimited | rewrite the clause to stand without the comparison framing |
| parentheses | units, expansions, citations, labels | an aside carrying a claim becomes a sentence |

### Exemption

Keep a §2 word where it is the domain's own term rather than decoration: test harness, API surface, cryptographic primitive, scaffolding a project. Keep any term a reader will grep for.

### Never invent

S5, S7 and S9 ask for a source or a number. Where the input has none, cut the sentence. Do not supply one from memory, do not estimate, do not add a version, date or benchmark.

## §3 Output

Return the edited document, then a change log.

| Rule | Applied | Cut outright |
|---|---|---|

List every sentence cut for lacking a source, so the author can supply one.

## §4 Ship checklist

Every row must pass.

| # | Check |
|---|---|
| 1 | Code, identifiers and quoted text byte-identical to the input |
| 2 | No fact, number, date or name absent from the input |
| 3 | Every cut claim listed in the change log |
| 4 | Each surviving sentence carries its original meaning |
| 5 | Headings sentence case, quotes straight |
| 6 | Em dash at most 1 per paragraph, no mid-sentence colon |
| 7 | Domain terms kept, not swapped |
