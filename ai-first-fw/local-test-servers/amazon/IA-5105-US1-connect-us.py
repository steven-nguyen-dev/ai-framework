#!/usr/bin/env python3
"""Short alias for IA-5105-US1-suite-connect-us.py."""
import os
import sys

target = os.path.join(os.path.dirname(__file__), "IA-5105-US1-suite-connect-us.py")
os.execv(sys.executable, [sys.executable, target] + sys.argv[1:])
