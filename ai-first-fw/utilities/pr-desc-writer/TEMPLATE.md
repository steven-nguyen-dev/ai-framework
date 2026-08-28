<!-- The shape of a pull request description in this repo. `pr-desc-writer` is the process that
     fills it; this file is only the shape.

  · One clause per bullet, each thing said once. Behaviour, not file diffs — never one
    bullet per changed file, and never a file path as a bullet's subject.
  · Shortest form that still says it: what over how, why only where the what cannot stand alone.
  · Only what changed — delete any line whose point is that something is unchanged.
  · Spell out every code, ticket id and fixture value — what it means, not just its value.
    A bare code reads to its author only.
  · No local paths (a scratch folder, another checkout, `/tmp`, a mock's folder). Repo-relative is fine.
  · Delete every heading and comment you did not fill. Keep the numbers of the headings you
    keep — do not renumber to close a gap.

  Optional, add under 2. Changes when they apply:

  #### 2.1 New properties  — fields this PR adds. Name, type and class only; a retyped field is not
  | # | Property | Type | Class |    new, so it goes in one line under the table.
  |---|---|---|---|

  #### 2.2 Existing bugs fixed — only defects that already stood on the base branch. A bug this PR
                                 introduced and then fixed belongs in 2. Changes. Name the blast
                                 radius where it is wider than the feature.

  Optional, add under 4.2 Proof when behaviour changed:

  | Use case | Expected |   — one case per row: what is sent, what has to be true. Where many cases
  |---|---|                  share an outcome, one row naming them.
-->

### 1. Context
- Jira: 
<!-- IA-0000, or the link -->

- Problem: 
<!-- what was broken or missing, and what it cost -->

### 2. Changes
<!-- One bullet per capability the branch adds or alters, the one a reviewer must grasp first
     at the top. 200 characters each, hard cap — split what will not fit, never wrap it.
     What, not how. Why only where the what is unreadable without it.
     Several files serving one capability are one bullet; a path trails the bullet, never heads it. -->
-

### 3. Impact & Risks
<!-- Breaking changes, migrations, env vars, flags, work this depends on, decisions still open — or "None". -->
-

### 4. Verification

#### 4.1 How to test
<!-- Commands a reviewer can run, and what has to be running first. -->
-

#### 4.2 Proof
<!-- Test counts, and what was exercised end to end. -->
-
