<!-- The shape of a pull request description in this repo, and every rule the filled body satisfies.
     `write-pr-desc` is the process that fills it; this file is the shape and the rules.

  Boundaries — the description covers this branch and stands alone for its reader.

  Tone — whatever changed is the grammatical subject, in the present tense, stating what now holds
    of it. Report the facts and let the reviewer appraise them.

  Concision — length tracks the size of the change. Each thing said once. Keep every line the
    reviewer would miss.

  · One clause per bullet. Every bullet's subject is a behaviour, and one bullet covers every file
    that serves it.
  · Shortest form that still says it: what over how, why where the what stands alone without it.
  · Only what changed — every line that survives names something this branch altered.
  · Spell out every code, ticket id and fixture value — what it means alongside its value, so it
    reads to someone other than its author.
  · Paths are repo-relative.
  · Delete every heading and comment left unfilled. Keep the original numbers on the headings that
    survive, gaps included.

  Optional, add under 2. Changes where they apply:

  #### 2.1 New properties  — fields this PR adds. Name, type and class only; a retyped field goes in
  | # | Property | Type | Class |    one line under the table.
  |---|---|---|---|

  #### 2.2 Existing bugs fixed — defects that already stood on the base branch. A bug this PR
                                 introduced and then fixed belongs in 2. Changes. Name the blast
                                 radius where it is wider than the feature.

  Optional, add under 4.2 Proof where behaviour changed:

  | Use case | Expected |   — one case per row: what is sent, what has to be true. Where many cases
  |---|---|                  share an outcome, one row naming them.
-->

### 1. Context
- Jira: 
<!-- the ticket id, or the link -->

- Problem: 
<!-- what was broken or missing, and what it cost -->

### 2. Changes
<!-- One bullet per capability the branch adds or alters, the one a reviewer must grasp first
     at the top. 200 characters each, hard cap — split what exceeds it into separate bullets.
     What, not how. Why where the what needs it to read.
     Several files serving one capability are one bullet; a path trails the bullet. -->
-

### 3. Impact & Risks
<!-- Breaking changes, migrations, env vars, flags, work this depends on, decisions still open — or "None". -->
-

### 4. Verification

#### 4.1 How to test
<!-- Commands a reviewer can run, and what has to be running first. Repeat what the developer said
     about testing; where the changes touch tests, "run the unit tests" says it. -->
-

#### 4.2 Proof
<!-- Test counts, and what was exercised end to end. -->
-
