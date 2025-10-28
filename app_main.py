"""
Universal Soul AI - Android App Entry Point
Simplified version for Android beta testing
"""
import os
import sys
from pathlib import Path

# Kivy imports
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView


class MainScreen(Screen):
    """Main chat interface screen"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Title
        title = Label(
            text='Universal Soul AI - Beta',
            size_hint_y=0.08,
            font_size='24sp',
            bold=True
        )
        self.layout.add_widget(title)
        
        # Chat history with scroll
        scroll = ScrollView(size_hint_y=0.7)
        self.chat_display = Label(
            text='Welcome to Universal Soul AI Beta!\n\nThis is a simplified demo version.\nType a message below to test the interface.\n',
            size_hint_y=None,
            markup=True
        )
        self.chat_display.bind(texture_size=self.chat_display.setter('size'))
        scroll.add_widget(self.chat_display)
        self.layout.add_widget(scroll)
        
        # Input area
        input_box = BoxLayout(size_hint_y=0.12, spacing=5)
        self.message_input = TextInput(
            hint_text='Type your message...',
            multiline=False,
            size_hint_x=0.75
        )
        self.message_input.bind(on_text_validate=self.send_message)
        input_box.add_widget(self.message_input)
        
        send_btn = Button(
            text='Send',
            size_hint_x=0.25,
            on_press=self.send_message
        )
        input_box.add_widget(send_btn)
        self.layout.add_widget(input_box)
        
        # Status bar
        self.status_label = Label(
            text='Status: Beta Testing Mode',
            size_hint_y=0.05,
            font_size='12sp',
            color=(0.7, 0.7, 0.7, 1)
        )
        self.layout.add_widget(self.status_label)
        
        # Button bar
        btn_box = BoxLayout(size_hint_y=0.05, spacing=5)
        
        info_btn = Button(
            text='About',
            on_press=self.show_about
        )
        btn_box.add_widget(info_btn)
        
        clear_btn = Button(
            text='Clear',
            on_press=self.clear_chat
        )
        btn_box.add_widget(clear_btn)
        
        self.layout.add_widget(btn_box)
        
        self.add_widget(self.layout)
        self.message_count = 0
    
    def send_message(self, instance):
        """Handle send button click"""
        message = self.message_input.text.strip()
        if not message:
            return
        
        self.message_count += 1
        
        # Add user message
        self.chat_display.text += f"\n[b]You:[/b] {message}\n"
        self.message_input.text = ""
        
        # Get AI response
        app = App.get_running_app()
        response = app.process_message(message)
        
        # Add AI response
        self.chat_display.text += f"[color=00ff00][b]AI:[/b][/color] {response}\n"
        
        self.status_label.text = f'Messages: {self.message_count}'
    
    def clear_chat(self, instance):
        """Clear chat history"""
        self.chat_display.text = 'Chat cleared. Start a new conversation!\n'
        self.message_count = 0
        self.status_label.text = 'Status: Ready'
    
    def show_about(self, instance):
        """Show about info"""
        self.chat_display.text += '\n[b]Universal Soul AI - Beta v1.0[/b]\nBuilt for Android testing\nFeatures: Basic chat interface\n'





class UniversalSoulAIApp(App):
    """Main application class - Simplified for beta testing"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = 'Universal Soul AI - Beta'
        self.responses = [
            "That's an interesting point! This is a beta test version.",
            "I understand. The full AI integration will be available in the next release.",
            "Great question! Currently testing the interface functionality.",
            "Thanks for testing! Your feedback helps improve the app.",
            "The AI engine will be fully integrated in the production version.",
            "This beta focuses on UI/UX testing. Full AI coming soon!",
            "Excellent! The app is working as expected for beta testing.",
            "I appreciate your input. More features will be added based on feedback.",
        ]
        self.response_index = 0
    
    def build(self):
        """Build the app UI"""
        # Create screen manager
        sm = ScreenManager()
        sm.add_widget(MainScreen(name='main'))
        return sm
    
    def process_message(self, message: str) -> str:
        """Process user message with demo responses
        
        Args:
            message: User input message
            
        Returns:
            Demo response
        """
        # Simple demo logic
        message_lower = message.lower()
        
        if 'hello' in message_lower or 'hi' in message_lower:
            return "Hello! Welcome to the Universal Soul AI beta test. How can I help you today?"
        
        elif 'help' in message_lower:
            return "This is a beta test version. Try asking me anything to test the interface!"
        
        elif 'who are you' in message_lower or 'what are you' in message_lower:
            return "I'm Universal Soul AI, currently in beta testing. The full AI engine will be integrated in the production release."
        
        elif 'bye' in message_lower or 'goodbye' in message_lower:
            return "Goodbye! Thanks for testing the beta version."
        
        elif 'features' in message_lower:
            return "Beta features: Chat interface, message history, smooth scrolling. Full AI features coming in v1.0!"
        
        else:
            # Cycle through responses
            response = self.responses[self.response_index]
            self.response_index = (self.response_index + 1) % len(self.responses)
            return response


def main():
    """Application entry point"""
    # Set up paths
    if hasattr(sys, '_MEIPASS'):
        # Running in PyInstaller bundle
        os.chdir(sys._MEIPASS)
    
    # Run app
    app = UniversalSoulAIApp()
    app.run()


if __name__ == '__main__':
    main()
