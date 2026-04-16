"""Configuration and credential management for teardrop-cli.

Credential resolution order (highest priority first):
  1. TEARDROP_TOKEN env var (static JWT, for CI/CD)
  2. TEARDROP_EMAIL + TEARDROP_SECRET env vars
  3. TEARDROP_CLIENT_ID + TEARDROP_CLIENT_SECRET env vars
  4. System keyring
  5. Config file (~/.config/teardrop/config.toml)

Config/data directories follow XDG / platformdirs conventions.
"""

from __future__ import annotations

import os
import stat
import tomllib
from pathlib import Path
from typing import Any

import platformdirs

# ---------------------------------------------------------------------------
# Keyring service name
# ---------------------------------------------------------------------------
_KEYRING_SERVICE = "teardrop-cli"
_KEYRING_JWT_KEY = "jwt_token"
_KEYRING_EMAIL_KEY = "email"
_KEYRING_SECRET_KEY = "secret"
_KEYRING_CLIENT_ID_KEY = "client_id"
_KEYRING_CLIENT_SECRET_KEY = "client_secret"

# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------


def get_config_dir() -> Path:
    """Return the platform-appropriate config directory, creating it if needed."""
    path = Path(platformdirs.user_config_dir("teardrop", appauthor=False))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _config_file() -> Path:
    return get_config_dir() / "config.toml"


# ---------------------------------------------------------------------------
# Config TOML helpers
# ---------------------------------------------------------------------------


def load_config() -> dict[str, Any]:
    """Load config.toml; return empty dict if it doesn't exist."""
    cfg_path = _config_file()
    if not cfg_path.exists():
        return {}
    try:
        return tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(data: dict[str, Any]) -> None:
    """Persist *data* to config.toml with owner-only read/write permissions."""
    import tomli_w  # lazy import — only needed on writes

    cfg_path = _config_file()
    cfg_path.write_text(tomli_w.dumps(data), encoding="utf-8")
    # Restrict permissions on POSIX (0o600); Windows ignores this silently.
    try:
        cfg_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except NotImplementedError:
        pass


# ---------------------------------------------------------------------------
# Base URL
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "https://api.teardrop.dev"


def get_base_url() -> str:
    """Return the API base URL, respecting env var and config overrides."""
    if url := os.environ.get("TEARDROP_BASE_URL"):
        return url.rstrip("/")
    cfg = load_config()
    if url := cfg.get("api", {}).get("base_url"):
        return url.rstrip("/")
    return DEFAULT_BASE_URL


# ---------------------------------------------------------------------------
# Credential storage
# ---------------------------------------------------------------------------


def _keyring_available() -> bool:
    try:
        import keyring  # noqa: F401

        return True
    except ImportError:
        return False


def store_token(token: str) -> None:
    """Persist a JWT token (keyring first, config file fallback)."""
    if _keyring_available():
        import keyring

        keyring.set_password(_KEYRING_SERVICE, _KEYRING_JWT_KEY, token)
        return

    cfg = load_config()
    cfg.setdefault("auth", {})["token"] = token
    save_config(cfg)


def store_email_credentials(email: str, secret: str) -> None:
    """Persist email + secret (keyring first, config file fallback).

    Note: the secret (password) is stored in the keyring only. The config
    file stores the email as plain text but never the secret.
    """
    if _keyring_available():
        import keyring

        keyring.set_password(_KEYRING_SERVICE, _KEYRING_EMAIL_KEY, email)
        keyring.set_password(_KEYRING_SERVICE, _KEYRING_SECRET_KEY, secret)
    # Always store the email in the config so we can show it in whoami
    cfg = load_config()
    cfg.setdefault("auth", {})["method"] = "email"
    cfg["auth"]["email"] = email
    save_config(cfg)


def store_client_credentials(client_id: str, client_secret: str) -> None:
    """Persist M2M client credentials."""
    if _keyring_available():
        import keyring

        keyring.set_password(_KEYRING_SERVICE, _KEYRING_CLIENT_ID_KEY, client_id)
        keyring.set_password(_KEYRING_SERVICE, _KEYRING_CLIENT_SECRET_KEY, client_secret)

    cfg = load_config()
    cfg.setdefault("auth", {})["method"] = "client_credentials"
    # Store client_id in config (not secret), mirroring email pattern
    cfg["auth"]["client_id"] = client_id
    save_config(cfg)


def clear_credentials() -> None:
    """Remove all stored credentials from keyring and config file."""
    if _keyring_available():
        import keyring

        for key in (
            _KEYRING_JWT_KEY,
            _KEYRING_EMAIL_KEY,
            _KEYRING_SECRET_KEY,
            _KEYRING_CLIENT_ID_KEY,
            _KEYRING_CLIENT_SECRET_KEY,
        ):
            try:
                keyring.delete_password(_KEYRING_SERVICE, key)
            except Exception:
                pass

    cfg = load_config()
    cfg.pop("auth", None)
    save_config(cfg)


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------


def get_client(base_url: str | None = None):
    """Build and return an ``AsyncTeardropClient`` from stored credentials.

    Raises ``SystemExit`` with a friendly message if no credentials are found.
    """
    from teardrop import AsyncTeardropClient

    from teardrop_cli.formatting import print_error

    url = base_url or get_base_url()

    # 1. Static token env var
    if token := os.environ.get("TEARDROP_TOKEN"):
        return AsyncTeardropClient(url, token=token)

    # 2. Email + secret env vars
    email_env = os.environ.get("TEARDROP_EMAIL")
    secret_env = os.environ.get("TEARDROP_SECRET")
    if email_env and secret_env:
        return AsyncTeardropClient(url, email=email_env, secret=secret_env)

    # 3. Client credentials env vars
    client_id_env = os.environ.get("TEARDROP_CLIENT_ID")
    client_secret_env = os.environ.get("TEARDROP_CLIENT_SECRET")
    if client_id_env and client_secret_env:
        return AsyncTeardropClient(url, client_id=client_id_env, client_secret=client_secret_env)

    # 4 & 5. Keyring / config file
    if _keyring_available():
        import keyring

        # Static JWT stored after login
        if token := keyring.get_password(_KEYRING_SERVICE, _KEYRING_JWT_KEY):
            return AsyncTeardropClient(url, token=token)

        # Email credentials
        email = keyring.get_password(_KEYRING_SERVICE, _KEYRING_EMAIL_KEY)
        secret = keyring.get_password(_KEYRING_SERVICE, _KEYRING_SECRET_KEY)
        if email and secret:
            return AsyncTeardropClient(url, email=email, secret=secret)

        # Client credentials
        cid = keyring.get_password(_KEYRING_SERVICE, _KEYRING_CLIENT_ID_KEY)
        csecret = keyring.get_password(_KEYRING_SERVICE, _KEYRING_CLIENT_SECRET_KEY)
        if cid and csecret:
            return AsyncTeardropClient(url, client_id=cid, client_secret=csecret)

    # Config file fallback (static token only)
    cfg = load_config()
    if token := cfg.get("auth", {}).get("token"):
        return AsyncTeardropClient(url, token=token)

    print_error(
        "Not authenticated.",
        hint="Run [bold]teardrop auth login[/bold] to sign in.",
    )
    raise SystemExit(1)
