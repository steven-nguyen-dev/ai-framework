#!/usr/bin/env python3
"""Wrapper alias for suite-IA-5105-US1-taxonomy.py."""
import os
import sys

target = os.path.join(os.path.dirname(__file__), "suite-IA-5105-US1-taxonomy.py")
os.execv(sys.executable, [sys.executable, target] + sys.argv[1:])
