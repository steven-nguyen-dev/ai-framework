# testbed guard

A `PreToolUse` hook on `Bash`, shipped by the `lv1-mcps` plugin (`hooks/hooks.json`). It closes the
shell gap the Read/Edit deny rules leave, so the `testbed` MCP stays the agents' only route. The key
isolation is the real protection; the guard is a text match, not a sandbox.

## Rules

| Rule | Purpose | Example (blocked) |
| --- | --- | --- |
| Key file: `.testbed.env`, `~/.config/lv1-testbed/` | Agents never read the testbed keys | `cat ~/.mcp/.testbed.env` |
| Mock host: `test.concavoi.com` | A direct call skips the MCP | `curl https://test.concavoi.com/x` |
| Admin API: `/api/content`, `/api/mocks`, `/api/lease`, `/api/servers`, `__testbed` | Mock admin goes through `mocks_*`, `stores_*`, `reset` | `curl $BASE/amazon/__testbed/reset` |
| Mock ports: 23000-23103 | Same, against a local mock | `curl localhost:23001/x` |
| Engine: running `suite/cli.py`, `-m suite.cli`, `testbed_client` | The MCP runs suites for agents | `python3 suite/cli.py run` |
| Mock data: `~/.local/share/lv1-testbed/` | Writing it bypasses the API | `rm -rf ~/.local/share/lv1-testbed` |

Path segments end at `/`, a quote, whitespace or the end, so `lv1-testbed-dev` and `lv1-testbed-mcp`
pass. Each rule runs on the raw command, with `\xNN`/`\NNN` escapes decoded, and with quotes and
backslashes removed. `bash -c` and `$(...)` need nothing more: their text is in the command.
Existing files the command executes (named next to an interpreter, or executable) are scanned
too, one level deep; a `unittest` run is not scanned through its files.

## Allowed

`wiki.concavoi.com`, `drive.concavoi.com`, other `~/.mcp` files, `ls ~/.local/share`,
`sed -n 1p ~/.zshrc`, `env`, `cat suite/cli.py`, `git` and `grep` on any of the names.

## Limits

A host built at runtime (`A=test.conc; B=avoi.com`), base64 or code-built strings, symlinks to the
keys, and tools that call the server on their own (tests, git hooks, `make`) are not seen.
If the guard fails to analyse a command, it denies it.

## Tests

```sh
cd lv1-mcp/testbed/guard && python3 -m unittest -v test_guard
```
