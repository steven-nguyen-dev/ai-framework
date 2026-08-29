---
name: git-coordinator
description: Sync the current feature branch into its QA or UAT mirror branch from a separate worktree — merge, build the merged result, push, open a draft PR — and tear the mirrors down once the work has landed. Use on "sync to qa", "sync to uat", "promote this to QA", when a mirror PR needs updating, or on "sync complete", "ticket done", "clean up the branches".
version: 0.4.0
---

# git-coordinator

The developer commits on the feature branch and stays there. Every merge, build and push happens in a
separate worktree.

Two jobs. **Sync** carries new commits to a mirror — steps 1 to 8. **Cleanup** removes the worktrees and
mirrors once the work has landed, on any signal that the ticket is finished. Cleanup has its own section
below and runs on its own request.

## Vocabulary

| Term | Meaning |
|---|---|
| **feature branch** | The developer's work branch, `feature/<rest>`. The single branch that receives commits. |
| **mirror** | `QA/<rest>` or `UAT/<rest>`. Carries the feature's commits plus the base's own history, so the PR shows the merged result rather than the feature's diff alone. |
| **base** | The long-lived branch the mirror's PR targets — one per environment, resolved in step 2. |
| **sync** | Merge feature into the mirror, merge base into the mirror, build, push. |
| **exception** | Any condition these steps leave open. Stop and ask the developer. |

Mirror names are mechanical: replace the leading `feature` segment with the target's name.
`feature/<owner>/<ticket>-<slug>` gives `QA/<owner>/<ticket>-<slug>` and `UAT/<owner>/<ticket>-<slug>`.

## Run settings

Every value below belongs to the repository, so resolve it at run time and echo the resolved set to the
developer before step 5 acts on it. Read the repository first; ask the developer for whatever the
repository leaves open, and treat their answer as settled for the rest of the run.

| Setting | Where to read it |
|---|---|
| **base branch per target** | The gate branches the repository's own merge check requires, named in its CI workflow files; else the local branches carrying an upstream (`git for-each-ref --format='%(refname:short) -> %(upstream:short)' refs/heads/`); else the base of the mirror's existing pull request (`gh pr list --head <mirror> --json baseRefName`); else the developer. |
| **release branch** | The branch the merge check's workflow triggers on, and the repository's default branch (`git symbolic-ref refs/remotes/origin/HEAD`). Where the two agree, that is the release branch; where they differ, ask. |
| **worktree path** | An existing entry in `git worktree list` for the mirror, else a sibling of the repository root named for the repository and target. |
| **build command** | The repository's own pipeline — its CI workflow files, the scripts they call, and the root build file. Take the module ordering, the recursion flags and the diff-base rule from the workflow itself. |
| **build environment** | The variables the repository's own build workflow sets, its env sample, or the developer. Values stay in the source they came from. |
| **toolchain** | The version the build workflow declares, and the module's own build file where it declares a different one. |

Remote branch listings carry every abandoned experiment the repository ever pushed, so a name that merely
looks like a base belongs to the developer's judgement — the CI workflow and the tracked local branches
are the sources that name one.

## 1. Orient

```sh
git rev-parse --show-toplevel
git rev-parse --abbrev-ref HEAD
git worktree list
```

Record the current branch and confirm at the end that it still holds.

The current branch starts with `feature/`. Any other branch is an **exception**.

A sync reads committed history, so uncommitted changes in the working tree are fine — report them and
carry on.

**Outcome:** repository root, feature branch name and existing worktrees are known, and the feature
branch prefix is confirmed.

## 2. Resolve the target and the run settings

QA or UAT — ask the developer when they left it open.

Fill the run settings table above, then fetch what the run needs:

```sh
git fetch origin <base> "<release branch>"
git fetch origin "<mirror>" 2>/dev/null || true
```

**Outcome:** target, mirror name, base, release branch, worktree path, build command and build
environment are all resolved and stated back to the developer.

## 3. Gate

**New work.** `git rev-list --no-merges --count origin/<mirror>..<feature>` comes back non-zero. A
missing mirror is the first sync and passes. A mirror that exists with nothing new is an **exception** —
report whether `origin/<base>` has moved and ask whether they want a base-only refresh.

**QA before UAT.** For UAT, `git rev-list --no-merges origin/QA/<rest>..<feature>` comes back empty.
Commits missing from the QA mirror, or a missing QA mirror, is an **exception**: list them and ask
whether to sync QA first.

Then count `origin/<QA base>..<feature>`. Non-zero means the QA pull request is still open. Name the
count, flag it, and continue.

**Outcome:** the sync is known to carry new commits, and the developer knows the state of the pull
requests ahead of it.

## 4. Get a worktree

Reuse the worktree from `git worktree list`, or create one at the resolved path:

```sh
git worktree add <worktree> <mirror>                     # mirror exists on origin
git worktree add -b <mirror> <worktree> origin/<base>    # first sync
```

Every git, build and push command from here carries `git -C <worktree>` or runs inside `<worktree>`, so
the main checkout keeps its branch, its build output and its IDE index throughout.

**Outcome:** a worktree exists on the mirror branch, and the main checkout is untouched.

## 5. Merge — feature first, base last

```sh
git -C <worktree> merge --no-ff <feature>
git -C <worktree> merge --no-ff origin/<base>
```

Base last, so the tip is the merged result CI and the reviewer will see.

A conflict is an **exception**. Leave it in place, list the conflicted files, and ask the developer to
resolve. Tell them the resolution matches the other mirror's, so both environments ship the same code.

**Outcome:** the mirror tip is the feature merged with the current base, with both merges recorded as
merge commits.

## 6. Build the merged result

A clean merge and a correct merge are different things. The base may hold a different version of a
shared model: it merges silently, then fails to compile, or leaves a guard off the path it was written
to cover. This build is the place that catches it — CI builds the pull request head, and the merge is
what ships.

Run the repository's own pipeline against the merged tree, using the build command and environment
resolved in the run settings. Where the pipeline computes an impacted module set from a diff base, give
it the merge base of the base branch and the merged head, and build the modules it names in the order
it gives.

A repository whose build steps stay unclear after reading it is an **exception**: ask how to build the
impacted modules. A build or test failure is an **exception**: report the failing module and the first
real error, and ask whether to fix it on the feature branch — fixes land on the feature branch and reach
the mirror through the next sync.

**Outcome:** the merged tree builds and its tests pass, or the developer holds the failing module and
the first real error.

## 7. Push and open a draft pull request

```sh
git -C <worktree> push -u origin <mirror>
gh pr list --head <mirror> --base <base> --state open
```

Run the **`pr-desc-writer`** skill yourself against the merged tree for the body — it reads the session
and the diff, fills the repo's PR template, and gets the developer's approval before anything reaches
GitHub.

With no open pull request, create it from the approved body:

```sh
gh pr create --draft --head <mirror> --base <base> --title "<subject>" --body-file <file>
```

An open pull request picks up the new commits from the push and keeps its existing body;
`pr-desc-writer` owns the body update, approval included.

A rejected push means the mirror moved on origin — **exception**. `gh` missing or unauthenticated is an
**exception**: report the successful push, give the compare URL, and hand over the body as a chat block.

**Outcome:** the mirror is on origin and a draft pull request exists against the base with an
approved body, or the developer holds the compare URL and the body.

## 8. Report

Mirror branch, commits carried, whether the base moved, modules built, push result, pull request URL,
and confirmation that the main checkout still sits on the feature branch.

**Outcome:** the developer can see everything the sync did from one message.

## Cleanup

Runs on "sync complete", "ticket done", "clean up the branches", or any similar signal that the work is
finished.

**Cleanup is all-or-nothing, and the gate is the release branch.** Every pull request in the chain has
merged — QA, UAT and release — before anything is deleted. While the feature is still outside the
release branch, one more commit sends the developer back through QA and UAT, and the mirrors are still
in use. An early delete just means rebuilding them.

```sh
git fetch origin <QA base> <UAT base> "<release branch>"
git rev-list --no-merges --count origin/<QA base>..origin/QA/<rest>       # 0 = QA PR merged
git rev-list --no-merges --count origin/<UAT base>..origin/UAT/<rest>     # 0 = UAT PR merged
git rev-list --no-merges --count origin/<release branch>..<feature>       # 0 = release PR merged
```

All three zero: proceed. Any non-zero is an **exception** — report all three counts, name which pull
request is still open, and keep every branch in place until the developer explicitly says to delete.

Then, for each mirror:

```sh
git worktree remove <worktree>            # add --force where the worktree holds scratch files
git worktree prune
git branch -d QA/<rest>                   # -d refuses an unmerged branch; that refusal is a signal
git push origin --delete QA/<rest>
```

`git worktree remove` refusing on a lock is an **exception** — the usual cause is a worktree whose
directory is already gone, cleared by `git worktree prune`, or a stale lock file that
`rm -rf .git/worktrees/<name>` clears. Report the path and ask before removing anything by hand.

The feature branch is the developer's, so it survives cleanup by default. Offer to delete it once it has
landed in the release branch, and delete it on a clear yes.

**Outcome:** the mirrors and their worktrees are gone from local and origin, the main checkout still
sits on the feature branch, and `git worktree list` holds only it.

## Merge method

Mirror pull requests merge with **Create a merge commit**. Squash and rebase rewrite commit SHAs, and the
gate on the release branch tests SHA reachability into the QA and UAT bases — a rewritten SHA blocks that
pull request permanently, repairable only by redoing the work.

For the same reason the feature branch stays append-only once any of its commits reaches a mirror. A
request to amend, rebase or force-push it is an **exception**: explain the cost first.

## Exceptions

Ask the developer on every one.

- Current branch is outside `feature/…`.
- Nothing new to carry.
- UAT requested with commits missing from the QA mirror.
- Merge conflict.
- Build or test failure.
- Push rejected.
- `gh` unavailable.
- Build steps still unclear after reading the repository.
- Cleanup requested while any pull request in the chain is still open.
- `git worktree remove` refused, or a branch delete refused as unmerged.
- **Case collision.** A case-insensitive filesystem folds `QA/<rest>` and an existing `qa/<rest>` into
  one ref path. Check `git branch --list --all -i "*<rest>"` before creating a mirror; a differently-cased
  twin is an exception — ask whether to reuse or rename it. A local mirror whose upstream names a ref
  origin lacks is the same collision seen from the other side.
- Worktree creation refused because the branch is checked out elsewhere. Report where.
