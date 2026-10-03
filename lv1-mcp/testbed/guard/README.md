# testbed guard

A Claude Code `PreToolUse` hook on `Bash`. It keeps agents off the mock server, its local data
(`~/.local/share/lv1-testbed`), the testbed engine and MCP secrets, so the `testbed` MCP is their only route to them. When it denies a command, the
reason names the MCP tool to use instead.

## What it blocks

| Category | Matches |
| --- | --- |
| Mock server | `concavoi`, ports `2300x` / `2310x`, `/api/content`, `/api/mocks`, `/api/lease`, `/api/servers`, `__testbed`, `/log/data` |
| Secrets | `X-Auth-Token`, `ADMIN_PASSWORD`, `PATH_KEY`, `TESTBED_API_TOKEN`, `TESTBED_PATH_KEY`, `lv1-testbed`, `testbed.env`, any `.mcp` path, `~/.config` aimed at `lv1*` or globbed, globs on home dot-dirs, grep over a directory holding `~/.mcp`, `~/.config/lv1-testbed` or `~/.local/share/lv1-testbed`, environment dumps (`env`, `printenv`, `set`, `export -p` at the end of a command or before a pipe), `ps` with `e`, `launchctl getenv` |
| Mock server data | `~/.local/share/lv1-testbed`, and `~/.local`, `~/.local/share` bare or globbed (writing the data bypasses the API) |
| Engine | `cli.py`, `suite.cli`, `-m cli`, `testbed_client`, `commands.sync` |

Each rule is checked against the raw command and against forms an evasion would hide behind:
`\xNN` / `\NNN` / `\uNNNN` escapes expanded, quotes and backslashes removed, a compact form with
whitespace, `+`, `,`, `$` and brackets removed (host and secret names only), the reverse of each,
and decoded base64 and hex tokens (two levels).

Script files the command would run are scanned too, up to two levels of scripts naming scripts:
any existing file named in a command that also runs an interpreter (`python`, `bash`, `node`,
`source`, `eval`, `xargs`, `env`, …), and any executable file it names.

## What it allows

- Edit/Write/Read tool calls (not matched; `permissions.deny` covers `~/.mcp/**`,
  `~/.config/lv1-testbed/**` and `~/.local/share/lv1-testbed/**`).
- `git` with a known subcommand: the commit message, `--grep`, `-S`/`-G` text and file names such
  as `suite/cli.py` are not scanned, since git runs none of them.
- `grep` / `rg` / `git grep`: the pattern is not scanned, so you can search the repos for the host
  or secret names. The paths are, and a path that covers `~/.mcp` or `~/.config/lv1-testbed`
  is blocked.
- `python -m unittest …`: test files are not scanned, because they hold fixture text.

## Known limits

A text guard cannot run the shell, so it misses anything the command builds at runtime:

1. A host or name split across variables (`A=test.conc; B=avoi.com; curl https://$A$B/`).
2. Strings built by code: `chr()` lists, ROT13, `tr`, XOR, string slicing, anything not base64 or
   hex.
3. Values read at runtime from a file the guard does not treat as a script (`curl "https://$(cat host.txt)/"`).
4. A unit test, a git hook (`pre-commit`), a `make` target or a `npm` script that calls the server:
   the guard scans what the command names, not what a tool loads on its own.
5. A file written by Edit/Write and run later through an interpreter the guard does not list, or
   run through a path it cannot resolve (`$DIR/x.sh` where `DIR` is set at runtime).
6. Symlinks or hard links to the secrets made under another name, then read through that name.
7. `git` aliases (`git config alias.x '!curl …'`) are blocked only because `config` is not a known
   subcommand; a pre-existing alias that shadows a known name is not inspected.
8. Commands sent to another process: an existing terminal multiplexer pane, `osascript` driving a
   terminal app, or a background job started before the hook was installed.

`test_guard.py` keeps the first cases in `KNOWN_GAPS`, so a fix shows up as a failing test.

It also blocks some harmless commands: any mention of the patterns outside git and grep, for
example `wc -l suite/cli.py`, `python -m venv env`, or `cat` of a file named `testbed.env`. Use the
Read tool for those files.

## Install

Registered in `~/.claude-clone/settings.json`:

```json
"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command",
  "command": "python3 '<repo>/lv1-mcp/testbed/guard/guard.py'", "timeout": 10}]}]
```

If the guard fails to analyse a command, it denies it.

## Tests

```sh
cd lv1-mcp/testbed/guard && python3 -m unittest -v test_guard
```
