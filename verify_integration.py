"""
Universal Soul AI - Integration Verification Script
===================================================

Verifies 100% integration of all optimization modules.
Tests each component and provides comprehensive status report.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from main import UniversalSoulAI


async def verify_integration():
    """Verify complete system integration"""
    print("=" * 70)
    print("UNIVERSAL SOUL AI - INTEGRATION VERIFICATION")
    print("=" * 70)
    print()
    
    try:
        # Initialize system
        print("🔧 Initializing Universal Soul AI system...")
        system = UniversalSoulAI()
        await system.initialize()
        print("✅ System initialized successfully")
        print()
        
        # Get system status
        status = await system.get_system_status()
        
        # Display component status
        print("📊 Component Status:")
        print("-" * 70)
        
        # Core engines
        print(f"  HRM Engine (Ollama + Qwen2.5-3B): ", end="")
        print("✅ Active" if status['hrm_engine'] else "❌ Inactive")
        
        print(f"  CoAct-1 Engine (TerminalBench):   ", end="")
        print("✅ Active" if status['coact_engine'] else "❌ Inactive")
        
        # Optimization engines
        print(f"  Coqui TTS (6 Personalities):      ", end="")
        tts_status = status['optimization_engines']['tts_enabled']
        print("✅ Active" if tts_status else "❌ Inactive")
        
        print(f"  MemGPT (Long-Term Memory):        ", end="")
        mem_status = status['optimization_engines']['memory_enabled']
        print("✅ Active" if mem_status else "❌ Inactive")
        
        print()
        print("-" * 70)
        
        # System metrics
        print("📈 System Metrics:")
        print("-" * 70)
        metrics = status['system_metrics']
        print(f"  Total Requests:       {metrics['total_requests']}")
        print(f"  Successful Requests:  {metrics['successful_requests']}")
        print(f"  Active Sessions:      {status['active_sessions']}")
        print(f"  Config Version:       {status['config_version']}")
        print()
        print("-" * 70)
        
        # Engine details
        if status['hrm_engine']:
            print("🧠 HRM Engine Details:")
            print("-" * 70)
            hrm = status['hrm_engine']
            print(f"  Model:                {hrm.get('model_name', 'N/A')}")
            print(f"  Backend:              {hrm.get('backend', 'N/A')}")
            print(f"  Context Window:       {hrm.get('context_window', 'N/A')}")
            print(f"  Total Inferences:     {hrm.get('total_inferences', 0)}")
            print(f"  Avg Response Time:    "
                  f"{hrm.get('average_response_time', 0):.2f}s")
            print()
            print("-" * 70)
        
        if status['coact_engine']:
            print("🤖 CoAct-1 Engine Details:")
            print("-" * 70)
            coact = status['coact_engine']
            print(f"  Total Tasks:          {coact.get('total_tasks', 0)}")
            print(f"  Successful Tasks:     {coact.get('successful_tasks', 0)}")
            success_rate = coact.get('success_rate', 0)
            print(f"  Success Rate:         {success_rate:.1f}%")
            print(f"  TerminalBench Tasks:  "
                  f"{coact.get('terminalbench_tasks', 0)}")
            print()
            print("-" * 70)
        
        # Integration summary
        print()
        print("🎯 Integration Summary:")
        print("=" * 70)
        
        total_components = 4
        active_components = sum([
            bool(status['hrm_engine']),
            bool(status['coact_engine']),
            tts_status,
            mem_status
        ])
        
        integration_percentage = (active_components / total_components) * 100
        
        print(f"  Active Components:    {active_components}/{total_components}")
        print(f"  Integration Level:    {integration_percentage:.0f}%")
        print()
        
        if integration_percentage == 100:
            print("  Status:               🎉 100% INTEGRATION COMPLETE 🎉")
            print()
            print("  All optimization modules are fully integrated and active!")
            print("  System is production-ready with:")
            print("    ✅ Real AI inference (Qwen2.5-3B)")
            print("    ✅ Advanced automation (TerminalBench)")
            print("    ✅ Personality voices (Coqui TTS)")
            print("    ✅ Long-term memory (MemGPT)")
        elif integration_percentage >= 50:
            print(f"  Status:               ⚠️  {integration_percentage:.0f}% "
                  "Integration")
            print()
            print("  Core components active. Consider enabling:")
            if not tts_status:
                print("    ❌ Coqui TTS - Set 'coqui_tts.enabled': true")
            if not mem_status:
                print("    ❌ MemGPT - Set 'memgpt.enabled': true")
        else:
            print(f"  Status:               ❌ {integration_percentage:.0f}% "
                  "Integration")
            print()
            print("  Critical components missing. Check initialization logs.")
        
        print()
        print("=" * 70)
        
        # Test basic request processing
        print()
        print("🧪 Testing Request Processing...")
        print("-" * 70)
        
        try:
            response = await system.process_user_request(
                "Hello, what is your purpose?",
                user_id="test_user"
            )
            print("✅ Request processing successful")
            print(f"   Response preview: {response[:100]}...")
            print()
        except Exception as e:
            print(f"❌ Request processing failed: {e}")
            print()
        
        print("-" * 70)
        
        # Shutdown
        print()
        print("🛑 Shutting down system...")
        await system.shutdown()
        print("✅ System shutdown complete")
        print()
        
        print("=" * 70)
        print("VERIFICATION COMPLETE")
        print("=" * 70)
        
        return integration_percentage == 100
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def quick_health_check():
    """Quick health check without full initialization"""
    print()
    print("⚡ Quick Health Check")
    print("-" * 70)
    
    # Check imports
    print("Checking module imports...")
    
    try:
        from core.engines.ollama_integration import OllamaIntegration
        print("  ✅ Ollama integration")
    except ImportError as e:
        print(f"  ❌ Ollama integration: {e}")
    
    try:
        from core.engines.llama_cpp_optimizer import LlamaCppOptimizer
        print("  ✅ Llama.cpp optimizer")
    except ImportError as e:
        print(f"  ❌ Llama.cpp optimizer: {e}")
    
    try:
        from core.engines.terminalbench_integration import (
            TerminalBenchIntegration
        )
        print("  ✅ TerminalBench integration")
    except ImportError as e:
        print(f"  ❌ TerminalBench integration: {e}")
    
    try:
        from core.engines.coqui_tts_optimizer import CoquiTTSOptimizer
        print("  ✅ Coqui TTS optimizer")
    except ImportError as e:
        print(f"  ❌ Coqui TTS optimizer: {e}")
    
    try:
        from core.engines.memgpt_autogen_integration import MemGPTIntegration
        print("  ✅ MemGPT integration")
    except ImportError as e:
        print(f"  ❌ MemGPT integration: {e}")
    
    print()
    print("-" * 70)


def main():
    """Main verification entry point"""
    print()
    print("🚀 Starting Universal Soul AI Integration Verification")
    print()
    
    # Quick health check first
    asyncio.run(quick_health_check())
    
    # Full verification
    success = asyncio.run(verify_integration())
    
    if success:
        print()
        print("✅ All systems operational - ready for use!")
        print()
        sys.exit(0)
    else:
        print()
        print("⚠️  Partial integration - review logs for details")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
