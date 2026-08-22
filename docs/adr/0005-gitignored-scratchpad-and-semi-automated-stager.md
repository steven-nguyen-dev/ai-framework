# Gitignored Scratchpads and Semi-Automated Staging

We store all transient task artifacts (`raw-context.md`, `spec.md`, `plan.md`) inside a local, gitignored `.scratchpads/<task-slug>/` directory to avoid polluting team git histories and support concurrent task contexts. Furthermore, the workflow terminates at a semi-automated staging boundary where the agent prepares clean semantic commits and formats the `gh pr create` command, leaving the physical remote push and PR publishing to final human execution.

