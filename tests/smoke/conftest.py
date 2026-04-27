"""Shared fixtures for hermetic smoke tests.

Smoke tests run the CLI in a real subprocess with an isolated home directory.
They do not require a network connection or any credentials.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Callable

import pytest


@pytest.fixture()
def subprocess_cli(tmp_path: Path) -> Callable[..., subprocess.CompletedProcess]:
    """Run the teardrop CLI in a real subprocess with an isolated home directory.

    Returns a callable ``run(*args, extra_env=None)`` that invokes the CLI and
    returns the completed process.  Each call shares the same isolated ``HOME``
    directory so state written by one call is visible to the next.
    """
    home = tmp_path / "home"
    home.mkdir()

    def run(
        *args: str,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess:
        env = os.environ.copy()

        # Isolate home so config reads/writes go to our tmp dir
        env["HOME"] = str(home)
        env["USERPROFILE"] = str(home)  # Windows: Path.home() uses USERPROFILE

        # Strip any inherited Teardrop credentials so tests start clean
        for key in (
            "TEARDROP_API_KEY",
            "TEARDROP_TOKEN",
            "TEARDROP_EMAIL",
            "TEARDROP_SECRET",
            "TEARDROP_BASE_URL",
            "TEARDROP_CLIENT_ID",
            "TEARDROP_CLIENT_SECRET",
            "TEARDROP_SIWE_PRIVATE_KEY",
        ):
            env.pop(key, None)

        if extra_env:
            env.update(extra_env)

        return subprocess.run(
            [
                sys.executable,
                "-c",
                "from teardrop_cli.cli import app; app()",
                *args,
            ],
            capture_output=True,
            text=True,
            env=env,
        )

    return run
