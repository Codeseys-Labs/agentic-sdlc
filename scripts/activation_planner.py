#!/usr/bin/env python3
"""Compatibility loader for the canonical P2 activation planner."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

_CANONICAL = Path(__file__).resolve().parents[1] / "skills" / "agentic-sdlc" / "tools" / "activation-planner.py"


def _load():
    spec = importlib.util.spec_from_file_location("_agentic_sdlc_activation_planner", _CANONICAL)
    if spec is None or spec.loader is None:
        raise RuntimeError("canonical activation planner is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    os.execv(os.fspath(Path(sys.executable)), [sys.executable, os.fspath(_CANONICAL), *sys.argv[1:]])
else:
    _module = _load()
    globals().update({name: value for name, value in vars(_module).items() if not name.startswith("__")})
