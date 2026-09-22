"""Sends the one-line wake prompt to a pane, via the configured ``herdr`` command.

T0 in CONTRACT.md §8 is unresolved: the design doc names two spellings for this command. The
command therefore lives in ``config.toml`` as ``herdr.prompt_argv``, not in code here - this
module runs whatever argv the config names and never special-cases a spelling.

CONTRACT.md §4b: a zero exit code alone is not delivery. Herdr answers on stdout in JSON, and
this module reads that answer rather than trusting the exit code by itself - see ``send_prompt``.
"""

from __future__ import annotations

import json
import subprocess
from enum import Enum

from .common import ConfigError, PromptFailed
from .config import Config

# CONTRACT.md §4b: named outcomes `--wait` can report on stdout with exit 0. Both mean the
# submission never reached a running state - `send_prompt` treats them as `prompt_failed`,
# never as confirmation, and carries the name itself as `herdr_code`.
_STALL_TYPES = frozenset({"agent_prompt_stalled", "agent_blocked"})
_CONFIRMED_TYPE = "agent_prompted"


class PromptDelivery(Enum):
    """What ``send_prompt`` could verify about a dispatch that did not raise.

    Two members, not a bool: a bool's ``False`` reads as "did not happen", but the unconfirmed
    case is "happened, unknown whether it landed" - a third state a bool cannot spell, which is
    exactly the distinction CONTRACT.md §4b exists to draw.
    """

    CONFIRMED = "confirmed"
    """Herdr's own JSON said the pane received the prompt (``type: agent_prompted``)."""

    UNCONFIRMED = "unconfirmed"
    """The process exited 0 but said nothing this module can read as confirmation - stdout
    empty, not JSON, or JSON in a shape it does not recognise. An older Herdr, or an argv
    without ``--wait``, cannot confirm; that is not evidence of failure, so this is not one."""


def send_prompt(config: Config, pane: str, text: str) -> PromptDelivery:
    """Runs ``config.prompt_argv`` with ``{pane}``/``{text}`` substituted as whole argv elements.

    Never invokes a shell: each argv element is passed to ``subprocess.run`` verbatim, so
    ``text`` cannot inject a second command no matter what it contains.

    A zero exit code is necessary but not sufficient for delivery (CONTRACT.md §4b): Herdr can
    exit 0 while its own JSON reports an error or a stall, and this function reads that JSON
    rather than stopping at the exit code.

    @param pane the pane name to substitute for ``{pane}``
    @param text the one-line prompt to substitute for ``{text}``
    @return ``PromptDelivery.CONFIRMED`` when Herdr's JSON says the pane received the prompt;
        ``PromptDelivery.UNCONFIRMED`` when the process exited 0 but produced nothing this
        function can read as confirmation - empty stdout, non-JSON text, or JSON in an
        unrecognised shape. Fails open: an older Herdr or an argv without ``--wait`` cannot
        confirm, and treating that as a failure would refuse to dispatch on no evidence at all.
    @raises ConfigError if an argv element is not a valid ``str.format`` template against
        ``pane``/``text`` - e.g. a config value like ``--opt={a}`` carrying an unrelated brace.
        That is a bad `config.toml`, not a bug, and must not surface as a raw ``KeyError`` or
        ``IndexError``.
    @raises ConfigError if the command names a binary that does not exist. An absent ``herdr`` is a
        machine that cannot signal any pane, so it names the config value rather than masquerading
        as one pane's failed notification.
    @raises PromptFailed if the process exits non-zero or exceeds ``config.prompt_timeout_s``.
        Carries ``pane``, ``exit_code`` (``None`` on a timeout) and ``stderr``. This is a
        notification failure, not a write failure - callers write the Redis key before
        prompting and do not undo that write when this raises (CONTRACT §3).
    @raises PromptFailed if Herdr's own JSON carries an ``error`` object, or names one of the
        stall outcomes (``agent_prompt_stalled``, ``agent_blocked``): the exit code was 0 but
        Herdr itself says the prompt did not land. Carries ``pane``, the real ``exit_code``
        (0), ``stderr``, and ``herdr_code`` - Herdr's own code, so the envelope names what
        Herdr said rather than inventing a generic message.
    """
    argv = []
    for part in config.prompt_argv:
        try:
            argv.append(part.format(pane=pane, text=text))
        except (KeyError, IndexError) as exc:
            raise ConfigError(
                f"herdr.prompt_argv element {part!r} is not a valid argv template: {exc}",
                field="herdr.prompt_argv",
                actual=part,
            ) from exc
    command = argv[0]
    try:
        completed = subprocess.run(
            argv,
            shell=False,
            capture_output=True,
            text=True,
            timeout=config.prompt_timeout_s,
        )
    except FileNotFoundError as exc:
        raise ConfigError(
            f"{command} is not on PATH. T0 settles this spelling; set herdr.prompt_argv to it.",
            field="herdr.prompt_argv",
            actual=command,
        ) from exc
    except subprocess.TimeoutExpired as exc:
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        raise PromptFailed(
            f"{command} timed out after {config.prompt_timeout_s}s prompting {pane}.",
            pane=pane,
            exit_code=None,
            stderr=stderr or "",
        ) from exc
    if completed.returncode != 0:
        raise PromptFailed(
            f"{command} exited {completed.returncode} prompting {pane}.",
            pane=pane,
            exit_code=completed.returncode,
            stderr=completed.stderr or "",
        )
    return _read_reply(completed.stdout, pane, completed.stderr)


def _read_reply(stdout: str, pane: str, stderr: str) -> PromptDelivery:
    """Classifies a zero-exit reply. See ``send_prompt`` for the three outcomes and why."""
    payload = _parse_json_object(stdout)
    if payload is None:
        return PromptDelivery.UNCONFIRMED

    error = payload.get("error")
    if isinstance(error, dict):
        code = error.get("code") or ""
        message = error.get("message") or "no message"
        raise PromptFailed(
            f"herdr reported {code or 'an error'} prompting {pane}: {message}",
            pane=pane,
            exit_code=0,
            stderr=stderr or "",
            herdr_code=code,
        )

    msg_type = payload.get("type")
    if msg_type in _STALL_TYPES:
        raise PromptFailed(
            f"herdr reported {msg_type} prompting {pane}.",
            pane=pane,
            exit_code=0,
            stderr=stderr or "",
            herdr_code=msg_type,
        )
    if msg_type == _CONFIRMED_TYPE:
        return PromptDelivery.CONFIRMED
    return PromptDelivery.UNCONFIRMED


def _parse_json_object(stdout: str) -> dict[str, object] | None:
    """Returns the parsed JSON object, or ``None`` for anything that is not one.

    Empty stdout, plain text, a JSON array, or any other non-object shape all return ``None``
    here rather than raising - CONTRACT.md §4b treats every one of them as unconfirmed, not as
    a parse failure the caller must handle.
    """
    stripped = stdout.strip()
    if not stripped:
        return None
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
