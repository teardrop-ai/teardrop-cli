from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from teardrop_cli import config


@pytest.fixture
def mock_keyring():
    with patch("keyring.get_password") as m:
        yield m


@pytest.fixture
def mock_load_config():
    with patch("teardrop_cli.config.load_config") as m:
        m.return_value = {}
        yield m


@pytest.fixture
def clean_env():
    # Remove relevant env vars to ensure we test config/keyring priority
    env_vars = [
        "TEARDROP_API_KEY",
        "TEARDROP_TOKEN",
        "TEARDROP_EMAIL",
        "TEARDROP_SECRET",
        "TEARDROP_CLIENT_ID",
        "TEARDROP_CLIENT_SECRET",
    ]
    old_values = {k: os.environ.get(k) for k in env_vars}
    for k in env_vars:
        if k in os.environ:
            del os.environ[k]
    yield
    for k, v in old_values.items():
        if v is not None:
            os.environ[k] = v


def test_priority_email_over_token(mock_keyring, mock_load_config, clean_env):
    # BOTH are present
    # Token in config
    mock_load_config.return_value = {"access_token": "stale-token", "email": "test@example.com"}
    
    # Email/Secret in keyring
    def keyring_side_effect(service, key):
        if key == config._KEYRING_EMAIL_KEY:
            return "test@example.com"
        if key == config._KEYRING_SECRET_KEY:
            return "password123"
        return None
    
    mock_keyring.side_effect = keyring_side_effect
    
    with patch("teardrop.AsyncTeardropClient") as mock_client_cls:
        config.get_client()
        
        # Verify it was called with email/secret (Priority 4), not token (Priority 5)
        # Note: Priority 4 is now keyring/email+secret
        mock_client_cls.assert_called_once()
        args, kwargs = mock_client_cls.call_args
        assert kwargs.get("email") == "test@example.com"
        assert kwargs.get("secret") == "password123"
        assert "token" not in kwargs


def test_fallback_to_token_if_no_email(mock_keyring, mock_load_config, clean_env):
    # Only token is present
    mock_load_config.return_value = {"access_token": "valid-token"}
    mock_keyring.return_value = None
    
    with patch("teardrop.AsyncTeardropClient") as mock_client_cls:
        config.get_client()
        
        mock_client_cls.assert_called_once()
        args, kwargs = mock_client_cls.call_args
        assert kwargs.get("token") == "valid-token"
        assert "email" not in kwargs


def test_env_vars_still_highest_priority(mock_keyring, mock_load_config):
    # Env var present alongside config/keyring
    os.environ["TEARDROP_API_KEY"] = "env-token"
    mock_load_config.return_value = {"access_token": "config-token"}
    
    try:
        with patch("teardrop.AsyncTeardropClient") as mock_client_cls:
            config.get_client()
            
            mock_client_cls.assert_called_once()
            args, kwargs = mock_client_cls.call_args
            assert kwargs.get("token") == "env-token"
    finally:
        del os.environ["TEARDROP_API_KEY"]


class TestDetectCredentialSource:
    """Tests for config.detect_credential_source()."""

    def test_env_api_key(self, mock_keyring, mock_load_config, clean_env):
        os.environ["TEARDROP_API_KEY"] = "tok-xyz"
        assert config.detect_credential_source() == "env:api_key"

    def test_env_token_alias(self, mock_keyring, mock_load_config, clean_env):
        os.environ["TEARDROP_TOKEN"] = "tok-xyz"
        assert config.detect_credential_source() == "env:api_key"

    def test_env_email(self, mock_keyring, mock_load_config, clean_env):
        os.environ["TEARDROP_EMAIL"] = "u@e.com"
        os.environ["TEARDROP_SECRET"] = "s3kr1t"
        assert config.detect_credential_source() == "env:email"

    def test_env_client(self, mock_keyring, mock_load_config, clean_env):
        os.environ["TEARDROP_CLIENT_ID"] = "cid"
        os.environ["TEARDROP_CLIENT_SECRET"] = "csecret"
        assert config.detect_credential_source() == "env:client"

    def test_keyring_email(self, mock_keyring, mock_load_config, clean_env):
        def side_effect(service, key):
            if key == config._KEYRING_EMAIL_KEY:
                return "u@e.com"
            if key == config._KEYRING_SECRET_KEY:
                return "s3kr1t"
            return None
        mock_keyring.side_effect = side_effect
        assert config.detect_credential_source() == "keyring:email"

    def test_keyring_client(self, mock_keyring, mock_load_config, clean_env):
        def side_effect(service, key):
            if key == config._KEYRING_CLIENT_ID_KEY:
                return "cid"
            if key == config._KEYRING_CLIENT_SECRET_KEY:
                return "csecret"
            return None
        mock_keyring.side_effect = side_effect
        assert config.detect_credential_source() == "keyring:client"

    def test_config_token(self, mock_keyring, mock_load_config, clean_env):
        mock_load_config.return_value = {"access_token": "tok-abc"}
        mock_keyring.return_value = None
        assert config.detect_credential_source() == "config:token"

    def test_config_legacy_token(self, mock_keyring, mock_load_config, clean_env):
        mock_load_config.return_value = {"auth": {"token": "tok-legacy"}}
        mock_keyring.return_value = None
        assert config.detect_credential_source() == "config:legacy_token"

    def test_none(self, mock_keyring, mock_load_config, clean_env):
        mock_keyring.return_value = None
        mock_load_config.return_value = {}
        assert config.detect_credential_source() is None
