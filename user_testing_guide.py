"""
Universal Soul AI - User Testing Guide
======================================

Complete testing suite for user testing the full Universal Soul AI system.
This provides an interactive testing experience for end users.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add Soul Project to path for voice capabilities
SOUL_PROJECT_PATH = r"C:\Users\Richard.Downing\Documents\augment-projects\Soul Project"
sys.path.insert(0, SOUL_PROJECT_PATH)
sys.path.insert(0, str(Path(SOUL_PROJECT_PATH) / "Mobile Open AI EdgeMind Mobile"))

from main import UniversalSoulAI
from core.interfaces.data_structures import UserContext, PersonalityMode


class UserTestingSession:
    """Interactive user testing session"""
    
    def __init__(self):
        self.soul_ai = None
        self.test_results = []
        self.user_feedback = []
        self.session_start = datetime.now()
        
    async def initialize(self):
        """Initialize the Universal Soul AI system"""
        print("\n" + "="*60)
        print("🚀 UNIVERSAL SOUL AI - USER TESTING SESSION")
        print("="*60 + "\n")
        
        print("Initializing Universal Soul AI...")
        self.soul_ai = UniversalSoulAI()
        success = await self.soul_ai.initialize()
        
        if success:
            print("✅ System initialized successfully!\n")
            return True
        else:
            print("❌ System initialization failed\n")
            return False
    
    async def test_hrm_engine(self):
        """Test HRM Engine (27M parameters)"""
        print("\n" + "-"*60)
        print("🧠 TEST 1: HRM ENGINE (27M PARAMETERS)")
        print("-"*60 + "\n")
        
        test_questions = [
            "What are your capabilities?",
            "How can you help me with daily tasks?",
            "What makes you different from other AI?",
        ]
        
        for i, question in enumerate(test_questions, 1):
            print(f"\nQuestion {i}: {question}")
            print("Processing...", end=" ", flush=True)
            
            try:
                response = await self.soul_ai.process_user_request(
                    question,
                    user_id="test_user"
                )
                
                print("✅")
                print(f"Response: {response[:200]}...")
                
                feedback = input("\n👍 Was this response helpful? (y/n/skip): ").strip().lower()
                self.user_feedback.append({
                    "test": "HRM Engine",
                    "question": question,
                    "helpful": feedback == 'y',
                    "skipped": feedback == 'skip'
                })
                
            except Exception as e:
                print(f"❌ Error: {e}")
                self.test_results.append({"test": "HRM Engine", "status": "failed", "error": str(e)})
    
    async def test_personality_modes(self):
        """Test different personality modes"""
        print("\n" + "-"*60)
        print("🎭 TEST 2: PERSONALITY MODES")
        print("-"*60 + "\n")
        
        modes = [
            (PersonalityMode.FRIENDLY, "casual chat"),
            (PersonalityMode.PROFESSIONAL, "business inquiry"),
            (PersonalityMode.ENERGETIC, "motivational request"),
        ]
        
        for mode, scenario in modes:
            print(f"\n🎭 Testing {mode.value.upper()} mode ({scenario})")
            print("Ask a question to test this personality:")
            question = input("Your question (or press Enter for default): ").strip()
            
            if not question:
                question = "Tell me about yourself"
            
            try:
                context = UserContext(
                    user_id="test_user",
                    personality_mode=mode
                )
                
                response = await self.soul_ai.hrm_engine.process_request(question, context)
                print(f"\nResponse: {response[:200]}...")
                
                rating = input("\nRate this personality (1-5): ").strip()
                self.user_feedback.append({
                    "test": f"Personality - {mode.value}",
                    "rating": rating,
                    "question": question
                })
                
            except Exception as e:
                print(f"❌ Error: {e}")
    
    async def test_coact_automation(self):
        """Test CoAct-1 automation engine"""
        print("\n" + "-"*60)
        print("🤖 TEST 3: COACT-1 AUTOMATION ENGINE")
        print("-"*60 + "\n")
        
        print("The CoAct-1 engine automates complex tasks.")
        print("Let's test some automation scenarios:\n")
        
        automation_tasks = [
            "Organize my schedule for tomorrow",
            "Create a reminder for my meeting",
            "Help me plan my week",
        ]
        
        for i, task in enumerate(automation_tasks, 1):
            print(f"\n📋 Task {i}: {task}")
            use_task = input("Test this task? (y/n): ").strip().lower()
            
            if use_task == 'y':
                try:
                    from core.interfaces.data_structures import AutomationTask
                    
                    auto_task = AutomationTask(
                        description=task,
                        complexity=3.0
                    )
                    
                    result = await self.soul_ai.coact_engine.execute_task(auto_task, {})
                    
                    print(f"✅ Success: {result.get('success', False)}")
                    print(f"📊 Confidence: {result.get('confidence', 0):.1%}")
                    
                    self.user_feedback.append({
                        "test": "CoAct-1 Automation",
                        "task": task,
                        "success": result.get('success', False)
                    })
                    
                except Exception as e:
                    print(f"❌ Error: {e}")
    
    async def test_voice_capabilities(self):
        """Test voice capabilities from Soul Project"""
        print("\n" + "-"*60)
        print("🎤 TEST 4: VOICE CAPABILITIES (OPTIONAL)")
        print("-"*60 + "\n")
        
        print("Voice capabilities are available from the Soul Project.")
        test_voice = input("Would you like to test voice features? (y/n): ").strip().lower()
        
        if test_voice == 'y':
            try:
                print("\nAttempting to load voice system...")
                from living_soul.voice.unified_voice_engine import UnifiedVoiceEngine
                from living_soul.core.config_manager import ConfigManager
                
                print("✅ Voice system available!")
                print("\nVoice Features:")
                print("  • Text-to-Speech (Coqui TTS / ElevenLabs)")
                print("  • Speech-to-Text (Whisper / Deepgram)")
                print("  • Voice Cloning (XTTS v2)")
                print("  • Multiple personalities and emotions")
                
                self.test_results.append({"test": "Voice System", "status": "available"})
                
            except ImportError as e:
                print(f"⚠️ Voice system not fully configured: {e}")
                print("   Install with: pip install TTS elevenlabs")
                self.test_results.append({"test": "Voice System", "status": "not_configured"})
        else:
            print("⏭️  Skipping voice tests")
    
    async def interactive_chat_session(self):
        """Interactive chat session for freeform testing"""
        print("\n" + "-"*60)
        print("💬 TEST 5: INTERACTIVE CHAT SESSION")
        print("-"*60 + "\n")
        
        print("Now you can chat freely with Universal Soul AI!")
        print("Type 'exit' to end the session.\n")
        
        while True:
            user_input = input("You: ").strip()
            
            if user_input.lower() in ['exit', 'quit', 'done']:
                break
            
            if not user_input:
                continue
            
            try:
                response = await self.soul_ai.process_user_request(
                    user_input,
                    user_id="test_user"
                )
                
                print(f"\n🤖 Soul AI: {response}\n")
                
            except Exception as e:
                print(f"❌ Error: {e}\n")
    
    async def collect_overall_feedback(self):
        """Collect overall user feedback"""
        print("\n" + "="*60)
        print("📊 FINAL FEEDBACK")
        print("="*60 + "\n")
        
        print("Thank you for testing Universal Soul AI!")
        print("\nPlease provide your overall feedback:\n")
        
        questions = [
            "Overall satisfaction (1-5): ",
            "Ease of use (1-5): ",
            "Response quality (1-5): ",
            "Would you use this daily? (y/n): ",
            "What did you like most? ",
            "What needs improvement? ",
        ]
        
        overall_feedback = {}
        for question in questions:
            answer = input(question).strip()
            overall_feedback[question] = answer
        
        self.user_feedback.append({
            "test": "Overall Feedback",
            "feedback": overall_feedback
        })
    
    def generate_test_report(self):
        """Generate test report"""
        print("\n" + "="*60)
        print("📋 USER TESTING REPORT")
        print("="*60 + "\n")
        
        print(f"Session Duration: {datetime.now() - self.session_start}")
        print(f"Total Tests: {len(self.test_results)}")
        print(f"Feedback Items: {len(self.user_feedback)}\n")
        
        print("Test Results:")
        for result in self.test_results:
            status_emoji = "✅" if result.get('status') != 'failed' else "❌"
            print(f"  {status_emoji} {result.get('test', 'Unknown')}: {result.get('status', 'completed')}")
        
        print("\nUser Feedback Summary:")
        helpful_count = sum(1 for f in self.user_feedback if f.get('helpful'))
        print(f"  Helpful Responses: {helpful_count}/{len([f for f in self.user_feedback if 'helpful' in f])}")
        
        # Save report
        report_file = f"user_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, 'w') as f:
            f.write("="*60 + "\n")
            f.write("UNIVERSAL SOUL AI - USER TESTING REPORT\n")
            f.write("="*60 + "\n\n")
            f.write(f"Date: {datetime.now()}\n")
            f.write(f"Duration: {datetime.now() - self.session_start}\n\n")
            
            f.write("Test Results:\n")
            for result in self.test_results:
                f.write(f"  - {result}\n")
            
            f.write("\nUser Feedback:\n")
            for feedback in self.user_feedback:
                f.write(f"  - {feedback}\n")
        
        print(f"\n📄 Report saved to: {report_file}")
    
    async def run_full_test_suite(self):
        """Run complete user testing suite"""
        if not await self.initialize():
            return
        
        print("\n🧪 Starting User Testing Suite...")
        print("You'll be guided through various tests.\n")
        
        input("Press Enter to begin...")
        
        # Run tests
        await self.test_hrm_engine()
        await self.test_personality_modes()
        await self.test_coact_automation()
        await self.test_voice_capabilities()
        await self.interactive_chat_session()
        await self.collect_overall_feedback()
        
        # Generate report
        self.generate_test_report()
        
        print("\n" + "="*60)
        print("🎉 USER TESTING COMPLETE!")
        print("="*60)
        print("\nThank you for testing Universal Soul AI!")
        print("Your feedback helps make it better! 🚀\n")


async def main():
    """Run user testing session"""
    session = UserTestingSession()
    await session.run_full_test_suite()


if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║          UNIVERSAL SOUL AI - USER TESTING SUITE           ║
║                                                            ║
║  This interactive session will guide you through testing  ║
║  all major features of Universal Soul AI.                 ║
║                                                            ║
║  Tests Include:                                           ║
║    • HRM Engine (27M parameters)                          ║
║    • Personality Modes                                    ║
║    • CoAct-1 Automation                                   ║
║    • Voice Capabilities                                   ║
║    • Interactive Chat                                     ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
""")
    
    asyncio.run(main())
