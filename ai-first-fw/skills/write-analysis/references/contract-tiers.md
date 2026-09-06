# Contract tiers

The repository's context files name the systems. This file states who owns the contract between two
of them, because the owner settles whether a gap in that contract is work or a limit.

## The three tiers

| Tier | Who holds the contract | Where it is written | A gap in it is |
|---|---|---|---|
| `external` | A party outside the organisation | Their published documentation | A limit — the contract adapts to what they publish |
| `internal` | Another product of the same organisation, co-defined with this codebase | Both sides' specifications | Work — this codebase moves first, and tells that team |
| `integration` | This codebase, end to end | This repository | Work — this codebase does it |

## Settling the tier

Name the two systems the contract sits between, and read each one's level off the context files.

| The contract sits between | Tier |
|---|---|
| This codebase and a party outside the organisation | `external` |
| This codebase and another product of the same organisation | `internal` |
| Two modules inside this codebase | `integration` |

A module the context files place inside this codebase is `integration`, whatever it serves. Read the
level off the context file, so the tier follows what that file states.

## The order the work moves in

For each new value the contract carries:

1. Widen this codebase's own ingress to accept the value.
2. Implement this side end to end, so the surface that carries it is callable.
3. State in the contract that the surface now carries it, and tell the team on the other side.
4. Where the value travels back to an `internal` system, send it, and record that team's acceptance.

An `internal` contract that carries no such field yet is step 1 of this order. It sits in the changes
section as the item this codebase builds, with the request the other team receives.

## The deliverable

`integration` and `internal` work is delivered when its surface is callable and documented. Adoption
is the consumer's choice — a consumer calls this codebase's adapter, or reaches the party directly —
so the deliverable is the reachable surface, and a `D-n` states that it is reachable.

## Evidence order

The code holds this repository's behaviour, and the documents derive from it. A claim about what
this codebase does carries kind `code`. Where a document and the code state different things, the
code's locator and words go into the library row, and the document is corrected to match.

An `external` claim carries kind `url` or `doc`, and cites the party's own published page.

## Simulation

An `external` contract is published, and an `integration` or `internal` contract is this side's to
define, so both sides of every flow stand up against the repository's mocks. A flow that runs end to
end against the mocks is deliverable, and carries the `D-n` that states it.

## What reaches the preconditions table

A precondition row names an `external` contract limit, or a decision a named person settles. An
`integration` or `internal` gap carries its item in the changes section, and the `D-n` that closes
it.
