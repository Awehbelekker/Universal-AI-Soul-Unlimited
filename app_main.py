"""
Universal Soul AI - Android App Entry Point
Kivy UI with optional connection to UniversalSoulAI backend.
"""
import asyncio
import os
import sys
import threading
from pathlib import Path

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView

# Demo responses when AI backend is unavailable
_DEMO_RESPONSES = [
    "That's an interesting point! AI backend is starting or unavailable.",
    "I understand. Connect Ollama on desktop or wait for backend init.",
    "Great question! Full AI runs when UniversalSoulAI initializes.",
    "Thanks for testing! Your feedback helps improve the app.",
]


class AIBackend:
    """Runs UniversalSoulAI on a background asyncio loop."""

    def __init__(self):
        self._loop = None
        self._thread = None
        self._soul = None
        self._ready = threading.Event()
        self._error = None

    def start(self):
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=30)

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
        self._loop.run_forever()

    @property
    def available(self) -> bool:
        return self._soul is not None and self._soul.is_initialized

    def process_message(self, message: str, user_id: str = "android_user") -> str:
        if not self.available or not self._loop:
            return self._fallback(message)

        try:
            future = asyncio.run_coroutine_threadsafe(
                self._soul.process_user_request(message, user_id=user_id),
                self._loop,
            )
            return future.result(timeout=90)
        except Exception as exc:
            return f"[AI error: {exc}] {self._fallback(message)}"

    def _fallback(self, message: str) -> str:
        message_lower = message.lower()
        if "hello" in message_lower or "hi" in message_lower:
            return "Hello! Universal Soul AI is loading or using demo mode."
        if "help" in message_lower:
            return "Type any message. Real AI responds when backend is ready."
        if self._error:
            return f"Backend unavailable ({self._error}). Using demo mode."
        idx = hash(message) % len(_DEMO_RESPONSES)
        return _DEMO_RESPONSES[idx]


class MainScreen(Screen):
    """Main chat interface screen"""

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

        scroll = ScrollView(size_hint_y=0.7)
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

        send_btn = Button(text="Send", size_hint_x=0.25, on_press=self.send_message)
        input_box.add_widget(send_btn)
        self.layout.add_widget(input_box)

        self.status_label = Label(
            text="Status: Initializing...",
            size_hint_y=0.05,
            font_size="12sp",
            color=(0.7, 0.7, 0.7, 1),
        )
        self.layout.add_widget(self.status_label)

        btn_box = BoxLayout(size_hint_y=0.05, spacing=5)
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
        mode = "AI" if app.backend.available else "Demo"
        self.status_label.text = f"{mode} | Messages: {self.message_count}"

    def clear_chat(self, instance):
        self.chat_display.text = "Chat cleared. Start a new conversation!\n"
        self.message_count = 0
        self.status_label.text = "Status: Ready"

    def show_about(self, instance):
        self.chat_display.text += (
            "\n[b]Universal Soul AI v1.0[/b]\n"
            "Android build with UniversalSoulAI backend bridge.\n"
        )


class UniversalSoulAIApp(App):
    """Main application class"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "Universal Soul AI"
        self.backend = AIBackend()

    def build(self):
        sm = ScreenManager()
        sm.add_widget(MainScreen(name="main"))
        return sm

    def on_start(self):
        self.backend.start()
        screen = self.root.get_screen("main")
        if self.backend.available:
            screen.chat_display.text += (
                "[color=00ff00]AI backend ready.[/color]\n"
            )
            screen.status_label.text = "Status: AI ready"
        else:
            screen.chat_display.text += (
                "[color=ffaa00]Demo mode — backend unavailable.[/color]\n"
            )
            screen.status_label.text = "Status: Demo mode"

    def process_message(self, message: str) -> str:
        return self.backend.process_message(message)


def main():
    if hasattr(sys, "_MEIPASS"):
        os.chdir(sys._MEIPASS)
    UniversalSoulAIApp().run()


if __name__ == "__main__":
    main()
