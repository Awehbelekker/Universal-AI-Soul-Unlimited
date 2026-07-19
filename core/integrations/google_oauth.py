"""
Google OAuth 2.0 (authorization code) + Gmail draft/send for Universal Soul.

Credentials stay on the PC (env / data files). The PWA only triggers the flow.
"""

from __future__ import annotations

import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
TOKEN_PATH = DATA / "google_tokens.json"
CLIENT_PATH = DATA / "google_client.json"
PENDING_PATH = DATA / "google_oauth_pending.json"
ENV_PATH = ROOT / ".env"

SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.compose",
    # Files created/opened by Soul only (safer than full Drive; still needs Test users)
    "https://www.googleapis.com/auth/drive.file",
]

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
DRIVE_API = "https://www.googleapis.com/drive/v3"

_STATE_TTL_SEC = 600


def _load_pending() -> Dict[str, Dict[str, Any]]:
    if not PENDING_PATH.is_file():
        return {}
    try:
        data = json.loads(PENDING_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_pending(pending: Dict[str, Dict[str, Any]]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    PENDING_PATH.write_text(json.dumps(pending, indent=2), encoding="utf-8")


def _purge_states() -> None:
    now = time.time()
    pending = _load_pending()
    dead = [k for k, v in pending.items() if now - float(v.get("created") or 0) > _STATE_TTL_SEC]
    for k in dead:
        pending.pop(k, None)
    _save_pending(pending)


def load_dotenv(path: Path = ENV_PATH) -> None:
    """Load KEY=VALUE from .env into os.environ if not already set."""
    import os

    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def get_client() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (client_id, client_secret, error_message)."""
    import os

    load_dotenv()
    cid = (os.environ.get("GOOGLE_CLIENT_ID") or "").strip()
    secret = (os.environ.get("GOOGLE_CLIENT_SECRET") or "").strip()
    if (not cid or not secret) and CLIENT_PATH.is_file():
        try:
            data = json.loads(CLIENT_PATH.read_text(encoding="utf-8"))
            web = data.get("web") or data.get("installed") or data
            cid = cid or (web.get("client_id") or "").strip()
            secret = secret or (web.get("client_secret") or "").strip()
        except Exception as exc:
            return None, None, f"Invalid {CLIENT_PATH.name}: {exc}"
    if not cid or not secret:
        return (
            None,
            None,
            "Google OAuth not configured. Set GOOGLE_CLIENT_ID and "
            "GOOGLE_CLIENT_SECRET in .env (see .env.example).",
        )
    return cid, secret, None


def _read_tokens() -> Dict[str, Any]:
    if not TOKEN_PATH.is_file():
        return {}
    try:
        return json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_tokens(data: Dict[str, Any]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def save_client_credentials(client_id: str, client_secret: str) -> Dict[str, Any]:
    """
    Persist Google OAuth web client credentials for local use.
    Writes data/google_client.json and upserts .env (never commit these).
    """
    import os
    import re

    cid = (client_id or "").strip()
    secret = (client_secret or "").strip()
    if not cid or not secret:
        return {"ok": False, "error": "client_id and client_secret required"}
    if "apps.googleusercontent.com" not in cid and not cid.endswith(".apps.googleusercontent.com"):
        # soft warning only — some test clients look different
        pass

    DATA.mkdir(parents=True, exist_ok=True)
    CLIENT_PATH.write_text(
        json.dumps(
            {
                "web": {
                    "client_id": cid,
                    "client_secret": secret,
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    lines: list[str] = []
    if ENV_PATH.is_file():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    elif (ROOT / ".env.example").is_file():
        lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()

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

    # Make available immediately in this process
    os.environ["GOOGLE_CLIENT_ID"] = cid
    os.environ["GOOGLE_CLIENT_SECRET"] = secret

    st = status()
    return {
        "ok": True,
        "configured": bool(st.get("configured")),
        "message": "Google client saved. Tap Sign in with Google.",
        "redirect_uris_hint": suggested_redirect_uris(),
    }


def clear_tokens() -> None:
    if TOKEN_PATH.is_file():
        TOKEN_PATH.unlink()
    try:
        _unlink_profile()
    except Exception:
        pass


def _default_profile_path() -> Path:
    return DATA / "user_profiles" / "default.json"


def _link_profile(email: Optional[str], name: Optional[str], scopes: Any) -> None:
    """Auto-link Google identity into the default companion profile."""
    path = _default_profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: Dict[str, Any] = {}
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    prefs = dict(existing.get("preferences") or {})
    prefs["google_linked"] = True
    prefs["google_email"] = email
    prefs["google_name"] = name
    prefs["google_linked_at"] = time.time()
    if isinstance(scopes, str):
        prefs["google_scopes"] = scopes.split()
    elif isinstance(scopes, list):
        prefs["google_scopes"] = scopes
    existing["user_id"] = existing.get("user_id") or "default"
    existing["preferences"] = prefs
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")


def _unlink_profile() -> None:
    path = _default_profile_path()
    if not path.is_file():
        return
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    prefs = dict(existing.get("preferences") or {})
    prefs["google_linked"] = False
    prefs.pop("google_email", None)
    prefs.pop("google_name", None)
    prefs.pop("google_linked_at", None)
    prefs.pop("google_scopes", None)
    existing["preferences"] = prefs
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")


def status() -> Dict[str, Any]:
    cid, _, cfg_err = get_client()
    tokens = _read_tokens()
    connected = bool(tokens.get("access_token") or tokens.get("refresh_token"))
    return {
        "ok": True,
        "configured": bool(cid) and not cfg_err,
        "config_error": cfg_err,
        "connected": connected,
        "linked": connected,
        "email": tokens.get("email"),
        "name": tokens.get("name"),
        "picture": tokens.get("picture"),
        "scopes": tokens.get("scope") or SCOPES,
        "has_refresh": bool(tokens.get("refresh_token")),
        "flow": (
            "Tap Sign in -> Google login -> approve permissions -> "
            "account auto-links on this PC"
        ),
        "setup_hint": (
            None
            if (cid and not cfg_err)
            else "On the PC run: python scripts/setup_google_oauth.py"
        ),
    }


def build_auth_url(redirect_uri: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (auth_url, error). Opens Google login + consent screen."""
    cid, _, err = get_client()
    if err or not cid:
        return None, err or "missing client id"
    _purge_states()
    pending = _load_pending()
    state = secrets.token_urlsafe(24)
    pending[state] = {"redirect_uri": redirect_uri, "created": time.time()}
    _save_pending(pending)
    params = {
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "include_granted_scopes": "true",
        # Always show account picker + permission screen so linking is explicit
        "prompt": "select_account consent",
        "state": state,
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}", None


def exchange_code(code: str, state: str) -> Dict[str, Any]:
    """Exchange authorization code for tokens and auto-link the profile."""
    cid, secret, err = get_client()
    if err or not cid or not secret:
        return {"ok": False, "error": err or "not configured"}
    _purge_states()
    pending = _load_pending()
    entry = pending.pop(state, None)
    _save_pending(pending)
    if not entry:
        return {
            "ok": False,
            "error": "Invalid or expired OAuth state. Tap Connect with Google again.",
        }
    redirect_uri = entry["redirect_uri"]
    body = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": cid,
            "client_secret": secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            token_data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "error": f"Token exchange failed: {detail}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    existing = _read_tokens()
    merged = {
        **existing,
        "access_token": token_data.get("access_token"),
        "token_type": token_data.get("token_type", "Bearer"),
        "expires_at": time.time() + int(token_data.get("expires_in") or 3600) - 60,
        "scope": token_data.get("scope") or " ".join(SCOPES),
        "updated_at": time.time(),
        "linked_at": time.time(),
    }
    if token_data.get("refresh_token"):
        merged["refresh_token"] = token_data["refresh_token"]
    elif existing.get("refresh_token"):
        merged["refresh_token"] = existing["refresh_token"]

    _write_tokens(merged)
    info = _fetch_userinfo(merged["access_token"])
    if info.get("email"):
        merged["email"] = info["email"]
        merged["name"] = info.get("name")
        merged["picture"] = info.get("picture")
        _write_tokens(merged)
    try:
        _link_profile(merged.get("email"), merged.get("name"), merged.get("scope"))
    except Exception:
        pass
    return {
        "ok": True,
        "linked": True,
        "email": merged.get("email"),
        "name": merged.get("name"),
        "picture": merged.get("picture"),
    }


def _fetch_userinfo(access_token: str) -> Dict[str, Any]:
    req = urllib.request.Request(
        USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}


def _refresh_access_token() -> Tuple[Optional[str], Optional[str]]:
    cid, secret, err = get_client()
    if err or not cid or not secret:
        return None, err or "not configured"
    tokens = _read_tokens()
    refresh = tokens.get("refresh_token")
    if not refresh:
        return None, "Not connected — tap Connect with Google."
    body = urllib.parse.urlencode(
        {
            "client_id": cid,
            "client_secret": secret,
            "refresh_token": refresh,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return None, f"Refresh failed: {detail}"
    except Exception as exc:
        return None, str(exc)
    tokens["access_token"] = data.get("access_token")
    tokens["expires_at"] = time.time() + int(data.get("expires_in") or 3600) - 60
    tokens["updated_at"] = time.time()
    if data.get("scope"):
        tokens["scope"] = data["scope"]
    _write_tokens(tokens)
    return tokens["access_token"], None


def get_valid_access_token() -> Tuple[Optional[str], Optional[str]]:
    tokens = _read_tokens()
    access = tokens.get("access_token")
    expires = float(tokens.get("expires_at") or 0)
    if access and time.time() < expires:
        return access, None
    if tokens.get("refresh_token"):
        return _refresh_access_token()
    if access:
        return access, None
    return None, "Not connected — tap Connect with Google."


def _gmail_request(
    method: str, path: str, payload: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    token, err = get_valid_access_token()
    if err or not token:
        return None, err or "no token"
    url = GMAIL_API + path
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8")
            return (json.loads(raw) if raw else {}), None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return None, f"Gmail API {exc.code}: {detail}"
    except Exception as exc:
        return None, str(exc)


def _rfc2822_message(to: str, subject: str, body: str) -> str:
    import base64
    from email.mime.text import MIMEText

    msg = MIMEText(body, "plain", "utf-8")
    msg["To"] = to
    msg["Subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    return raw


def create_draft(to: str, subject: str, body: str) -> Dict[str, Any]:
    to = (to or "").strip()
    subject = (subject or "").strip()
    body = body or ""
    if not to or "@" not in to:
        return {"ok": False, "error": "Valid To address required"}
    raw = _rfc2822_message(to, subject or "(no subject)", body)
    result, err = _gmail_request(
        "POST", "/drafts", {"message": {"raw": raw}}
    )
    if err:
        return {"ok": False, "error": err}
    return {
        "ok": True,
        "action": "draft",
        "draft_id": (result or {}).get("id"),
        "message_id": ((result or {}).get("message") or {}).get("id"),
        "email": _read_tokens().get("email"),
    }


def send_mail(to: str, subject: str, body: str) -> Dict[str, Any]:
    to = (to or "").strip()
    subject = (subject or "").strip()
    body = body or ""
    if not to or "@" not in to:
        return {"ok": False, "error": "Valid To address required"}
    raw = _rfc2822_message(to, subject or "(no subject)", body)
    result, err = _gmail_request("POST", "/messages/send", {"raw": raw})
    if err:
        return {"ok": False, "error": err}
    return {
        "ok": True,
        "action": "send",
        "message_id": (result or {}).get("id"),
        "thread_id": (result or {}).get("threadId"),
        "email": _read_tokens().get("email"),
    }


def _drive_request(
    method: str,
    path: str,
    *,
    payload: Optional[Dict[str, Any]] = None,
    raw_body: Optional[bytes] = None,
    content_type: Optional[str] = None,
    query: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    token, err = get_valid_access_token()
    if err or not token:
        return None, err or "no token"
    url = DRIVE_API + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = raw_body
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif content_type and raw_body is not None:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8")
            return (json.loads(raw) if raw else {}), None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return None, f"Drive API {exc.code}: {detail}"
    except Exception as exc:
        return None, str(exc)


def drive_status() -> Dict[str, Any]:
    tokens = _read_tokens()
    scope = tokens.get("scope") or ""
    if isinstance(scope, list):
        scope = " ".join(scope)
    linked = bool(tokens.get("access_token") or tokens.get("refresh_token"))
    has_drive = "drive.file" in scope or "drive" in scope
    return {
        "ok": True,
        "linked": linked,
        "drive_scope": has_drive,
        "email": tokens.get("email"),
        "note": (
            "While the app is in Testing, only Test users on the OAuth consent "
            "screen can sign in. Google verification is not required for that."
        ),
    }


def drive_save_note(title: str, content: str) -> Dict[str, Any]:
    """Create a plain-text note in the user's Drive (drive.file scope)."""
    title = (title or "Soul note").strip()[:120] or "Soul note"
    content = content or ""
    # multipart upload
    boundary = "soul_boundary_7xK9"
    meta = json.dumps(
        {"name": f"{title}.txt", "mimeType": "text/plain"},
        ensure_ascii=False,
    )
    body = (
        f"--{boundary}\r\n"
        "Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{meta}\r\n"
        f"--{boundary}\r\n"
        "Content-Type: text/plain; charset=UTF-8\r\n\r\n"
        f"{content}\r\n"
        f"--{boundary}--"
    ).encode("utf-8")
    token, err = get_valid_access_token()
    if err or not token:
        return {"ok": False, "error": err or "Not connected to Google"}
    url = (
        "https://www.googleapis.com/upload/drive/v3/files?"
        + urllib.parse.urlencode({"uploadType": "multipart"})
    )
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/related; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "error": f"Drive upload failed: {detail}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "file_id": data.get("id"),
        "name": data.get("name"),
        "web_link": f"https://drive.google.com/file/d/{data.get('id')}/view",
    }


def drive_list_soul_files(page_size: int = 10) -> Dict[str, Any]:
    """List recent files Soul can see (typically ones it created via drive.file)."""
    result, err = _drive_request(
        "GET",
        "/files",
        query={
            "pageSize": str(max(1, min(int(page_size or 10), 25))),
            "fields": "files(id,name,mimeType,modifiedTime,webViewLink)",
            "orderBy": "modifiedTime desc",
        },
    )
    if err:
        return {"ok": False, "error": err}
    return {"ok": True, "files": (result or {}).get("files") or []}


def suggested_redirect_uris(port: int = 8765, lan_ips: Optional[List[str]] = None) -> List[str]:
    """
    Google Web OAuth only accepts loopback (localhost / 127.0.0.1), not LAN IPs.
    Phone PWA uses the PC-linked tokens; complete Sign-in on the PC browser.
    """
    _ = lan_ips  # unused — LAN IPs are rejected by Google ("public TLD" rule)
    return [
        f"http://127.0.0.1:{port}/api/google/callback",
        f"http://localhost:{port}/api/google/callback",
    ]
