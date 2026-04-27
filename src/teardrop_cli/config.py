"""Configuration and credential management for teardrop-cli.

Config file location: ``~/.teardrop/config.toml`` (created with mode 600).

Credential resolution order (highest priority first):
  1. ``TEARDROP_API_KEY`` env var (or legacy ``TEARDROP_TOKEN``) — static JWT, no auto-refresh
  2. ``TEARDROP_EMAIL`` + ``TEARDROP_SECRET`` env vars — auto-refresh via TokenManager
  3. ``TEARDROP_CLIENT_ID`` + ``TEARDROP_CLIENT_SECRET`` env vars — M2M
  4. Stored access_token in config file (with optional refresh_token)
  5. Stored email + secret (keyring) or client credentials (keyring)
"""

from __future__ import annotations

import contextlib
import os
import stat
import tomllib
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Keyring service name
# ---------------------------------------------------------------------------
_KEYRING_SERVICE = "teardrop-cli"
_KEYRING_EMAIL_KEY = "email"
_KEYRING_SECRET_KEY = "secret"
_KEYRING_CLIENT_ID_KEY = "client_id"
_KEYRING_CLIENT_SECRET_KEY = "client_secret"

DEFAULT_BASE_URL = "https://api.teardrop.ai"

# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------


def get_config_dir() -> Path:
    """Return ``~/.teardrop/``, creating it (mode 700) if needed."""
    path = Path.home() / ".teardrop"
    path.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(NotImplementedError, OSError):
        path.chmod(stat.S_IRWXU)  # 0o700
    _maybe_migrate_legacy_config(path)
    return path


def _config_file() -> Path:
    return get_config_dir() / "config.toml"


def _maybe_migrate_legacy_config(new_dir: Path) -> None:
    """One-time copy from old XDG path to ``~/.teardrop/`` if new file absent."""
    new_file = new_dir / "config.toml"
    if new_file.exists():
        return
    try:
        import platformdirs
    except ImportError:
        return
    legacy = Path(platformdirs.user_config_dir("teardrop", appauthor=False)) / "config.toml"
    if legacy.exists() and legacy != new_file:
        with contextlib.suppress(OSError):
            new_file.write_text(legacy.read_text(encoding="utf-8"), encoding="utf-8")
            with contextlib.suppress(NotImplementedError, OSError):
                new_file.chmod(stat.S_IRUSR | stat.S_IWUSR)


# ---------------------------------------------------------------------------
# Config TOML helpers
# ---------------------------------------------------------------------------


def load_config() -> dict[str, Any]:
    """Load ``config.toml``; return empty dict if it doesn't exist."""
    cfg_path = _config_file()
    if not cfg_path.exists():
        return {}
    try:
        return tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(data: dict[str, Any]) -> None:
    """Persist *data* to ``config.toml`` with owner-only read/write permissions."""
    import tomli_w

    cfg_path = _config_file()
    cfg_path.write_text(tomli_w.dumps(data), encoding="utf-8")
    with contextlib.suppress(NotImplementedError, OSError):
        cfg_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600


# ---------------------------------------------------------------------------
# Base URL
# ---------------------------------------------------------------------------


def get_base_url() -> str:
    """Return the API base URL, respecting env var and config overrides."""
    if url := os.environ.get("TEARDROP_BASE_URL"):
        return url.rstrip("/")
    cfg = load_config()
    if url := cfg.get("api_url"):
        return str(url).rstrip("/")
    # Legacy nested location
    if url := cfg.get("api", {}).get("base_url"):
        return str(url).rstrip("/")
    return DEFAULT_BASE_URL


def set_api_url(url: str) -> None:
    """Persist ``api_url`` to the config file."""
    cfg = load_config()
    cfg["api_url"] = url.rstrip("/")
    save_config(cfg)


# ---------------------------------------------------------------------------
# Credential storage
# ---------------------------------------------------------------------------


def _keyring_available() -> bool:
    try:
        import keyring  # noqa: F401

        return True
    except ImportError:
        return False


def store_session(
    *,
    access_token: str | None,
    refresh_token: str | None = None,
    email: str | None = None,
    org_id: str | None = None,
) -> None:
    """Persist the result of a successful login to the config file.

    Writes ``access_token``, ``refresh_token``, ``email``, and ``org_id`` to
    ``~/.teardrop/config.toml``. None values are not written. The file is
    chmod'd 600 immediately.
    """
    cfg = load_config()
    if access_token is not None:
        cfg["access_token"] = access_token
    if refresh_token is not None:
        cfg["refresh_token"] = refresh_token
    if email is not None:
        cfg["email"] = email
    if org_id is not None:
        cfg["org_id"] = org_id
    save_config(cfg)


def store_token(token: str) -> None:
    """Persist a JWT token to the config file as ``access_token``."""
    cfg = load_config()
    cfg["access_token"] = token
    save_config(cfg)


def store_email_credentials(email: str, secret: str) -> None:
    """Persist email + secret. Email goes in config; secret goes in keyring only."""
    if _keyring_available():
        import keyring

        with contextlib.suppress(Exception):
            keyring.set_password(_KEYRING_SERVICE, _KEYRING_EMAIL_KEY, email)
            keyring.set_password(_KEYRING_SERVICE, _KEYRING_SECRET_KEY, secret)
    cfg = load_config()
    cfg["email"] = email
    save_config(cfg)


def store_client_credentials(client_id: str, client_secret: str) -> None:
    """Persist M2M client credentials. Secret goes in keyring only."""
    if _keyring_available():
        import keyring

        with contextlib.suppress(Exception):
            keyring.set_password(_KEYRING_SERVICE, _KEYRING_CLIENT_ID_KEY, client_id)
            keyring.set_password(
                _KEYRING_SERVICE, _KEYRING_CLIENT_SECRET_KEY, client_secret
            )
    cfg = load_config()
    cfg["client_id"] = client_id
    save_config(cfg)


def get_refresh_token() -> str | None:
    """Return the stored refresh token, or None."""
    return load_config().get("refresh_token")


def clear_credentials() -> None:
    """Remove all stored credentials from keyring and config file."""
    if _keyring_available():
        import keyring

        for key in (
            _KEYRING_EMAIL_KEY,
            _KEYRING_SECRET_KEY,
            _KEYRING_CLIENT_ID_KEY,
            _KEYRING_CLIENT_SECRET_KEY,
        ):
            with contextlib.suppress(Exception):
                keyring.delete_password(_KEYRING_SERVICE, key)

    cfg = load_config()
    for key in ("access_token", "refresh_token", "email", "org_id", "client_id"):
        cfg.pop(key, None)
    cfg.pop("auth", None)  # legacy
    save_config(cfg)


def init_config_file() -> Path:
    """Create ``~/.teardrop/config.toml`` if absent. Returns the path.

    Used by ``teardrop init``. Idempotent.
    """
    cfg_path = _config_file()
    if not cfg_path.exists():
        save_config({"api_url": DEFAULT_BASE_URL})
    return cfg_path


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------


def get_client(base_url: str | None = None, *, require_auth: bool = True):
    """Build and return an ``AsyncTeardropClient`` from stored credentials.

    When ``require_auth`` is False, returns an unauthenticated client if no
    credentials are found (used by public commands like ``marketplace list``
    and ``models benchmarks``).

    Raises ``SystemExit`` with a friendly message when ``require_auth`` is
    True and no credentials are available.
    """
    from teardrop import AsyncTeardropClient

    from teardrop_cli.formatting import print_error

    url = base_url or get_base_url()

    # 1. Static API key (TEARDROP_API_KEY preferred; TEARDROP_TOKEN legacy alias)
    if token := (os.environ.get("TEARDROP_API_KEY") or os.environ.get("TEARDROP_TOKEN")):
        return AsyncTeardropClient(url, token=token)

    # 2. Email + secret env vars
    email_env = os.environ.get("TEARDROP_EMAIL")
    secret_env = os.environ.get("TEARDROP_SECRET")
    if email_env and secret_env:
        return AsyncTeardropClient(url, email=email_env, secret=secret_env)

    # 3. Client credentials env vars
    cid_env = os.environ.get("TEARDROP_CLIENT_ID")
    csecret_env = os.environ.get("TEARDROP_CLIENT_SECRET")
    if cid_env and csecret_env:
        return AsyncTeardropClient(url, client_id=cid_env, client_secret=csecret_env)

    # 4. Stored access_token
    cfg = load_config()
    if token := cfg.get("access_token"):
        return AsyncTeardropClient(url, token=token)
    # Legacy nested location
    if token := cfg.get("auth", {}).get("token"):
        return AsyncTeardropClient(url, token=token)

    # 5. Stored email + secret (keyring)
    if _keyring_available():
        import keyring

        email = keyring.get_password(_KEYRING_SERVICE, _KEYRING_EMAIL_KEY)
        secret = keyring.get_password(_KEYRING_SERVICE, _KEYRING_SECRET_KEY)
        if email and secret:
            return AsyncTeardropClient(url, email=email, secret=secret)

        cid = keyring.get_password(_KEYRING_SERVICE, _KEYRING_CLIENT_ID_KEY)
        csecret = keyring.get_password(_KEYRING_SERVICE, _KEYRING_CLIENT_SECRET_KEY)
        if cid and csecret:
            return AsyncTeardropClient(url, client_id=cid, client_secret=csecret)

    if not require_auth:
        return AsyncTeardropClient(url)

    print_error(
        "Not authenticated.",
        hint="Run [bold]teardrop auth login[/bold] to sign in.",
    )
    raise SystemExit(1)


def extract_session_tokens(client) -> tuple[str | None, str | None]:
    """Pull access + refresh tokens from a client's TokenManager (best effort)."""
    tm = getattr(client, "_token_manager", None)
    if tm is None:
        return None, None
    return getattr(tm, "_token", None), getattr(tm, "_refresh_token", None)
