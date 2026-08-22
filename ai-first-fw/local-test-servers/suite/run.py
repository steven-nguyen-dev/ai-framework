#!/usr/bin/env python3
"""Command line for a suite file.

    python3 <mock>/suite-<name>.py                 every case
    python3 <mock>/suite-<name>.py --fast          skip the cases that only wait
    python3 <mock>/suite-<name>.py N1 K1 K4        only the cases named
    python3 <mock>/suite-<name>.py --judge <run>   re-score a folder, fire nothing
    python3 <mock>/suite-<name>.py --list          the cases and what each expects

A suite file is also runnable through this module, which is what the mock's `/test` page uses:

    python3 suite/run.py eton/suite-flow2.py --fast
"""

import importlib.util
import os
import sys

# Absolute, after putting the package's own parent on the path: this module is started both as a
# script and as part of the package, and a relative import fails in the first case.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from suite import engine


def package_root():
    """The `local-test-servers` folder itself -- the one holding `mock.py` and this engine.

    Every mock folder is a child of it and every run folder sits inside one, so a suite works the
    same whatever directory it was started in -- the `/test` page starts it from the mock's own
    folder -- and the whole package can be moved without editing a path.
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_suite(path):
    """Imports a suite file by path and returns the `SUITE` it declares."""
    path = os.path.abspath(path)
    package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    spec = importlib.util.spec_from_file_location(
        "suite_file_" + os.path.basename(path).replace(".", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "SUITE"):
        raise SystemExit("%s declares no SUITE" % path)
    return module.SUITE


def main(suite_path, argv):
    suite = load_suite(suite_path)
    package = package_root()

    if "--list" in argv:
        for case in suite.cases:
            print("%-4s %-6s wait %-4d %s" % (case.id, case.shape, case.wait, case.name))
            print("       %s" % engine.describe(suite, case))
        return 0

    if "--judge" in argv:
        folder = argv[argv.index("--judge") + 1]
        return engine.rejudge(suite, folder)

    fast = "--fast" in argv
    ids = [a for a in argv if not a.startswith("--")]
    return engine.execute(suite, package, engine.settings(suite), ids, fast)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2:]))
