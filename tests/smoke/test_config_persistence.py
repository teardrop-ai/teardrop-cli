"""Smoke tests proving config values persist across subprocess boundaries.

These tests invoke the CLI in two separate subprocesses (sharing the same
isolated home directory) to prove that TOML config round-trips correctly.
They verify cross-process state that CliRunner-based unit tests cannot cover
because CliRunner reuses the same Python process and import cache.
"""

from __future__ import annotations

import pytest


@pytest.mark.smoke
def test_set_then_get_round_trips(subprocess_cli) -> None:
    """A value written by ``config set`` is visible to a later ``config get``."""
    set_result = subprocess_cli("config", "set", "api_url", "https://persist.example")
    assert set_result.returncode == 0, set_result.stderr

    get_result = subprocess_cli("config", "get", "api_url")
    assert get_result.returncode == 0, get_result.stderr
    assert "https://persist.example" in get_result.stdout


@pytest.mark.smoke
def test_init_creates_readable_config(subprocess_cli) -> None:
    """``teardrop init`` writes a config.toml that a later process can list."""
    init_result = subprocess_cli("init")
    assert init_result.returncode == 0, init_result.stderr

    list_result = subprocess_cli("config", "list")
    assert list_result.returncode == 0, list_result.stderr


@pytest.mark.smoke
def test_init_with_base_url_persists(subprocess_cli) -> None:
    """``teardrop init --base-url`` value survives to a new process."""
    subprocess_cli("init", "--base-url", "https://staging.example")
    get_result = subprocess_cli("config", "get", "api_url")
    assert get_result.returncode == 0, get_result.stderr
    assert "staging.example" in get_result.stdout


@pytest.mark.smoke
def test_disallowed_key_rejected(subprocess_cli) -> None:
    """``config set access_token …`` must be rejected (exit != 0)."""
    result = subprocess_cli("config", "set", "access_token", "should-be-rejected")
    assert result.returncode != 0
