"""Supply missing macOS Python CA roots without bypassing TLS verification."""
from __future__ import annotations

import importlib
import os
import ssl
import sys
from pathlib import Path


def mac_certificate_bundle(system=None):
    """Return a fallback CA bundle only when Python has no default trust roots.

    Existing system trust and explicit certificate environment settings are kept.
    pip's vendored bundle also works in older source installs without certifi.
    """
    if (system or sys.platform) != "darwin":
        return None
    if "SSL_CERT_FILE" in os.environ or "SSL_CERT_DIR" in os.environ:
        return None
    if ssl.create_default_context().cert_store_stats().get("x509_ca", 0):
        return None
    for name in ("certifi", "pip._vendor.certifi"):
        try:
            bundle = Path(importlib.import_module(name).where()).resolve()
        except ImportError:
            continue
        if not bundle.is_file():
            continue
        # Parse the bundle and keep hostname/chain verification enabled.
        context = ssl.create_default_context(cafile=str(bundle))
        if context.cert_store_stats().get("x509_ca", 0):
            return str(bundle)
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    raise RuntimeError(
        f"Python has no trusted HTTPS certificates. Close SoundShredder and run "
        f"/Applications/Python {version}/Install Certificates.command, then reopen the app. "
        "Do not disable certificate verification."
    )


def configure_macos_certificates():
    bundle = mac_certificate_bundle()
    if bundle:
        # Inherited by the audio job process and urllib's model downloads.
        os.environ["SSL_CERT_FILE"] = bundle
    return bundle


if __name__ == "__main__":
    try:
        print(mac_certificate_bundle() or "")
    except (OSError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc
