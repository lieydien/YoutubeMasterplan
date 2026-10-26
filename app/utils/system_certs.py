"""Trust the operating system's root certificates in addition to certifi's bundle.

edge-tts, requests and httpx load only certifi's CA bundle. Behind a TLS-inspecting proxy such as
Zscaler, the proxy's root certificate is trusted by the OS but is not in certifi, so every HTTPS
call fails with CERTIFICATE_VERIFY_FAILED. This adds the OS store whenever a context loads a CA
bundle. It only adds trust anchors; certificate and hostname verification stay enabled.

Set MPT_DISABLE_SYSTEM_CERTS=1 to turn it off.
"""

import os
import ssl
import threading

DISABLE_ENV = "MPT_DISABLE_SYSTEM_CERTS"

_original_load_verify_locations = ssl.SSLContext.load_verify_locations
# On Windows load_default_certs feeds the system store back through load_verify_locations.
_state = threading.local()


def _load_verify_locations_with_system_store(self, *args, **kwargs):
    _original_load_verify_locations(self, *args, **kwargs)
    if getattr(_state, "loading", False):
        return
    _state.loading = True
    try:
        self.load_default_certs(ssl.Purpose.SERVER_AUTH)
    except Exception:
        # The bundle that was asked for is already loaded; the system store is a bonus.
        pass
    finally:
        _state.loading = False


def install() -> bool:
    """Patch ssl.SSLContext once. Returns True when the system store is in use."""
    if os.environ.get(DISABLE_ENV, "").strip().lower() in {"1", "true", "yes"}:
        return False
    ssl.SSLContext.load_verify_locations = _load_verify_locations_with_system_store
    return True


def uninstall() -> None:
    ssl.SSLContext.load_verify_locations = _original_load_verify_locations
