"""
Universal Soul AI - Android App Entry Point
Kivy UI with UniversalSoulAI backend, network Ollama fallback, or demo mode.

Thin-client focus: persist Ollama URL/model, Settings screen, resilient LAN checks.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

# Prefer config / env for network Ollama (phone → PC on LAN)
_DEFAULT_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
_DEFAULT_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
_SETTINGS_NAME = "android_settings.json"

_DEMO_RESPONSES = [
    "That's an interesting point! AI backend is starting or unavailable.",
    "I understand. Connect Ollama on desktop or wait for backend init.",
    "Great question! Full AI runs when UniversalSoulAI initializes.",
    "Thanks for testing! Your feedback helps improve the app.",
]


def normalize_ollama_url(url: str) -> str:
    """Accept host, host:port, or full URL; default port 11434."""
    u = (url or "").strip()
    if not u:
        return _DEFAULT_OLLAMA_URL.rstrip("/")
    if "://" not in u:
        u = "http://" + u
    u = u.rstrip("/")
    parsed = urlparse(u)
    host = parsed.hostname
    if not host:
        return _DEFAULT_OLLAMA_URL.rstrip("/")
    port = parsed.port
    if port is None:
        port = 11434
    scheme = parsed.scheme or "http"
    return f"{scheme}://{host}:{port}"


def _candidate_settings_paths(user_data_dir: Optional[str] = None) -> Tuple[Path, ...]:
    paths = []
    if user_data_dir:
        paths.append(Path(user_data_dir) / _SETTINGS_NAME)
    root = Path(__file__).resolve().parent
    paths.append(root / "data" / _SETTINGS_NAME)
    paths.append(Path("data") / _SETTINGS_NAME)
    # Deduplicate while preserving order
    seen = set()
    out = []
    for p in paths:
        key = str(p.resolve()) if p.parent.exists() else str(p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return tuple(out)


def load_ollama_settings(
    user_data_dir: Optional[str] = None,
) -> Tuple[str, str]:
    """Load URL/model: env → saved settings → config JSON → defaults."""
    url = _DEFAULT_OLLAMA_URL
    model = _DEFAULT_OLLAMA_MODEL
    env_url = os.environ.get("OLLAMA_URL")
    env_model = os.environ.get("OLLAMA_MODEL")

    for path in _candidate_settings_paths(user_data_dir):
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            url = data.get("ollama_url", url)
            model = data.get("ollama_model", model)
            break
        except Exception:
            continue

    for candidate in (
        Path("config/universal_soul.json"),
        Path(__file__).resolve().parent / "config" / "universal_soul.json",
    ):
        if not candidate.is_file():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
            hrm = data.get("hrm", {})
            # Saved settings already applied; config fills gaps only if still default
            if not any(
                p.is_file() for p in _candidate_settings_paths(user_data_dir)
            ):
                url = hrm.get("ollama_url", url)
                model = hrm.get("ollama_model", model)
            break
        except Exception:
            pass

    # Explicit env wins (useful for desktop smoke / CI)
    if env_url:
        url = env_url
    if env_model:
        model = env_model

    return normalize_ollama_url(url), (model or _DEFAULT_OLLAMA_MODEL).strip()


def save_ollama_settings(
    url: str,
    model: str,
    user_data_dir: Optional[str] = None,
) -> Path:
    """Persist settings to the first writable candidate path."""
    payload = {
        "ollama_url": normalize_ollama_url(url),
        "ollama_model": (model or _DEFAULT_OLLAMA_MODEL).strip(),
        "updated_at": time.time(),
    }
    last_err: Optional[Exception] = None
    for path in _candidate_settings_paths(user_data_dir):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return path
        except Exception as e:
            last_err = e
            continue
    raise OSError(f"Could not save settings: {last_err}")


class OllamaClient:
    """Minimal synchronous Ollama HTTP client for Android thin-client mode."""

    def __init__(self, base_url: str, model: str):
        self.base_url = normalize_ollama_url(base_url)
        self.model = (model or _DEFAULT_OLLAMA_MODEL).strip()

    def configure(self, base_url: str, model: str) -> None:
        self.base_url = normalize_ollama_url(base_url)
        self.model = (model or _DEFAULT_OLLAMA_MODEL).strip()

    def healthy(self, timeout: float = 3.0, retries: int = 2) -> bool:
        return self.probe(timeout=timeout, retries=retries)["ok"]

    def probe(self, timeout: float = 3.0, retries: int = 2) -> Dict[str, Any]:
        """Return {ok, error, models?, latency_ms} for Settings UI."""
        last_err = "unreachable"
        url = f"{self.base_url}/api/tags"
        for attempt in range(max(1, retries)):
            started = time.time()
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "UniversalSoulAI/android"},
                    method="GET",
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw) if raw else {}
                    models = [
                        m.get("name")
                        for m in data.get("models", [])
                        if isinstance(m, dict) and m.get("name")
                    ]
                    return {
                        "ok": resp.status == 200,
                        "error": None,
                        "models": models,
                        "latency_ms": int((time.time() - started) * 1000),
                        "url": self.base_url,
                    }
            except Exception as exc:
                last_err = str(exc)
                if attempt + 1 < retries:
                    time.sleep(0.35 * (attempt + 1))
        return {
            "ok": False,
            "error": last_err,
            "models": [],
            "latency_ms": None,
            "url": self.base_url,
            "hint": (
                "On the PC run Ollama bound to LAN "
                "(OLLAMA_HOST=0.0.0.0) and allow port 11434."
            ),
        }

    def chat(self, message: str, timeout: int = 90, retries: int = 2) -> str:
        payload = json.dumps(
            {
                "model": self.model,
                "prompt": (
                    "You are Universal Soul AI. Reply directly and helpfully.\n\n"
                    f"User: {message}\n\nAssistant:"
                ),
                "stream": False,
                "options": {"num_predict": 256, "temperature": 0.7},
            }
        ).encode("utf-8")
        last_err: Optional[Exception] = None
        for attempt in range(max(1, retries)):
            try:
                req = urllib.request.Request(
                    f"{self.base_url}/api/generate",
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "UniversalSoulAI/android",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                return (data.get("response") or "").strip() or "(empty response)"
            except Exception as exc:
                last_err = exc
                if attempt + 1 < retries:
                    time.sleep(0.4 * (attempt + 1))
        raise last_err or RuntimeError("Ollama chat failed")


class AIBackend:
    """Runs UniversalSoulAI on a background loop; falls back to Ollama HTTP."""

    def __init__(self):
        self._loop = None
        self._thread = None
        self._soul = None
        self._ready = threading.Event()
        self._error = None
        self._ollama: Optional[OllamaClient] = None
        self._mode = "demo"  # full | ollama | demo
        self._user_data_dir: Optional[str] = None

    def set_user_data_dir(self, path: str) -> None:
        self._user_data_dir = path

    def start(self):
        url, model = load_ollama_settings(self._user_data_dir)
        self._ollama = OllamaClient(url, model)
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=30)
        self.refresh_mode()

    def refresh_mode(self) -> str:
        if self._soul is not None and getattr(self._soul, "is_initialized", False):
            self._mode = "full"
        elif self._ollama and self._ollama.healthy():
            self._mode = "ollama"
        else:
            self._mode = "demo"
        return self._mode

    def apply_ollama_settings(self, url: str, model: str) -> Dict[str, Any]:
        """Save + apply + probe. Returns probe result."""
        path = save_ollama_settings(url, model, self._user_data_dir)
        if self._ollama is None:
            self._ollama = OllamaClient(url, model)
        else:
            self._ollama.configure(url, model)
        probe = self._ollama.probe()
        if self._mode != "full":
            self._mode = "ollama" if probe.get("ok") else "demo"
        probe["saved_to"] = str(path)
        probe["model"] = self._ollama.model
        return probe

    def settings_snapshot(self) -> Dict[str, str]:
        if self._ollama:
            return {
                "ollama_url": self._ollama.base_url,
                "ollama_model": self._ollama.model,
                "mode": self._mode,
            }
        url, model = load_ollama_settings(self._user_data_dir)
        return {"ollama_url": url, "ollama_model": model, "mode": self._mode}

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            from main_desktop import UniversalSoulAI

            self._soul = UniversalSoulAI()
            self._loop.run_until_complete(self._soul.initialize())
        except Exception as exc:
            self._error = str(exc)
            self._soul = None
        finally:
            self._ready.set()
        if self._soul is not None:
            self._loop.run_forever()

    @property
    def available(self) -> bool:
        return self._mode in ("full", "ollama")

    @property
    def mode(self) -> str:
        return self._mode

    def process_message(self, message: str, user_id: str = "android_user") -> str:
        if self._mode == "full" and self._soul and self._loop:
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._soul.process_user_request(message, user_id=user_id),
                    self._loop,
                )
                return future.result(timeout=90)
            except Exception as exc:
                if self._ollama and self._ollama.healthy():
                    self._mode = "ollama"
                else:
                    return f"[AI error: {exc}] {self._fallback(message)}"

        if self._mode == "ollama" and self._ollama:
            try:
                return self._ollama.chat(message)
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                self.refresh_mode()
                return f"[Ollama error: {exc}] {self._fallback(message)}"

        return self._fallback(message)

    def _fallback(self, message: str) -> str:
        message_lower = message.lower()
        if "hello" in message_lower or "hi" in message_lower:
            return "Hello! Universal Soul AI is loading or using demo mode."
        if "help" in message_lower:
            url = self._ollama.base_url if self._ollama else "n/a"
            return (
                "Type any message. Modes: full stack, network Ollama, or demo. "
                f"Open Settings to set Ollama URL (now {url})."
            )
        if self._error:
            return f"Backend unavailable ({self._error}). Using demo mode."
        idx = hash(message) % len(_DEMO_RESPONSES)
        return _DEMO_RESPONSES[idx]


def main():
    # Delayed Kivy import so OllamaClient can be tested without Kivy.
    from kivy.app import App
    from kivy.uix.screenmanager import ScreenManager, Screen
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label
    from kivy.uix.button import Button
    from kivy.uix.textinput import TextInput
    from kivy.uix.scrollview import ScrollView

    class MainScreen(Screen):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.layout = BoxLayout(orientation="vertical", padding=10, spacing=10)

            title = Label(
                text="Universal Soul AI",
                size_hint_y=0.08,
                font_size="24sp",
                bold=True,
            )
            self.layout.add_widget(title)

            scroll = ScrollView(size_hint_y=0.65)
            self.chat_display = Label(
                text=(
                    "Welcome to Universal Soul AI!\n\n"
                    "Connecting to AI backend...\n"
                ),
                size_hint_y=None,
                markup=True,
            )
            self.chat_display.bind(texture_size=self.chat_display.setter("size"))
            scroll.add_widget(self.chat_display)
            self.layout.add_widget(scroll)

            input_box = BoxLayout(size_hint_y=0.12, spacing=5)
            self.message_input = TextInput(
                hint_text="Type your message...",
                multiline=False,
                size_hint_x=0.75,
            )
            self.message_input.bind(on_text_validate=self.send_message)
            input_box.add_widget(self.message_input)

            send_btn = Button(
                text="Send", size_hint_x=0.25, on_press=self.send_message
            )
            input_box.add_widget(send_btn)
            self.layout.add_widget(input_box)

            self.status_label = Label(
                text="Status: Initializing...",
                size_hint_y=0.05,
                font_size="12sp",
                color=(0.7, 0.7, 0.7, 1),
            )
            self.layout.add_widget(self.status_label)

            btn_box = BoxLayout(size_hint_y=0.1, spacing=5)
            btn_box.add_widget(Button(text="Settings", on_press=self.open_settings))
            btn_box.add_widget(Button(text="About", on_press=self.show_about))
            btn_box.add_widget(Button(text="Clear", on_press=self.clear_chat))
            self.layout.add_widget(btn_box)

            self.add_widget(self.layout)
            self.message_count = 0

        def send_message(self, instance):
            message = self.message_input.text.strip()
            if not message:
                return

            self.message_count += 1
            self.chat_display.text += f"\n[b]You:[/b] {message}\n"
            self.message_input.text = ""

            app = App.get_running_app()
            response = app.process_message(message)
            self.chat_display.text += (
                f"[color=00ff00][b]AI:[/b][/color] {response}\n"
            )
            mode = app.backend.mode.title()
            self.status_label.text = f"{mode} | Messages: {self.message_count}"

        def clear_chat(self, instance):
            self.chat_display.text = "Chat cleared. Start a new conversation!\n"
            self.message_count = 0
            self.status_label.text = "Status: Ready"

        def open_settings(self, instance):
            app = App.get_running_app()
            settings = self.manager.get_screen("settings")
            settings.load_from_backend(app.backend)
            self.manager.current = "settings"

        def show_about(self, instance):
            app = App.get_running_app()
            snap = app.backend.settings_snapshot()
            self.chat_display.text += (
                "\n[b]Universal Soul AI — Android thin client[/b]\n"
                "Modes: full stack → network Ollama → demo.\n"
                f"Ollama URL: {snap.get('ollama_url')}\n"
                f"Model: {snap.get('ollama_model')}\n"
                "Use Settings to set your PC LAN IP "
                "(e.g. 192.168.1.10 or http://192.168.1.10:11434).\n"
                "PC tip: set OLLAMA_HOST=0.0.0.0 before starting Ollama.\n"
            )

        def on_mode_changed(self, mode: str):
            self.status_label.text = f"Status: {mode}"

    class SettingsScreen(Screen):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            root = BoxLayout(orientation="vertical", padding=12, spacing=8)

            root.add_widget(
                Label(
                    text="Ollama / LAN Settings",
                    size_hint_y=0.08,
                    font_size="20sp",
                    bold=True,
                )
            )
            root.add_widget(
                Label(
                    text=(
                        "Point at your desktop Ollama over Wi‑Fi.\n"
                        "Example: 192.168.1.10  or  http://192.168.1.10:11434"
                    ),
                    size_hint_y=0.12,
                    font_size="13sp",
                )
            )

            root.add_widget(Label(text="Ollama URL / host", size_hint_y=0.05))
            self.url_input = TextInput(
                multiline=False,
                size_hint_y=0.08,
                hint_text="192.168.x.x:11434",
            )
            root.add_widget(self.url_input)

            root.add_widget(Label(text="Model", size_hint_y=0.05))
            self.model_input = TextInput(
                multiline=False,
                size_hint_y=0.08,
                hint_text="llama3.2:3b",
            )
            root.add_widget(self.model_input)

            self.result_label = Label(
                text="",
                size_hint_y=0.28,
                font_size="13sp",
                markup=True,
            )
            root.add_widget(self.result_label)

            row = BoxLayout(size_hint_y=0.1, spacing=6)
            row.add_widget(Button(text="Test", on_press=self.test_connection))
            row.add_widget(Button(text="Save", on_press=self.save_settings))
            row.add_widget(Button(text="Back", on_press=self.go_back))
            root.add_widget(row)

            self.add_widget(root)

        def load_from_backend(self, backend: AIBackend) -> None:
            snap = backend.settings_snapshot()
            self.url_input.text = snap.get("ollama_url", "")
            self.model_input.text = snap.get("ollama_model", "")
            self.result_label.text = f"Current mode: {snap.get('mode')}"

        def test_connection(self, instance):
            app = App.get_running_app()
            url = normalize_ollama_url(self.url_input.text)
            model = self.model_input.text.strip() or _DEFAULT_OLLAMA_MODEL
            client = OllamaClient(url, model)
            self.result_label.text = "Testing…"
            probe = client.probe()
            if probe.get("ok"):
                models = ", ".join((probe.get("models") or [])[:6]) or "(none listed)"
                self.result_label.text = (
                    f"[color=00ff00]OK[/color] {probe.get('latency_ms')} ms\n"
                    f"URL: {probe.get('url')}\n"
                    f"Models: {models}\n"
                    "(Tap Save to keep these settings.)"
                )
                # Session-only apply so chat works immediately
                if app.backend._ollama is None:
                    app.backend._ollama = client
                else:
                    app.backend._ollama.configure(url, model)
                if app.backend.mode != "full":
                    app.backend._mode = "ollama"
                main = self.manager.get_screen("main")
                main.on_mode_changed(app.backend.mode.title())
            else:
                hint = probe.get("hint") or ""
                self.result_label.text = (
                    f"[color=ff6666]Failed[/color]\n"
                    f"{probe.get('error')}\n{hint}"
                )

        def save_settings(self, instance):
            app = App.get_running_app()
            url = self.url_input.text
            model = self.model_input.text
            try:
                probe = app.backend.apply_ollama_settings(url, model)
            except OSError as exc:
                self.result_label.text = f"[color=ff6666]Save failed:[/color] {exc}"
                return
            if probe.get("ok"):
                self.result_label.text = (
                    f"[color=00ff00]Saved + connected[/color]\n"
                    f"{probe.get('saved_to')}\n"
                    f"Mode: {app.backend.mode}"
                )
            else:
                self.result_label.text = (
                    f"[color=ffaa00]Saved, but not reachable yet[/color]\n"
                    f"{probe.get('error')}\n"
                    f"{probe.get('hint') or ''}"
                )
            main = self.manager.get_screen("main")
            main.on_mode_changed(app.backend.mode.title())

        def go_back(self, instance):
            self.manager.current = "main"

    class UniversalSoulAIApp(App):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.title = "Universal Soul AI"
            self.backend = AIBackend()

        def build(self):
            self.backend.set_user_data_dir(self.user_data_dir)
            sm = ScreenManager()
            sm.add_widget(MainScreen(name="main"))
            sm.add_widget(SettingsScreen(name="settings"))
            return sm

        def on_start(self):
            self.backend.set_user_data_dir(self.user_data_dir)
            self.backend.start()
            screen = self.root.get_screen("main")
            if self.backend.mode == "full":
                screen.chat_display.text += (
                    "[color=00ff00]AI backend ready (full stack).[/color]\n"
                )
                screen.status_label.text = "Status: AI ready"
            elif self.backend.mode == "ollama":
                snap = self.backend.settings_snapshot()
                screen.chat_display.text += (
                    "[color=00aaff]Network Ollama ready.[/color]\n"
                    f"URL: {snap.get('ollama_url')} | "
                    f"model: {snap.get('ollama_model')}\n"
                )
                screen.status_label.text = "Status: Ollama"
            else:
                screen.chat_display.text += (
                    "[color=ffaa00]Demo mode — open Settings to set LAN Ollama.[/color]\n"
                )
                screen.status_label.text = "Status: Demo mode"

        def process_message(self, message: str) -> str:
            return self.backend.process_message(message)

    if hasattr(sys, "_MEIPASS"):
        os.chdir(sys._MEIPASS)
    UniversalSoulAIApp().run()


if __name__ == "__main__":
    main()
