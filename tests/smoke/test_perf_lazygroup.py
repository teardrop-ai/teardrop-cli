"""Smoke tests for CLI startup performance (LazyGroup).

The CLI docstring claims subcommands are imported only on demand, keeping
``teardrop --help`` well under 100 ms.  These tests verify that claim
structurally (no eager imports) and guard against catastrophic regressions.
"""

from __future__ import annotations

import subprocess
import sys
import time

import pytest


@pytest.mark.smoke
def test_help_lazy_imports() -> None:
    """Subcommand modules must NOT be imported when teardrop --help is shown.

    Verifies the LazyGroup contract: ``teardrop_cli.commands.*`` modules are
    absent from ``sys.modules`` immediately after the root app is imported.
    """
    code = (
        "import sys;"
        "from teardrop_cli.cli import app;"
        "loaded = [m for m in sys.modules if m.startswith('teardrop_cli.commands')];"
        "assert not loaded, f'Unexpected imports: {loaded}'"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.perf
def test_help_wall_time() -> None:
    """``teardrop --help`` completes within a 2 000 ms wall-time threshold.

    The threshold is intentionally generous to accommodate subprocess startup
    overhead on slow CI machines (~100-300 ms on Windows).  Its purpose is to
    catch catastrophic import regressions, not to benchmark raw startup speed.
    """
    # Warm-up: compile .pyc files so the measured run is not inflated by
    # first-run bytecode generation.
    subprocess.run(
        [sys.executable, "-c", "from teardrop_cli.cli import app"],
        capture_output=True,
    )

    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-c", "from teardrop_cli.cli import app; app()", "--help"],
        capture_output=True,
        text=True,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert result.returncode == 0, result.stderr
    assert "teardrop" in result.stdout.lower()
    assert elapsed_ms < 2000, f"--help took {elapsed_ms:.0f} ms (threshold: 2 000 ms)"


@pytest.mark.smoke
def test_quickstart_help_lazy() -> None:
    """``teardrop quickstart --help`` must not eagerly import other subcommands.

    quickstart's branches reference auth, tools, and llm_config, but those
    imports MUST be deferred to function bodies so listing help stays fast
    and free of side effects.
    """
    code = (
        "import sys;"
        "from teardrop_cli.cli import app;"
        "from click.testing import CliRunner;"
        "r = CliRunner().invoke(app, ['quickstart', '--help']);"
        "assert r.exit_code == 0, r.output;"
        # auth / tools / llm_config must remain unloaded
        "loaded = [m for m in ('teardrop_cli.commands.auth',"
        " 'teardrop_cli.commands.tools',"
        " 'teardrop_cli.commands.llm_config') if m in sys.modules];"
        "assert not loaded, f'Unexpected imports: {loaded}'"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
