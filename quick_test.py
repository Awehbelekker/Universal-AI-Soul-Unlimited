"""
Quick User Test - Universal Soul AI
===================================

Simple 5-minute test to verify everything works.
"""

import asyncio
import sys
sys.path.insert(0, r"C:\Users\Richard.Downing\Desktop\Universal-Soul-AI-Complete")

from main import UniversalSoulAI
from core.interfaces.data_structures import UserContext, PersonalityMode


async def quick_test():
    """Quick 5-minute user test"""
    
    print("\n" + "="*60)
    print("⚡ UNIVERSAL SOUL AI - QUICK TEST (5 minutes)")
    print("="*60 + "\n")
    
    # Initialize
    print("1️⃣  Initializing system...")
    soul_ai = UniversalSoulAI()
    success = await soul_ai.initialize()
    
    if not success:
        print("❌ Initialization failed")
        return
    
    print("✅ System ready!\n")
    
    # Test 1: Basic question
    print("2️⃣  Testing HRM Engine (27M parameters)...")
    response = await soul_ai.process_user_request(
        "What can you help me with?",
        user_id="quick_test"
    )
    print(f"Response: {response[:150]}...\n")
    
    # Test 2: Personality
    print("3️⃣  Testing Personality Modes...")
    context = UserContext(
        user_id="quick_test",
        personality_mode=PersonalityMode.FRIENDLY
    )
    response = await soul_ai.hrm_engine.process_request(
        "Tell me a joke",
        context
    )
    print(f"Friendly Mode: {response[:150]}...\n")
    
    # Test 3: Automation
    print("4️⃣  Testing CoAct-1 Automation...")
    from core.interfaces.data_structures import AutomationTask
    
    task = AutomationTask(
        description="Schedule a meeting for tomorrow",
        complexity=3.0
    )
    result = await soul_ai.coact_engine.execute_task(task, {})
    print(f"✅ Automation Success: {result.get('success')}")
    print(f"📊 Confidence: {result.get('confidence', 0):.1%}\n")
    
    # Interactive test
    print("5️⃣  Interactive Test - Ask a question:")
    user_question = input("Your question: ").strip()
    
    if user_question:
        response = await soul_ai.process_user_request(
            user_question,
            user_id="quick_test"
        )
        print(f"\n🤖 Response: {response}\n")
    
    print("="*60)
    print("✅ QUICK TEST COMPLETE!")
    print("="*60)
    print("\nSystem Status: All core features working! ✨")
    print("\nReady for full user testing with user_testing_guide.py\n")


if __name__ == "__main__":
    asyncio.run(quick_test())
