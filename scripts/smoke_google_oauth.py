#!/usr/bin/env python3
"""Smoke: Google OAuth module + PWA routes without live Google credentials."""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from core.integrations import google_oauth

    st = google_oauth.status()
    assert st.get("ok") is True
    assert "configured" in st
    assert "connected" in st
    print("status:", json.dumps(st, indent=2))

    url, err = google_oauth.build_auth_url(
        "http://127.0.0.1:8765/api/google/callback"
    )
    if st.get("configured"):
        assert url and "accounts.google.com" in url and err is None
        print("auth_url ok (credentials present)")
    else:
        assert url is None and err
        print("auth_url correctly blocked:", err[:80])

    # Handler import sanity
    import scripts.serve_pwa as serve  # noqa: F401

    print("serve_pwa import ok")
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
