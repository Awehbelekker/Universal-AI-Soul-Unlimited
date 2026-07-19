#!/usr/bin/env python3
"""
One-time Google OAuth setup for Universal Soul.

Creates/updates .env with GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET and prints
the redirect URIs to paste into Google Cloud Console.

After this, restart serve_pwa.py and tap "Sign in with Google" in the PWA —
Google will ask you to log in, approve permissions, then auto-link the account.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
EXAMPLE = ROOT / ".env.example"

sys.path.insert(0, str(ROOT))


def _lan_ips() -> list[str]:
    ips: list[str] = []
    try:
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            ips.append(ip)
    except Exception:
        pass
    return ips


def _upsert_env(cid: str, secret: str) -> None:
    lines: list[str] = []
    if ENV_PATH.is_file():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    elif EXAMPLE.is_file():
        lines = EXAMPLE.read_text(encoding="utf-8").splitlines()

    def set_key(key: str, value: str) -> None:
        nonlocal lines
        pat = re.compile(rf"^{re.escape(key)}=.*$")
        found = False
        out = []
        for line in lines:
            if pat.match(line):
                out.append(f"{key}={value}")
                found = True
            else:
                out.append(line)
        if not found:
            out.append(f"{key}={value}")
        lines = out

    set_key("GOOGLE_CLIENT_ID", cid)
    set_key("GOOGLE_CLIENT_SECRET", secret)
    ENV_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    from core.integrations import google_oauth

    print("=== Universal Soul · Google OAuth setup ===\n")
    print("1. Open https://console.cloud.google.com/apis/credentials")
    print("2. Create OAuth client → Application type: Web application")
    print("3. Under Authorized redirect URIs, add ALL of these:\n")
    for uri in google_oauth.suggested_redirect_uris(8765, _lan_ips()):
        print(f"   {uri}")
    print("\n4. Enable Gmail API:")
    print("   https://console.cloud.google.com/apis/library/gmail.googleapis.com")
    print("5. OAuth consent screen: add your Google account as a Test user")
    print("   (while the app is in Testing mode)\n")

    cid = input("Paste Client ID: ").strip()
    secret = input("Paste Client Secret: ").strip()
    if not cid or not secret:
        print("Aborted — both values are required.", file=sys.stderr)
        return 1

    _upsert_env(cid, secret)
    print(f"\nSaved to {ENV_PATH}")
    print("Restart: python scripts/serve_pwa.py --host 0.0.0.0 --port 8765")
    print("Then tap Sign in with Google → login → approve → auto-linked.\n")

    st = google_oauth.status()
    print("Status:", "configured" if st.get("configured") else st.get("config_error"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
