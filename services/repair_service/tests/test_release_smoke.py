"""Test exercising the deterministic release smoke path within pytest."""

from __future__ import annotations

import sys
from pathlib import Path

# Add repo root to sys.path to access scripts
repo_root = Path(__file__).resolve().parent.parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from scripts.release_smoke import SmokeClient, run_smoke_verification  # noqa: E402


def test_full_release_smoke_suite() -> None:
    """Run all 17 release smoke verification checks end-to-end."""
    client = SmokeClient()
    try:
        run_smoke_verification(client)
    finally:
        client.close()
