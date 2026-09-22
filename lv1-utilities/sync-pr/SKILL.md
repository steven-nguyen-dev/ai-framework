---
name: sync-pr
description: Syncs the current feature branch's commits into its QA or UAT mirror branch, then either pushes to the mirror's open pull request or opens a new draft one. Use on "sync to qa", "sync to uat", "promote this to QA", or when a mirror pull request needs updating; and on "sync complete", "ticket done", "clean up the branches" to tear the mirrors down.
version: 2.0.0
disable-model-invocation: false
---

# sync-pr

Carries the feature branch's commits to its **mirror** — `QA/<rest>` or `UAT/<rest>`, the feature branch
name with its leading segment swapped — and leaves one draft pull request open against the mirror's
base. The developer stays on the feature branch; the run works from a separate worktree.

`references/cleanup.md` tears the mirrors down — follow it on "sync complete", "ticket done", "clean up
the branches".

## Inputs

- **Target** — `QA` or `UAT`; ask when the developer leaves it open.
- **Base** — the branch the mirror's pull request targets, one per target. Read it from the gate
  branches the repository's own merge check requires; ask when the repository leaves it open.
- **Build command** — the per-module build and unit test invocation the repository's CI workflow uses,
  and the build file that maps a changed path to the module owning it.

## Step 1 — Merge into the mirror

Work from a worktree on the mirror branch, so the main checkout keeps its branch and its build output.
Merge the feature in, then the base, each as a merge commit — base last, so the tip is the merged result
CI and the reviewer will see.

UAT ships what QA has already seen: a UAT sync stops and asks when the QA mirror is missing any feature
commit. A conflict stops the run — the developer resolves it, and resolves it the same way in both
mirrors so the two environments ship the same code. A differently-cased twin of the mirror name folds
into the same ref on a case-insensitive filesystem, so look for one before creating the branch.

**Completion:** the mirror tip carries both merges as merge commits over a clean tree.

## Step 2 — Build what the merge touched

The base may hold a different version of a shared model: it merges silently, then fails to compile.
Build and unit-test only the modules owning a path that changed between the merged head and its merge
base with the base branch. A failure stops the run — fixes land on the feature branch and reach the
mirror through the next sync.

**Completion:** every changed path is accounted for by a module that was built or named as owned by
none, and every built module passed.

## Step 3 — Push, then decide

Push the mirror to origin, then ask GitHub what is open from it against the base.

- **A pull request is open** — the push is the whole update. It picks up the new commits, and the body
  stands as already written.
- **None is open** — run the `write-pr-desc` skill for the body, then open the pull request as a draft
  from it.

**Completion:** one pull request URL, reported with the commits carried, the modules built, and the
branch the main checkout sits on.

## Merge method

Mirror pull requests merge with **Create a merge commit**, and the feature branch stays append-only once
any commit of it reaches a mirror. Squash, rebase and force-push rewrite SHAs, and the release gate
tests SHA reachability into the QA and UAT bases — a rewritten SHA blocks that pull request permanently.

## The bar

- The main checkout sits on the feature branch it started on.
- Every built module's build and unit tests passed before the push ran.
- One pull request URL: a draft created where none was open, the existing one left alone where one was.
