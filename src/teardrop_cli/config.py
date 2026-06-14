"""Configuration and credential management for teardrop-cli.

Config file location: ``~/.teardrop/config.toml`` (created with mode 600).

Credential resolution order (highest priority first):
  1. ``TEARDROP_API_KEY`` env var (or legacy ``TEARDROP_TOKEN``) — static JWT, no auto-refresh
  2. ``TEARDROP_EMAIL`` + ``TEARDROP_SECRET`` env vars — auto-refresh via TokenManager
  3. ``TEARDROP_CLIENT_ID`` + ``TEARDROP_CLIENT_SECRET`` env vars — M2M
  4. Stored email + secret (keyring) or client credentials (keyring)
  5. Stored ``access_token`` in config file
  6. Legacy ``auth.token`` in config file (nested)
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
_KEYRING_SIWE_KEY = "siwe_private_key"
_KEYRING_SIWE_ADDRESS_KEY = "siwe_address"

DEFAULT_BASE_URL = "https://api.teardrop.dev"

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


def _is_secure_keyring() -> bool:
    """Check whether the active keyring backend is (likely) encrypted.

    Returns False for plaintext fallback backends that would store a
    private key in cleartext on disk.  Returns True when the backend
    cannot be inspected (e.g. macOS/Windows native keychains).
    """
    if not _keyring_available():
        return False
    import keyring

    def _is_insecure_backend(backend: Any) -> bool:
        cls = backend.__class__
        name = cls.__name__.lower()
        module = cls.__module__.lower()
        if "plaintext" in name or "uncrypted" in name:
            return True
        # keyring "fail" backend cannot store credentials.
        if module.startswith("keyring.backends.fail"):
            return True
        # keyrings.alt backends are fallback-oriented and may be plaintext.
        if module.startswith("keyrings.alt"):
            return True
        return "plaintext" in module or "uncrypted" in module

    try:
        backend = keyring.get_keyring()
    except Exception:
        return False

    if _is_insecure_backend(backend):
        return False

    # For chained backends, check all layers.
    return all(
        not _is_insecure_backend(sub)
        for sub in getattr(backend, "backends", [])
    )


def store_siwe_key(private_key: str, address: str) -> None:
    """Persist an Ethereum private key to the OS keyring.

    Refuses to write when the keyring backend is a plaintext fallback.
    The wallet address is stored alongside the key as a hint for
    ``get_siwe_key``.
    """
    from teardrop_cli.formatting import print_warning

    if not _is_secure_keyring():
        print_warning(
            "The active keyring backend is not encrypted. "
            "SIWE private key was NOT saved."
        )
        return
    import keyring

    try:
        keyring.set_password(_KEYRING_SERVICE, _KEYRING_SIWE_KEY, private_key)
        keyring.set_password(_KEYRING_SERVICE, _KEYRING_SIWE_ADDRESS_KEY, address)
    except Exception as exc:
        print_warning(f"Failed to save SIWE private key to keyring: {exc}")


def get_siwe_key() -> tuple[str, str] | None:
    """Return ``(private_key, address)`` from keyring, or None."""
    if not _keyring_available():
        return None
    import keyring

    try:
        pk = keyring.get_password(_KEYRING_SERVICE, _KEYRING_SIWE_KEY)
        addr = keyring.get_password(_KEYRING_SERVICE, _KEYRING_SIWE_ADDRESS_KEY)
    except Exception:
        return None
    if pk and addr:
        return pk, addr
    return None


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


def get_active_thread_id() -> str | None:
    """Return the active chat thread id from config, or None."""
    cfg = load_config()
    chat_cfg = cfg.get("chat")
    if isinstance(chat_cfg, dict):
        tid = chat_cfg.get("active_thread_id")
        if isinstance(tid, str) and tid.strip():
            return tid.strip()
    return None


def set_active_thread_id(tid: str | None) -> None:
    """Persist the active chat thread id to config."""
    cfg = load_config()
    chat_cfg = cfg.setdefault("chat", {})
    if tid is not None:
        chat_cfg["active_thread_id"] = tid
    else:
        chat_cfg.pop("active_thread_id", None)
    save_config(cfg)


def clear_active_thread_id() -> None:
    """Remove the active chat thread id from config."""
    set_active_thread_id(None)


def clear_credentials() -> None:
    """Remove all stored credentials from keyring and config file."""
    if _keyring_available():
        import keyring

        for key in (
            _KEYRING_EMAIL_KEY,
            _KEYRING_SECRET_KEY,
            _KEYRING_CLIENT_ID_KEY,
            _KEYRING_CLIENT_SECRET_KEY,
            _KEYRING_SIWE_KEY,
            _KEYRING_SIWE_ADDRESS_KEY,
        ):
            with contextlib.suppress(Exception):
                keyring.delete_password(_KEYRING_SERVICE, key)

    cfg = load_config()
    for key in ("access_token", "refresh_token", "email", "org_id", "client_id"):
        cfg.pop(key, None)
    cfg.pop("auth", None)  # legacy
    cfg.pop("chat", None)  # chat session state (active thread, etc.)
    save_config(cfg)


def init_config_file() -> Path:
    """Create ``~/.teardrop/config.toml`` if absent. Returns the path.

    Used by ``teardrop init``. Idempotent.
    """
    cfg_path = _config_file()
    if not cfg_path.exists():
        save_config({"api_url": DEFAULT_BASE_URL})
    return cfg_path


def has_existing_credentials() -> bool:
    """True if get_client() would likely succeed without prompting the user."""
    # Env vars (priorities 1-3)
    if os.environ.get("TEARDROP_API_KEY") or os.environ.get("TEARDROP_TOKEN"):
        return True
    if os.environ.get("TEARDROP_EMAIL") and os.environ.get("TEARDROP_SECRET"):
        return True
    if os.environ.get("TEARDROP_CLIENT_ID") and os.environ.get("TEARDROP_CLIENT_SECRET"):
        return True

    # Stored email + secret (keyring)
    if _keyring_available():
        import keyring

        email = keyring.get_password(_KEYRING_SERVICE, _KEYRING_EMAIL_KEY)
        secret = keyring.get_password(_KEYRING_SERVICE, _KEYRING_SECRET_KEY)
        if email and secret:
            return True
        cid = keyring.get_password(_KEYRING_SERVICE, _KEYRING_CLIENT_ID_KEY)
        csecret = keyring.get_password(_KEYRING_SERVICE, _KEYRING_CLIENT_SECRET_KEY)
        if cid and csecret:
            return True

    # Config file
    cfg = load_config()
    return bool(cfg.get("access_token") or cfg.get("auth", {}).get("token"))


def detect_credential_source() -> str | None:
    """Return a label describing which credential source is available, or None.

    Follows the same precedence order as :func:`has_existing_credentials`.
    Returns one of:
      ``"env:api_key"``, ``"env:email"``, ``"env:client"``,
      ``"keyring:email"``, ``"keyring:client"``,
      ``"config:token"``, ``"config:legacy_token"``, or ``None``.

    The return value is a *label only* — never a secret or credential value.
    """
    # Env vars (priorities 1-3)
    if os.environ.get("TEARDROP_API_KEY") or os.environ.get("TEARDROP_TOKEN"):
        return "env:api_key"
    if os.environ.get("TEARDROP_EMAIL") and os.environ.get("TEARDROP_SECRET"):
        return "env:email"
    if os.environ.get("TEARDROP_CLIENT_ID") and os.environ.get("TEARDROP_CLIENT_SECRET"):
        return "env:client"

    # Stored email + secret (keyring)
    if _keyring_available():
        import keyring

        email = keyring.get_password(_KEYRING_SERVICE, _KEYRING_EMAIL_KEY)
        secret = keyring.get_password(_KEYRING_SERVICE, _KEYRING_SECRET_KEY)
        if email and secret:
            return "keyring:email"
        cid = keyring.get_password(_KEYRING_SERVICE, _KEYRING_CLIENT_ID_KEY)
        csecret = keyring.get_password(_KEYRING_SERVICE, _KEYRING_CLIENT_SECRET_KEY)
        if cid and csecret:
            return "keyring:client"

    # Config file
    cfg = load_config()
    if cfg.get("access_token"):
        return "config:token"
    if cfg.get("auth", {}).get("token"):
        return "config:legacy_token"

    return None


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

    # 4. Stored email + secret (keyring)
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

    # 5. Stored access_token
    cfg = load_config()
    if token := cfg.get("access_token"):
        return AsyncTeardropClient(url, token=token)
    # Legacy nested location
    if token := cfg.get("auth", {}).get("token"):
        return AsyncTeardropClient(url, token=token)

    if not require_auth:
        return AsyncTeardropClient(url)

    print_error(
        "Not authenticated.",
        hint="Run [bold]teardrop auth login[/bold] to sign in, or [bold]teardrop auth signup[/bold] to create an account.",
    )
    raise SystemExit(1)


def extract_session_tokens(client) -> tuple[str | None, str | None]:
    """Pull access + refresh tokens from a client's TokenManager (best effort)."""
    tm = getattr(client, "_token_manager", None)
    if tm is None:
        return None, None
    return getattr(tm, "_token", None), getattr(tm, "_refresh_token", None)
