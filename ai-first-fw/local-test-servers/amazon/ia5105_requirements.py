#!/usr/bin/env python3
"""Convenience alias for IA-5105-US1-requirements.py.

All constants and functions are exported directly from IA-5105-US1-requirements.
"""

import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# Import and re-export everything from IA-5105-US1-requirements
_mod = __import__("IA-5105-US1-requirements")
for _k, _v in _mod.__dict__.items():
    if not _k.startswith("_"):
        globals()[_k] = _v
