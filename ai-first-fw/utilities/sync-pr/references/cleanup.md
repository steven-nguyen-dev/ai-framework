# Cleanup

Removes the worktrees and the mirror branches once the work has landed.

## Step 1 — Gate on the release branch

All-or-nothing, and the gate is the release branch: QA, UAT and release have all merged before anything
is deleted. While the feature sits outside the release branch one more commit sends the developer back
through QA and UAT, and the mirrors are still in use.

Confirm three comparisons carry nothing: each mirror against its base, and the feature branch against
the release branch. Anything left stops the run — report all three, name the pull request still open,
and keep every branch in place.

**Completion:** all three comparisons are reported, and each one is empty.

## Step 2 — Tear down each mirror

Remove the worktree, prune, delete the branch locally and on origin. Delete locally with the merge check
on, so a refusal surfaces work that never landed rather than discarding it.

The feature branch is the developer's, so it survives by default — offer to delete it, and delete it on
a clear yes.

**Completion:** no mirror for this ticket remains on local or origin, the worktree list holds the main
checkout alone, and the main checkout still sits on the feature branch.
