"""Minimal smoke test: verify a keyring backend is available on this platform.

Does NOT read or write any secrets.  Simply confirms that the ``keyring``
package is importable and that it can discover a backend with the expected
interface.  A missing or broken backend would cause ``auth login`` to silently
fall back to config-file-only credential storage, potentially leaving secrets
unprotected.
"""

from __future__ import annotations

import pytest


@pytest.mark.smoke
def test_keyring_backend_available() -> None:
    """A keyring backend must be detectable — verifies the package is functional."""
    try:
        import keyring
    except ImportError:
        pytest.skip("keyring not installed")

    backend = keyring.get_keyring()
    assert backend is not None, "keyring.get_keyring() returned None"
    assert hasattr(backend, "get_password"), (
        f"Backend {type(backend).__name__} is missing get_password"
    )
    assert hasattr(backend, "set_password"), (
        f"Backend {type(backend).__name__} is missing set_password"
    )
