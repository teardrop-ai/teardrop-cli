"""Tests for the `teardrop quickstart` wizard."""

from __future__ import annotations

from click.testing import CliRunner

from teardrop_cli.cli import app


class TestQuickstartCredCheck:
    def test_existing_creds_short_circuit(
        self, runner: CliRunner, monkeypatch
    ):
        """When TEARDROP_API_KEY is set, wizard offers to use existing creds."""
        monkeypatch.setenv("TEARDROP_API_KEY", "fake-jwt")
        # Inputs: confirm "Use them?" → y; choose "Exit" → 4.
        result = runner.invoke(app, ["quickstart"], input="y\n4\n")
        assert result.exit_code == 0, result.output
        assert "existing credentials" in result.output.lower()

    def test_keyring_creds_short_circuit(
        self, runner: CliRunner, monkeypatch
    ):
        """Credentials stored in keyring (not env/config) are also detected."""
        # Ensure no env creds
        for var in ("TEARDROP_API_KEY", "TEARDROP_TOKEN", "TEARDROP_EMAIL",
                    "TEARDROP_SECRET", "TEARDROP_CLIENT_ID", "TEARDROP_CLIENT_SECRET"):
            monkeypatch.delenv(var, raising=False)

        # mock_keyring fixture (autouse) provides an in-memory keyring backend.
        import keyring

        from teardrop_cli.config import _KEYRING_EMAIL_KEY, _KEYRING_SECRET_KEY, _KEYRING_SERVICE
        keyring.set_password(_KEYRING_SERVICE, _KEYRING_EMAIL_KEY, "user@example.com")
        keyring.set_password(_KEYRING_SERVICE, _KEYRING_SECRET_KEY, "hunter2")

        result = runner.invoke(app, ["quickstart"], input="y\n4\n")
        assert result.exit_code == 0, result.output
        assert "existing credentials" in result.output.lower()


class TestQuickstartScaffoldBranch:
    def test_scaffold_branch_invokes_tools_init(
        self, runner: CliRunner, monkeypatch, tmp_path
    ):
        """Branch 1 calls tools.init and prints the publish hint."""
        monkeypatch.setenv("TEARDROP_API_KEY", "fake-jwt")
        monkeypatch.chdir(tmp_path)
        # use creds → y; choice 1 (scaffold); tool name "demo_tool"
        result = runner.invoke(
            app, ["quickstart"], input="y\n1\ndemo_tool\n"
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
            app, ["quickstart"], input="y\n1\nBadName\n"
        )
        assert result.exit_code != 0
        assert not (tmp_path / "tool.json").exists()


class TestQuickstartSampleRunBranch:
    def test_sample_run_executes_run(
        self, runner: CliRunner, monkeypatch
    ):
        """Branch 2 executes the agent run instead of just printing a command."""
        monkeypatch.setenv("TEARDROP_API_KEY", "fake-jwt")

        run_called: dict = {}

        async def _fake_stream(client, message, thread, context):
            run_called["message"] = message

        from teardrop_cli.commands import run as run_mod
        monkeypatch.setattr(run_mod, "_stream", _fake_stream)

        # use creds → y; choice 2 (run); prompt text; skip BYOK → n
        result = runner.invoke(
            app, ["quickstart"], input="y\n2\nhello there\nn\n"
        )
        assert result.exit_code == 0, result.output
        assert "message" in run_called
        assert run_called["message"] == "hello there"
        assert "exploring" in result.output.lower()

    def test_sample_run_error_shown_gracefully(
        self, runner: CliRunner, monkeypatch
    ):
        """A run failure prints the error and skips next-steps — wizard exits 0."""
        monkeypatch.setenv("TEARDROP_API_KEY", "fake-jwt")

        async def _failing_stream(client, message, thread, context):
            raise RuntimeError("network down")

        from teardrop_cli.commands import run as run_mod
        monkeypatch.setattr(run_mod, "_stream", _failing_stream)

        result = runner.invoke(
            app, ["quickstart"], input="y\n2\nping\nn\n"
        )
        # _handle_run_error prints the error but doesn't raise; wizard finishes cleanly
        assert result.exit_code == 0, result.output
        assert "exploring" not in result.output.lower()


class TestQuickstartMarketplaceBranch:
    def test_marketplace_branch_calls_list(
        self, runner: CliRunner, monkeypatch
    ):
        """Branch 3 invokes marketplace list_cmd and prints a subscribe hint."""
        monkeypatch.setenv("TEARDROP_API_KEY", "fake-jwt")

        listed: dict = {}

        def _fake_list_cmd(base_url=None, category=None, as_json=False):
            listed["called"] = True

        from teardrop_cli.commands import marketplace as marketplace_mod
        monkeypatch.setattr(marketplace_mod, "list_cmd", _fake_list_cmd)

        # use creds → y; choice 3 (marketplace)
        result = runner.invoke(app, ["quickstart"], input="y\n3\n")
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
            "TEARDROP_API_KEY", "TEARDROP_TOKEN", "TEARDROP_EMAIL",
            "TEARDROP_SECRET", "TEARDROP_CLIENT_ID", "TEARDROP_CLIENT_SECRET",
        ):
            monkeypatch.delenv(var, raising=False)

        # no account (Enter=N default); choose email signup (2); exit (4)
        result = runner.invoke(app, ["quickstart"], input="\n2\n4\n")
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
            "TEARDROP_API_KEY", "TEARDROP_TOKEN", "TEARDROP_EMAIL",
            "TEARDROP_SECRET", "TEARDROP_CLIENT_ID", "TEARDROP_CLIENT_SECRET",
        ):
            monkeypatch.delenv(var, raising=False)

        # has account (y); choose email login (2 = default); exit (4)
        result = runner.invoke(app, ["quickstart"], input="y\n\n4\n")
        assert result.exit_code == 0, result.output
        assert "kwargs" in called

