"""
Simplified main.py that imports app_main for Android build compatibility
"""
from app_main import UniversalSoulAIApp

if __name__ == '__main__':
    app = UniversalSoulAIApp()
    app.run()
