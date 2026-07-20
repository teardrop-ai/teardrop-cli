from __future__ import annotations

from unittest.mock import patch

import pytest

from teardrop_cli.formatting import handle_token_expiry


@pytest.mark.asyncio
async def test_handle_token_expiry_retry_on_refreshable_source():
    from teardrop import AuthenticationError

    exc = AuthenticationError("Token has expired")

    with patch("teardrop_cli.config.detect_credential_source") as mock_source:
        mock_source.return_value = "keyring:email"

        with patch("teardrop_cli.formatting.print_warning") as mock_warn:
            action = await handle_token_expiry(exc)

            assert action == "retry"
            mock_warn.assert_called_once_with("Session expired. Attempting auto-refresh...")


@pytest.mark.asyncio
async def test_handle_token_expiry_fail_on_no_email_non_interactive():
    from teardrop import AuthenticationError

    exc = AuthenticationError("Token has expired")

    with (
        patch("teardrop_cli.config.detect_credential_source") as mock_source,
        patch("teardrop_cli.config.get_siwe_key") as mock_siwe,
    ):
        # Config token source, no SIWE key to recover with.
        mock_source.return_value = "config:token"
        mock_siwe.return_value = None

        with patch("teardrop_cli.formatting.print_error") as mock_err:
            action = await handle_token_expiry(exc, allow_prompt_login=False)

            assert action == "fail"
            mock_err.assert_called_once()
            assert "session has expired" in mock_err.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_token_expiry_prompt_login_for_config_token_interactive():
    from teardrop import AuthenticationError

    exc = AuthenticationError("Token has expired")

    with (
        patch("teardrop_cli.config.detect_credential_source") as mock_source,
        patch("teardrop_cli.config.get_siwe_key") as mock_siwe,
        patch("teardrop_cli.formatting.print_warning") as mock_warn,
        patch("teardrop_cli.formatting.print_error") as mock_err,
    ):
        mock_source.return_value = "config:token"
        mock_siwe.return_value = None

        action = await handle_token_expiry(exc, allow_prompt_login=True)

        assert action == "prompt_login"
        mock_err.assert_not_called()
        assert any(
            "Stored session has expired" in call.args[0] for call in mock_warn.call_args_list
        )


@pytest.mark.asyncio
async def test_handle_token_expiry_ignore_generic_auth_error():
    from teardrop import AuthenticationError

    exc = AuthenticationError("Invalid password")  # not an expiry error

    action = await handle_token_expiry(exc)
    assert action == "none"


@pytest.mark.asyncio
async def test_handle_unauthorized_status_as_expired_session():
    from teardrop import AuthenticationError

    exc = AuthenticationError("Unauthorized")
    exc.status_code = 401

    with (
        patch("teardrop_cli.config.detect_credential_source") as mock_source,
        patch("teardrop_cli.config.get_siwe_key", return_value=None),
        patch("teardrop_cli.formatting.print_warning") as mock_warn,
        patch("teardrop_cli.formatting.print_error") as mock_err,
    ):
        mock_source.return_value = "config:token"

        action = await handle_token_expiry(exc, allow_prompt_login=True)

        assert action == "prompt_login"
        mock_err.assert_not_called()
        assert any(
            "Stored session has expired" in call.args[0] for call in mock_warn.call_args_list
        )


@pytest.mark.asyncio
async def test_handle_token_expiry_retry_on_siwe_key():
    """When no email is available but a SIWE key is stored in keyring,
    handle_token_expiry should re-auth via _siwe_auth_async and return retry."""
    from teardrop import AuthenticationError

    exc = AuthenticationError("Token has expired")

    with (
        patch("teardrop_cli.config.detect_credential_source") as mock_source,
        patch("teardrop_cli.config.get_siwe_key") as mock_siwe,
        patch("teardrop_cli.commands.auth._siwe_auth_async") as mock_siwe_auth,
        patch("teardrop_cli.config.store_session") as mock_store,
    ):
        # Config-token source with SIWE key present.
        mock_source.return_value = "config:token"
        mock_siwe.return_value = ("0xdeadbeef" * 8, "0xABCDEF123456789")
        mock_siwe_auth.return_value = "new-jwt-token"

        with patch("teardrop_cli.formatting.print_warning") as mock_warn:
            action = await handle_token_expiry(exc)

            assert action == "retry"
            # Should have called _siwe_auth_async with the stored key
            mock_siwe_auth.assert_called_once()
            call_args = mock_siwe_auth.call_args[0]
            assert call_args[1] == ("0xdeadbeef" * 8)
            assert mock_warn.called
            # Should have stored the new JWT
            mock_store.assert_called_once_with(access_token="new-jwt-token")


@pytest.mark.asyncio
async def test_handle_token_expiry_env_api_key_skips_siwe():
    from teardrop import AuthenticationError

    exc = AuthenticationError("Token has expired")

    with (
        patch("teardrop_cli.config.detect_credential_source") as mock_source,
        patch("teardrop_cli.config.get_siwe_key") as mock_siwe,
        patch("teardrop_cli.commands.auth._siwe_auth_async") as mock_siwe_auth,
    ):
        mock_source.return_value = "env:api_key"
        mock_siwe.return_value = ("0xdeadbeef" * 8, "0xABCDEF123456789")

        with patch("teardrop_cli.formatting.print_error") as mock_err:
            action = await handle_token_expiry(exc)

            assert action == "fail"
            mock_siwe_auth.assert_not_called()
            assert "TEARDROP_API_KEY" in mock_err.call_args.kwargs["hint"]
