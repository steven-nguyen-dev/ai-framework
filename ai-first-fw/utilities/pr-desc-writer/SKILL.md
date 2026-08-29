---
name: pr-desc-writer
description: Write the pull request description for the current branch, from this session's work and the file changes, shaped by the repo's PR template, then offer to apply it to the open pull request on GitHub. Use on "write the PR description", "write PR desc", "draft the PR body", "update the PR description", or when asked to open or raise a pull request.
version: 0.3.0
---

# pr-desc-writer

Read the session, read the file changes, write the PR into the template.

## 1. Read the session

The work is usually in this conversation, and the reasons behind the branch live there. Take them from
it.

**Outcome:** the branch's purpose and the decisions behind it are in hand, in the developer's own terms.

## 2. Read the file changes

The diff says what the branch does. Read it.

**Outcome:** every changed behaviour on the branch is accounted for, grouped by capability rather than
by file.

## 3. Write the PR into the template

[`TEMPLATE.md`](TEMPLATE.md) beside this file holds the shape. Fill it.

Section 4 repeats what the developer said about testing. Where the changes touch tests, *run the unit
tests* says it.

Output goes to chat as one fenced markdown block ready to paste; to a file where a file was asked for.

**Outcome:** a filled body a reviewer can read start to finish without opening the diff.

## 4. Offer to apply it to the open pull request

Find the pull request for the current branch:

```sh
gh pr view --json number,title,url,body
```

With no open pull request, or with `gh` missing or unauthenticated, say so and finish at the chat block.
The one exception is a caller that is about to create the pull request itself, `git-coordinator` among
them: get the body approved the same way, then hand it back as a file for `gh pr create --body-file`.

With an open pull request found — name it (number, title, URL), say the current body will be
**replaced**, and ask the developer to approve or to state the edits they want. Then wait.

The update runs once the developer's approval arrives in chat. Approval covers the one body just shown;
after any edit, show the revised body and ask again.

On approval:

```sh
gh pr edit <number> --body-file <file>
```

Write the approved body to a scratch file and pass it with `--body-file`. Report the pull request URL
after the edit.

**Outcome:** the pull request body is the one the developer approved, and its URL is reported — or the
body is in chat with the reason it stopped there.

## Principles

**Boundaries.** The description covers this branch and stands alone for its reader.

**Tone.** Whatever changed is the grammatical subject, in the present tense, stating what now holds of
it. Report the facts and let the reviewer appraise them.

**Concision.** Length tracks the size of the change. Each thing said once. Keep every line the reviewer
would miss.
