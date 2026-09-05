#!/usr/bin/env python3
"""Backward-compatible wrapper alias for suite-IA-5105-US1-connect-us.py."""
import os
import sys

target = os.path.join(os.path.dirname(__file__), "suite-IA-5105-US1-connect-us.py")
os.execv(sys.executable, [sys.executable, target] + sys.argv[1:])
