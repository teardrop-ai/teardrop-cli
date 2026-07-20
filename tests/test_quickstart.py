"""Tests for the `teardrop quickstart` wizard."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from click.testing import CliRunner

from teardrop_cli import config
from teardrop_cli.cli import app


@pytest.fixture(autouse=True)
def mock_quickstart_auth(monkeypatch):
    """By default, make get_client return a verified mock for sample runs."""
    from teardrop_cli._fixtures import make_jwt_payload

    mock_client = MagicMock()
    mock_client.get_me = AsyncMock(return_value=make_jwt_payload())
    mock_client.close = AsyncMock()
    monkeypatch.setattr(
        "teardrop_cli.config.get_client",
        lambda base_url=None, require_auth=True: mock_client,
    )
    return mock_client


class TestQuickstartCredCheck:
    def test_existing_creds_short_circuit(self, runner: CliRunner, monkeypatch):
        """When TEARDROP_API_KEY is set, quickstart detects local creds."""
        monkeypatch.setenv("TEARDROP_API_KEY", "fake-jwt")
        # No "Use them?" prompt; just source line and main menu. Pick "0" to exit.
        result = runner.invoke(app, ["quickstart"], input="0\n")
        assert result.exit_code == 0, result.output
        assert "saved session found locally" in result.output.lower()
        assert "checked when you choose an authenticated action" in result.output.lower()

    def test_existing_creds_shows_source_label(self, runner: CliRunner, monkeypatch):
        """When TEARDROP_API_KEY is set, the source label is displayed."""
        monkeypatch.setenv("TEARDROP_API_KEY", "fake-jwt")
        result = runner.invoke(app, ["quickstart"], input="0\n")
        assert result.exit_code == 0, result.output
        assert "(source: env:api_key)" in result.output

    def test_keyring_creds_short_circuit(self, runner: CliRunner, monkeypatch):
        """Credentials stored in keyring (not env/config) are also detected."""
        # Ensure no env creds
        for var in (
            "TEARDROP_API_KEY",
            "TEARDROP_TOKEN",
            "TEARDROP_EMAIL",
            "TEARDROP_SECRET",
            "TEARDROP_CLIENT_ID",
            "TEARDROP_CLIENT_SECRET",
        ):
            monkeypatch.delenv(var, raising=False)

        # mock_keyring fixture (autouse) provides an in-memory keyring backend.
        import keyring

        keyring.set_password(
            config._KEYRING_SERVICE, config._KEYRING_EMAIL_KEY, "user@example.com"
        )
        keyring.set_password(config._KEYRING_SERVICE, config._KEYRING_SECRET_KEY, "hunter2")

        result = runner.invoke(app, ["quickstart"], input="0\n")
        assert result.exit_code == 0, result.output
        assert "saved session found locally" in result.output.lower()

    def test_saved_token_is_not_validated_for_local_exploration(
        self, runner: CliRunner, monkeypatch
    ):
        """Local exploration does not require a network validation call."""
        monkeypatch.setenv("TEARDROP_API_KEY", "fake-jwt")

        result = runner.invoke(app, ["quickstart"], input="0\n")
        assert result.exit_code == 0, result.output
        assert "verifying saved credentials" not in result.output.lower()


class TestQuickstartScaffoldBranch:
    def test_scaffold_branch_invokes_tools_init(self, runner: CliRunner, monkeypatch, tmp_path):
        """Branch 1 calls tools.init and prints the publish hint."""
        monkeypatch.setenv("TEARDROP_API_KEY", "fake-jwt")
        monkeypatch.chdir(tmp_path)
        # choice 1 (scaffold); tool name "demo_tool"
        result = runner.invoke(app, ["quickstart"], input="1\ndemo_tool\n")
        assert result.exit_code == 0, result.output
        assert (tmp_path / "tool.json").exists()
        assert "publish" in result.output.lower()

    def test_scaffold_invalid_name_exits(self, runner: CliRunner, monkeypatch, tmp_path):
        monkeypatch.setenv("TEARDROP_API_KEY", "fake-jwt")
        monkeypatch.chdir(tmp_path)
        # Invalid name "BadName" — tools_init raises typer.Exit(1)
        result = runner.invoke(app, ["quickstart"], input="1\nBadName\n")
        assert result.exit_code != 0
        assert not (tmp_path / "tool.json").exists()


class TestQuickstartSampleRunBranch:
    def test_sample_run_executes_run(self, runner: CliRunner, monkeypatch):
        """Branch 2 executes the agent run instead of just printing a command."""
        monkeypatch.setenv("TEARDROP_API_KEY", "fake-jwt")

        run_called: dict = {}

        async def _fake_stream(client, message, thread, context, **kwargs):
            run_called["message"] = message

        from teardrop_cli.commands import run as run_mod

        monkeypatch.setattr(run_mod, "_stream", _fake_stream)
        monkeypatch.setattr(run_mod, "_estimate_cost", lambda *args, **kwargs: True)

        # choice 2 (run); prompt text; skip BYOK; skip estimate; confirm run
        result = runner.invoke(app, ["quickstart"], input="2\nhello there\nn\nn\ny\n")
        assert result.exit_code == 0, result.output
        assert "message" in run_called
        assert run_called["message"] == "hello there"
        assert "exploring" in result.output.lower()

    def test_sample_run_error_shown_gracefully(self, runner: CliRunner, monkeypatch):
        """A run failure prints the error and skips next-steps — wizard exits 0."""
        monkeypatch.setenv("TEARDROP_API_KEY", "fake-jwt")

        async def _failing_stream(client, message, thread, context, **kwargs):
            raise RuntimeError("network down")

        from teardrop_cli.commands import run as run_mod

        monkeypatch.setattr(run_mod, "_stream", _failing_stream)
        monkeypatch.setattr(run_mod, "_estimate_cost", lambda *args, **kwargs: True)

        result = runner.invoke(app, ["quickstart"], input="2\nping\nn\nn\ny\n")
        # _handle_run_error prints the error but doesn't raise; wizard finishes cleanly
        assert result.exit_code == 0, result.output
        # "continue exploring" is the next-steps text that should be suppressed
        assert "continue exploring" not in result.output.lower()


class TestQuickstartMarketplaceBranch:
    def test_marketplace_branch_calls_list(self, runner: CliRunner, monkeypatch):
        """Branch 3 invokes marketplace list_cmd and prints a subscribe hint."""
        monkeypatch.setenv("TEARDROP_API_KEY", "fake-jwt")

        listed: dict = {}

        def _fake_list_cmd(base_url=None, category=None, as_json=False):
            listed["called"] = True

        from teardrop_cli.commands import marketplace as marketplace_mod

        monkeypatch.setattr(marketplace_mod, "list_cmd", _fake_list_cmd)

        # choice 3 (marketplace)
        result = runner.invoke(app, ["quickstart"], input="3\n")
        assert result.exit_code == 0, result.output
        assert "called" in listed
        assert "subscribe" in result.output.lower()


class TestQuickstartAuthMenu:
    def test_new_user_email_signup(self, runner: CliRunner, monkeypatch):
        """New user → email path → signup() is invoked."""
        from teardrop_cli.commands import auth as auth_mod

        called = {}

        def _fake_signup(**kwargs):
            called["kwargs"] = kwargs

        monkeypatch.setattr(auth_mod, "signup", _fake_signup)
        for var in (
            "TEARDROP_API_KEY",
            "TEARDROP_TOKEN",
            "TEARDROP_EMAIL",
            "TEARDROP_SECRET",
            "TEARDROP_CLIENT_ID",
            "TEARDROP_CLIENT_SECRET",
        ):
            monkeypatch.delenv(var, raising=False)

        # choose sample run; no account (Enter=N default); choose default email signup
        result = runner.invoke(app, ["quickstart"], input="2\n\n\n")
        assert result.exit_code == 0, result.output
        assert "kwargs" in called

    def test_existing_user_email_login(self, runner: CliRunner, monkeypatch):
        """Existing user → email path → login() is invoked."""
        from teardrop_cli.commands import auth as auth_mod

        called = {}

        def _fake_login(**kwargs):
            called["kwargs"] = kwargs

        monkeypatch.setattr(auth_mod, "login", _fake_login)
        for var in (
            "TEARDROP_API_KEY",
            "TEARDROP_TOKEN",
            "TEARDROP_EMAIL",
            "TEARDROP_SECRET",
            "TEARDROP_CLIENT_ID",
            "TEARDROP_CLIENT_SECRET",
        ):
            monkeypatch.delenv(var, raising=False)

        # choose sample run; has account (y); choose email login (2)
        result = runner.invoke(app, ["quickstart"], input="2\ny\n2\n")
        assert result.exit_code == 0, result.output
        assert "kwargs" in called


class TestQuickstartAuthRecovery:
    def test_sample_run_recovers_stale_saved_session(self, runner: CliRunner, monkeypatch):
        from teardrop import AuthenticationError

        from teardrop_cli._fixtures import make_jwt_payload
        from teardrop_cli.commands import auth as auth_mod
        from teardrop_cli.commands import run as run_mod

        for variable in (
            "TEARDROP_API_KEY",
            "TEARDROP_TOKEN",
            "TEARDROP_EMAIL",
            "TEARDROP_SECRET",
            "TEARDROP_CLIENT_ID",
            "TEARDROP_CLIENT_SECRET",
        ):
            monkeypatch.delenv(variable, raising=False)
        config.store_token("stale-token")
        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(
            side_effect=[AuthenticationError("Token expired"), make_jwt_payload()]
        )
        mock_client.close = AsyncMock()
        reauth_called = {}
        monkeypatch.setattr(config, "get_client", lambda base_url=None: mock_client)
        monkeypatch.setattr(
            auth_mod,
            "interactive_reauthenticate",
            lambda base_url=None, warning_message=None: (
                reauth_called.update(warning=warning_message)
                or config.store_token("fresh-token")
                or True
            ),
        )
        monkeypatch.setattr(run_mod, "_estimate_cost", lambda *args, **kwargs: True)
        monkeypatch.setattr(run_mod, "_execute_run", lambda *args, **kwargs: None)

        result = runner.invoke(app, ["quickstart"], input="2\nhello\nn\nn\ny\n")

        assert result.exit_code == 0, result.output
        assert "no longer valid" in reauth_called["warning"].lower()
        assert "session verified" in result.output.lower()

    def test_invalid_environment_credentials_stop_before_prompt(
        self, runner: CliRunner, monkeypatch
    ):
        from teardrop import AuthenticationError

        monkeypatch.setenv("TEARDROP_API_KEY", "stale-token")
        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(side_effect=AuthenticationError("Unauthorized"))
        mock_client.close = AsyncMock()
        monkeypatch.setattr(config, "get_client", lambda base_url=None: mock_client)

        result = runner.invoke(app, ["quickstart"], input="2\n")

        assert result.exit_code == 0, result.output
        assert "TEARDROP_API_KEY" in result.output
        assert "Prompt" not in result.output

    def test_estimate_failure_does_not_ask_to_run(self, runner: CliRunner, monkeypatch):
        monkeypatch.setenv("TEARDROP_API_KEY", "fake-jwt")
        from teardrop_cli.commands import run as run_mod

        monkeypatch.setattr(run_mod, "_estimate_cost", lambda *args, **kwargs: False)
        monkeypatch.setattr(
            run_mod,
            "_execute_run",
            lambda *args, **kwargs: pytest.fail("run must not start after estimate failure"),
        )

        result = runner.invoke(app, ["quickstart"], input="2\nhello\nn\ny\n")

        assert result.exit_code == 0, result.output
        assert "No run started" in result.output
        assert "Run this prompt now?" not in result.output
