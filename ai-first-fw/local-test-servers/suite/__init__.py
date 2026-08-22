#!/usr/bin/env python3
"""One suite, one file: what it sends, what it expects, and why each case exists.

A suite file declares a `SUITE` and nothing else. The engine here does the rest -- preflight,
reset, firing, capturing the evidence, judging it and publishing the `results.json` the mock's
`/test` page renders -- so a requirement change or a defect is an edit to one file with no runner
to keep in step with it.

    from suite import (Suite, Case, Group, merge, key_from, Blocked, DELETE,
                       ControllerStatus, Calls, Status, Marker, Rows, QueueDelta, Custom,
                       PostJson, Sql, MySql, Queues,
                       AppResponds, MockResponds, DatabaseResponds, SeedRows, QueuesRespond)

Start from `suite/TEMPLATE.py`. The contract this engine meets, and the traps it
already handles, are written down in `TESTING.md`.
"""

from .model import Suite, Case, Group, Call, Blocked, merge, key_from, DELETE
from .checks import (Check, ControllerStatus, Calls, Status, Marker, Rows, QueueDelta, Custom,
                     marker_of)
from .resources import PostJson, Sql, MySql, Queues, Mock, probe_url
from .probes import (Probe, AppResponds, MockResponds, DatabaseResponds, SeedRows, QueuesRespond,
                     FileExists)

__all__ = [
    "Suite", "Case", "Group", "Call", "Blocked", "merge", "key_from", "DELETE",
    "Check", "ControllerStatus", "Calls", "Status", "Marker", "Rows", "QueueDelta", "Custom",
    "marker_of",
    "PostJson", "Sql", "MySql", "Queues", "Mock", "probe_url",
    "Probe", "AppResponds", "MockResponds", "DatabaseResponds", "SeedRows", "QueuesRespond",
    "FileExists",
]
