"""Tests for the `teardrop quickstart` wizard."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from teardrop_cli.cli import app


class TestQuickstartCredCheck:
    def test_existing_creds_short_circuit(
        self, runner: CliRunner, monkeypatch
    ):
        """When TEARDROP_API_KEY is set, wizard offers to use existing creds."""
        monkeypatch.setenv("TEARDROP_API_KEY", "fake-jwt")
        # Inputs: confirm "Use them?" → y; skip BYOK → n; choose "Exit" → 3.
        result = runner.invoke(app, ["quickstart"], input="y\nn\n3\n")
        assert result.exit_code == 0, result.output
        assert "existing credentials" in result.output.lower()


class TestQuickstartScaffoldBranch:
    def test_scaffold_branch_invokes_tools_init(
        self, runner: CliRunner, monkeypatch, tmp_path
    ):
        """Branch 1 calls tools.init and prints the publish hint."""
        monkeypatch.setenv("TEARDROP_API_KEY", "fake-jwt")
        monkeypatch.chdir(tmp_path)
        # use creds → y; skip BYOK → n; choice 1; tool name "demo_tool"
        result = runner.invoke(
            app, ["quickstart"], input="y\nn\n1\ndemo_tool\n"
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "tool.json").exists()
        assert "publish" in result.output.lower()

    def test_scaffold_invalid_name_exits(
        self, runner: CliRunner, monkeypatch, tmp_path
    ):
        monkeypatch.setenv("TEARDROP_API_KEY", "fake-jwt")
        monkeypatch.chdir(tmp_path)
        # Invalid name "BadName" — tools_init raises typer.Exit(1)
        result = runner.invoke(
            app, ["quickstart"], input="y\nn\n1\nBadName\n"
        )
        assert result.exit_code != 0
        assert not (tmp_path / "tool.json").exists()


class TestQuickstartSampleRunBranch:
    def test_sample_run_prints_command(
        self, runner: CliRunner, monkeypatch
    ):
        """Branch 2 just prints the `teardrop run` command — no execution."""
        monkeypatch.setenv("TEARDROP_API_KEY", "fake-jwt")
        result = runner.invoke(
            app, ["quickstart"], input="y\nn\n2\nhello there\n"
        )
        assert result.exit_code == 0, result.output
        assert "teardrop run" in result.output


class TestQuickstartAuthMenu:
    def test_signup_branch_calls_signup(self, runner: CliRunner, monkeypatch):
        """No existing creds → choose option 2 → signup() is invoked."""
        # Patch signup to a no-op so we don't hit the network.
        from teardrop_cli.commands import auth as auth_mod

        called = {}

        def _fake_signup(**kwargs):
            called["kwargs"] = kwargs

        monkeypatch.setattr(auth_mod, "signup", _fake_signup)
        # Re-import quickstart so its `from auth import signup` picks up patch.
        # (quickstart imports inside _auth_menu, so the patch is hit at runtime.)
        # No env creds set → cred check returns False.
        for var in (
            "TEARDROP_API_KEY",
            "TEARDROP_TOKEN",
            "TEARDROP_EMAIL",
            "TEARDROP_SECRET",
            "TEARDROP_CLIENT_ID",
            "TEARDROP_CLIENT_SECRET",
        ):
            monkeypatch.delenv(var, raising=False)

        # choice 2 (signup); skip BYOK → n; exit → 3
        result = runner.invoke(app, ["quickstart"], input="2\nn\n3\n")
        assert result.exit_code == 0, result.output
        assert "kwargs" in called
