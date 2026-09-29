---
name: write-pr-desc
description: Writes the pull request title and description for the current branch from this session's work and the branch diff, filled into the repo's PR template and checked against the team's PR guidelines, then applies both to the open pull request once the developer approves. Use on "write the PR description", "draft the PR body", "write the PR title", on "update the PR description", and when asked to open or raise a pull request.
version: 1.2.0
disable-model-invocation: false
---

# write-pr-desc

One pull request title and body: shown in chat, the body also in a file, and — on the developer's
approval — both applied to the open pull request on GitHub. Alongside them, the **pre-flight**: the
team's PR guidelines checked against the branch, findings reported in chat.

`templates/pr-body.md` holds the title rule, the body's sections and the writing rule for each.

## Inputs

- **Session** — this conversation: what the branch is for, and the decisions behind it in the
  developer's own terms. Where the work happened elsewhere, the commit messages stand in.
- **Diff** — the branch against the commit it forked from, `git diff $(git merge-base HEAD
  origin/<base>)..HEAD`. The base is the developer's, or `origin/HEAD` where they name none.
- **Pull request** — the open pull request for the current branch, from `gh pr view --json
  number,title,url,body,labels`, and its build from `gh pr checks`. It can be absent.

## Step 1 — Read the session

Take the branch's purpose, every decision behind it, and every test scenario the developer ran from
this conversation.

**Completion:** the purpose, each decision and each test scenario are written down in the
developer's own terms, or the session is named as carrying none.

## Step 2 — Read the diff

Group what changed by the capability it serves, not by the file it sits in. Mark every migration,
query, entity or table change as a database change.

**Completion:** every file in the diff is accounted for under a named capability, and every
database change is listed.

## Step 3 — Run the pre-flight

Check the branch against each line, and record a finding for every line it fails:

| Guideline | Check |
|---|---|
| Build | `gh pr checks` passes, or the developer states a passing local build |
| Up to date | `git rev-list --count HEAD..origin/<base>` is `0`; otherwise rebase or merge the base |
| Clean code | No added line is commented-out code, a debug print, or a `catch` that swallows the error without logging it |
| Focused scope | The capabilities from Step 2 serve one purpose; unrelated ones are named as candidates to split |
| Environment branches | Where the base is QA, Stage or Master, the other environment branches this change must reach under the release flow are named |
| Label | One of `feature`, `bugfix`, `hotfix`, `enhancement` fits the branch, and it is named for the developer to attach |

**Completion:** every guideline carries a pass or a finding quoting the command output or the diff
line behind it.

## Step 4 — Fill the template

Copy `templates/pr-body.md` and fill the copy under its own comments. Write the title under the
template's title rule.

Where a pull request body already stands, read it and carry forward only lines the diff still
supports. Every line describing code this branch deletes is dropped.

Ship the title and the filled body in chat, the body as one fenced markdown block, and the same
body in a scratch file for `--body-file`.

**Completion:** every section of the copy is filled or deleted, every line inherited from the
existing body is matched to a change the diff still carries, and the scratch file's path is named
in chat.

## Step 5 — Get the title and body approved

Report the pre-flight findings. Name the pull request — number, current title, URL — say its title
and body will be **replaced**, and ask the developer to approve the title and body just shown or to
state the edits they want. Then wait.

Each approval covers the one title and body just shown; after an edit, show the revision and ask
again.

With no open pull request, or with `gh` missing or unauthenticated, name which and finish at the
chat block and the file.

**Completion:** the pre-flight findings are in chat, and the developer's approval of the exact title
and body just shown is in chat, or the reason the run finishes at the file is named.

## Step 6 — Apply it

```sh
gh pr edit <number> --title "<title>" --body-file <file>
```

**Completion:** the pull request URL is reported after the edit.

## The bar

- The body covers this branch and stands alone for the reviewer who opens no diff.
- Every capability the diff changes appears in the body, and every line in the body names something
  this branch altered.
- Every database change from Step 2 appears in the body with its query.
- Every pre-flight guideline is reported as a pass or a finding before the approval is asked.
- The title and body that reached GitHub are character-for-character the ones the developer approved.
- The title and every line of the body satisfy a rule quoted from `templates/pr-body.md`.
