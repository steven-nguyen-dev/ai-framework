---
name: write-pr-desc
description: Writes the pull request description for the current branch from this session's work and the branch diff, filled into the repo's PR template, then applies it to the open pull request once the developer approves. Use on "write the PR description", "draft the PR body", on "update the PR description", and when asked to open or raise a pull request.
version: 1.1.0
disable-model-invocation: false
---

# write-pr-desc

One pull request body: a fenced block in chat, the same body in a file, and — on the developer's
approval — the body of the open pull request on GitHub.

`templates/pr-body.md` holds the body's sections and the writing rule for each.

## Inputs

- **Session** — this conversation: what the branch is for, and the decisions behind it in the
  developer's own terms. Where the work happened elsewhere, the commit messages stand in.
- **Diff** — the branch against the commit it forked from, `git diff $(git merge-base HEAD
  origin/<base>)..HEAD`. The base is the developer's, or `origin/HEAD` where they name none.
- **Pull request** — the open pull request for the current branch, from `gh pr view --json
  number,title,url,body`. It can be absent.

## Step 1 — Read the session

Take the branch's purpose and every decision behind it from this conversation.

**Completion:** the purpose and each decision are written down in the developer's own terms, or the
session is named as carrying none.

## Step 2 — Read the diff

Group what changed by the capability it serves, not by the file it sits in.

**Completion:** every file in the diff is accounted for under a named capability.

## Step 3 — Fill the template

Copy `templates/pr-body.md` and fill the copy under its own comments.

Where a pull request body already stands, read it and carry forward only lines the diff still
supports. Every line describing code this branch deletes is dropped.

Ship the filled body twice: one fenced markdown block in chat, and the same text in a scratch file
for `--body-file`.

**Completion:** every section of the copy is filled or deleted, every line inherited from the
existing body is matched to a change the diff still carries, and the scratch file's path is named
in chat.

## Step 4 — Get the body approved

Name the pull request — number, title, URL — say its current body will be **replaced**, and ask the
developer to approve the body just shown or to state the edits they want. Then wait.

Each approval covers the one body just shown; after an edit, show the revised body and ask again.

With no open pull request, or with `gh` missing or unauthenticated, name which and finish at the
chat block and the file.

**Completion:** the developer's approval of the exact body just shown is in chat, or the reason the
run finishes at the file is named.

## Step 5 — Apply it

```sh
gh pr edit <number> --body-file <file>
```

**Completion:** the pull request URL is reported after the edit.

## The bar

- The body covers this branch and stands alone for the reviewer who opens no diff.
- Every capability the diff changes appears in the body, and every line in the body names something
  this branch altered.
- The body that reached GitHub is character-for-character the body the developer approved.
- Every line of the body satisfies a rule quoted from `templates/pr-body.md`.

