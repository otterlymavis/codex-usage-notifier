#!/usr/bin/env python3
"""Run the repository's shared Codex usage notifier from the Claude skill folder."""

from __future__ import annotations

import runpy
from pathlib import Path


ROOT_SCRIPT = Path(__file__).resolve().parents[4] / "codex_usage_notifier.py"

if __name__ == "__main__":
    runpy.run_path(str(ROOT_SCRIPT), run_name="__main__")
