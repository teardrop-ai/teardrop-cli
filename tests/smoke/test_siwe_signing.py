"""Smoke tests for the SIWE (Sign-In-With-Ethereum) cryptographic primitive.

Verifies that ``eth_account`` can sign and recover a SIWE-format message on
this platform, without requiring a network connection or a real Teardrop API.
This is valuable because the crypto primitive is a platform dependency; a
broken ``eth_account`` installation would silently fail only at login time.
"""

from __future__ import annotations

import pytest


@pytest.mark.smoke
def test_siwe_sign_and_recover() -> None:
    """Generate an ephemeral keypair, sign a SIWE message, recover the signer.

    Mirrors the exact signing logic used in
    ``teardrop_cli.commands.auth._login_siwe``.
    """
    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct
    except ImportError:
        pytest.skip("eth-account not installed")

    account = Account.create()
    wallet_address = account.address

    # Reproduce the message format from _login_siwe()
    domain = "api.teardrop.dev"
    nonce = "testNonce0xABC123"
    message = (
        f"{domain} wants you to sign in with your Ethereum account:\n"
        f"{wallet_address}\n\n"
        f"Sign in to Teardrop\n\n"
        f"URI: https://api.teardrop.dev\n"
        f"Version: 1\n"
        f"Chain ID: 1\n"
        f"Nonce: {nonce}\n"
        f"Issued At: 2026-04-26T00:00:00Z"
    )

    signable = encode_defunct(text=message)
    signed = account.sign_message(signable)
    recovered = Account.recover_message(signable, signature=signed.signature)

    assert recovered == wallet_address


@pytest.mark.smoke
def test_siwe_missing_env_exits_nonzero(subprocess_cli) -> None:
    """``auth login --siwe`` without TEARDROP_SIWE_PRIVATE_KEY exits 1 with hint."""
    # subprocess_cli already strips TEARDROP_SIWE_PRIVATE_KEY from the env
    result = subprocess_cli("auth", "login", "--siwe")
    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert "TEARDROP_SIWE_PRIVATE_KEY" in combined
