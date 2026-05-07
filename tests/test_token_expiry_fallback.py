from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from teardrop_cli.formatting import handle_token_expiry


@pytest.mark.asyncio
async def test_handle_token_expiry_retry_on_email_present():
    from teardrop import AuthenticationError
    
    exc = AuthenticationError("Token has expired")
    
    with patch("teardrop_cli.config.load_config") as mock_load:
        with patch("teardrop_cli.config.has_existing_credentials") as mock_has:
            with patch("teardrop_cli.config._keyring_available") as mock_key_avail:
                with patch("keyring.get_password") as mock_pass:
                    # Simulate email credentials present
                    mock_has.return_value = True
                    mock_key_avail.return_value = True
                    mock_load.return_value = {"email": "test@example.com"}
                    mock_pass.return_value = "secret"
                    
                    with patch("teardrop_cli.formatting.print_warning") as mock_warn:
                        should_retry = await handle_token_expiry(exc)
                        
                        assert should_retry is True
                        mock_warn.assert_called_once_with("Session expired. Attempting auto-refresh...")


@pytest.mark.asyncio
async def test_handle_token_expiry_fail_on_no_email():
    from teardrop import AuthenticationError
    
    exc = AuthenticationError("Token has expired")
    
    with patch("teardrop_cli.config.load_config") as mock_load:
        with patch("teardrop_cli.config.has_existing_credentials") as mock_has:
            with patch("teardrop_cli.config._keyring_available") as mock_key_avail:
                # Only static token, no email
                mock_has.return_value = True
                mock_key_avail.return_value = False
                mock_load.return_value = {"access_token": "some-token"} # no email key
                
                with patch("teardrop_cli.formatting.print_error") as mock_err:
                    with pytest.raises(SystemExit):
                        await handle_token_expiry(exc)
                    
                    mock_err.assert_called_once()
                    assert "session has expired" in mock_err.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_token_expiry_ignore_generic_auth_error():
    from teardrop import AuthenticationError
    
    exc = AuthenticationError("Invalid password") # not an expiry error
    
    should_retry = await handle_token_expiry(exc)
    assert should_retry is False
