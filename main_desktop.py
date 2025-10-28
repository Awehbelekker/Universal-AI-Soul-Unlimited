"""
Main Universal Soul AI System
=============================

Main entry point and orchestration for the complete Universal Soul AI system.
Integrates HRM engine, CoAct-1 automation, personality, values, and all
components.

Enhanced with:
- Qwen2.5-3B AI inference (Ollama)
- TerminalBench multi-agent automation
- Coqui TTS personality voices
- MemGPT long-term memory
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Core imports
from core.config import ConfigManager
from core.container import get_container, register_service
from core.interfaces.base_interfaces import (
    IAIEngine, IAutomationEngine
)
from core.interfaces.data_structures import (
    UserContext, PersonalityMode, UserRole
)
from core.interfaces.exceptions import InitializationError

# Core Engine imports
from core.engines.hrm_engine import HRMEngine
from core.engines.coact_engine import CoAct1AutomationEngine

# Set up logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/universal_soul_ai.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Optimization Engine imports
try:
    from core.engines.coqui_tts_optimizer import CoquiTTSOptimizer
    COQUI_TTS_AVAILABLE = True
except ImportError:
    COQUI_TTS_AVAILABLE = False
    logger.warning("Coqui TTS not available")

try:
    from core.engines.memgpt_autogen_integration import MemGPTIntegration
    MEMGPT_AVAILABLE = True
except ImportError:
    MEMGPT_AVAILABLE = False
    logger.warning("MemGPT/AutoGEN not available")


class UniversalSoulAI:
    """Main Universal Soul AI System Orchestrator"""
    
    def __init__(self, config_path: str = "config/universal_soul.json"):
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.get_config()
        self.container = get_container()
        
        # Core engines
        self.hrm_engine: Optional[HRMEngine] = None
        self.coact_engine: Optional[CoAct1AutomationEngine] = None
        
        # Optimization engines
        self.tts_engine: Optional['CoquiTTSOptimizer'] = None
        self.memory_engine: Optional['MemGPTIntegration'] = None
        
        # Service references (will be injected)
        self.personality_service = None
        self.values_service = None
        self.onboarding_service = None
        self.voice_service = None
        
        # System state
        self.is_initialized = False
        self.active_sessions = {}
        self.system_metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "average_response_time": 0.0,
            "active_users": 0
        }
    
    async def initialize(self) -> bool:
        """Initialize the complete Universal Soul AI system"""
        try:
            logger.info("Starting Universal Soul AI initialization...")
            
            # Create required directories
            await self._create_directories()
            
            # Register core services
            await self._register_services()
            
            # Initialize core engines
            await self._initialize_engines()
            
            # Initialize services
            await self._initialize_services()
            
            # Setup integration points
            await self._setup_integrations()
            
            # Validate system health
            await self._validate_system_health()
            
            self.is_initialized = True
            logger.info("Universal Soul AI initialization complete!")
            logger.info(f"HRM Engine: {'✓' if self.hrm_engine else '✗'}")
            logger.info(f"CoAct-1 Engine: {'✓' if self.coact_engine else '✗'}")
            logger.info("System ready for user requests")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Universal Soul AI: {e}")
            raise InitializationError(
                f"System initialization failed: {str(e)}",
                "SYSTEM_INIT_FAILED"
            )
    
    async def process_user_request(
        self,
        user_input: str,
        user_id: str = "default",
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Process a user request through the complete system"""
        if not self.is_initialized:
            await self.initialize()
        
        start_time = asyncio.get_event_loop().time()
        self.system_metrics["total_requests"] += 1
        
        try:
            # Get or create user context
            user_context = await self._get_user_context(user_id, context)
            
            # Recall relevant memories (MemGPT)
            memory_context = None
            if self.memory_engine:
                memory_context = await self.memory_engine.recall_memory(
                    user_id, user_input
                )
            
            # Check if user needs onboarding
            if self.onboarding_service and not user_context.values_profile:
                onboarding_needed = await self._check_onboarding_status(
                    user_id
                )
                if onboarding_needed:
                    return await self._handle_onboarding(
                        user_id, user_input
                    )
            
            # Process through HRM engine (with memory context)
            hrm_input = user_input
            if memory_context:
                hrm_input = (
                    f"[Memory Context: {memory_context}]\n"
                    f"User: {user_input}"
                )
            
            ai_response = await self.hrm_engine.process_request(
                hrm_input, user_context
            )
            
            # Check if automation is needed
            automation_result = await self._check_automation_needs(
                user_input, ai_response, user_context
            )
            
            if automation_result:
                ai_response = await self._integrate_automation_result(
                    ai_response, automation_result
                )
            
            # Apply personality and values
            final_response = await self._apply_personality_and_values(
                ai_response, user_context
            )
            
            # Store interaction in memory (MemGPT)
            if self.memory_engine:
                await self.memory_engine.store_interaction(
                    user_id, user_input, final_response
                )
            
            # Synthesize voice response (TTS)
            if self.tts_engine and user_context.personality_mode:
                personality_map = {
                    PersonalityMode.PROFESSIONAL: "professional",
                    PersonalityMode.FRIENDLY: "friendly",
                    PersonalityMode.EMPATHETIC: "calm",
                    PersonalityMode.ENTHUSIASTIC: "energetic",
                }
                personality = personality_map.get(
                    user_context.personality_mode, "professional"
                )
                
                try:
                    audio_path = await self.tts_engine.synthesize(
                        final_response, personality
                    )
                    logger.info(f"Voice response saved: {audio_path}")
                except Exception as e:
                    logger.warning(f"TTS synthesis failed: {e}")
            
            # Update metrics
            processing_time = asyncio.get_event_loop().time() - start_time
            self.system_metrics["successful_requests"] += 1
            self._update_response_time(processing_time)
            
            # Update user context
            await self._update_user_context(
                user_context, user_input, final_response
            )
            
            return final_response
            
        except Exception as e:
            processing_time = asyncio.get_event_loop().time() - start_time
            self._update_response_time(processing_time)
            
            logger.error(f"Error processing user request: {e}")
            return (
                "I apologize, but I encountered an error processing "
                "your request. Please try again."
            )
    
    async def shutdown(self) -> None:
        """Shutdown the Universal Soul AI system"""
        logger.info("Shutting down Universal Soul AI system...")
        
        try:
            # Shutdown engines
            if self.hrm_engine:
                await self.hrm_engine.shutdown()
            
            if self.coact_engine:
                # CoAct engine doesn't have shutdown method in interface
                pass
            
            # Save user contexts and system state
            await self._save_system_state()
            
            # Clear container
            self.container.clear()
            
            self.is_initialized = False
            logger.info("Universal Soul AI shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        hrm_metrics = {}
        coact_metrics = {}
        
        if self.hrm_engine:
            if hasattr(self.hrm_engine, 'get_performance_metrics'):
                hrm_metrics = self.hrm_engine.get_performance_metrics()
        
        if self.coact_engine:
            if hasattr(self.coact_engine, 'get_performance_metrics'):
                coact_metrics = self.coact_engine.get_performance_metrics()
        
        return {
            "system_initialized": self.is_initialized,
            "active_sessions": len(self.active_sessions),
            "system_metrics": self.system_metrics,
            "hrm_engine": hrm_metrics,
            "coact_engine": coact_metrics,
            "config_version": self.config.config_version,
            "optimization_engines": {
                "tts_enabled": self.tts_engine is not None,
                "memory_enabled": self.memory_engine is not None,
            },
            "services_status": {
                "personality": self.personality_service is not None,
                "values": self.values_service is not None,
                "onboarding": self.onboarding_service is not None,
                "voice": self.voice_service is not None
            }
        }
    
    # Private methods
    
    async def _create_directories(self) -> None:
        """Create required directories"""
        directories = [
            self.config.data_directory,
            self.config.models_directory,
            self.config.cache_directory,
            self.config.logs_directory,
            "config"
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    async def _register_services(self) -> None:
        """Register all services in the dependency injection container"""
        # Register engines
        register_service(IAIEngine, HRMEngine)
        register_service(IAutomationEngine, CoAct1AutomationEngine)
        
        # TODO: Register other services when implemented
        # register_service(IPersonalityEngine, PersonalityService)
        # register_service(IValuesEngine, ValuesService)
        # register_service(IOnboardingSystem, OnboardingService)
        # register_service(IVoiceProcessor, VoiceService)
    
    async def _initialize_engines(self) -> None:
        """Initialize core AI engines and optimizers"""
        # Initialize HRM engine with Ollama + Qwen2.5-3B
        self.hrm_engine = self.container.get(IAIEngine)
        if hasattr(self.hrm_engine, 'initialize'):
            init_result = self.hrm_engine.initialize()
            if asyncio.iscoroutine(init_result):
                await init_result
        
        logger.info("HRM Engine initialized with Ollama backend")
        
        # Initialize CoAct-1 automation engine with TerminalBench
        self.coact_engine = self.container.get(IAutomationEngine)
        if hasattr(self.coact_engine, 'initialize'):
            init_result = self.coact_engine.initialize()
            if asyncio.iscoroutine(init_result):
                await init_result
        
        logger.info("CoAct-1 Engine initialized with TerminalBench")
        
        # Initialize Coqui TTS optimizer (if enabled)
        if COQUI_TTS_AVAILABLE and hasattr(self.config, 'coqui_tts'):
            if self.config.coqui_tts.get('enabled', False):
                try:
                    self.tts_engine = CoquiTTSOptimizer(self.config.coqui_tts)
                    logger.info(
                        "Coqui TTS optimizer initialized "
                        "with 6 personalities"
                    )
                except Exception as e:
                    logger.warning(f"Failed to initialize TTS: {e}")
        
        # Initialize MemGPT/AutoGEN integration (if enabled)
        if MEMGPT_AVAILABLE and hasattr(self.config, 'memgpt'):
            if self.config.memgpt.get('enabled', False):
                try:
                    self.memory_engine = MemGPTIntegration(self.config.memgpt)
                    logger.info("MemGPT memory engine initialized")
                except Exception as e:
                    logger.warning(f"Failed to initialize MemGPT: {e}")
            if asyncio.iscoroutine(init_result):
                await init_result
        
        # Initialize CoAct-1 engine
        self.coact_engine = self.container.get(IAutomationEngine)
        if hasattr(self.coact_engine, 'initialize'):
            init_result = self.coact_engine.initialize()
            if asyncio.iscoroutine(init_result):
                await init_result
        
        logger.info("Core engines initialized successfully")
    
    async def _initialize_services(self) -> None:
        """Initialize system services"""
        # TODO: Initialize services when implemented
        # self.personality_service = self.container.get(IPersonalityEngine)
        # self.values_service = self.container.get(IValuesEngine)
        # self.onboarding_service = self.container.get(IOnboardingSystem)
        # self.voice_service = self.container.get(IVoiceProcessor)
        
        logger.info("Services initialization complete (placeholder)")
    
    async def _setup_integrations(self) -> None:
        """Setup integration points between services"""
        # TODO: Setup service integrations
        logger.info("Service integrations setup complete (placeholder)")
    
    async def _validate_system_health(self) -> None:
        """Validate system health after initialization"""
        if not self.hrm_engine:
            raise InitializationError("HRM Engine not initialized", "HRM_MISSING")
        
        if not self.coact_engine:
            raise InitializationError("CoAct-1 Engine not initialized", "COACT_MISSING")
        
        # Test basic functionality
        test_context = UserContext(
            user_id="health_check",
            personality_mode=PersonalityMode.FRIENDLY,
            role=UserRole.INDIVIDUAL
        )
        
        try:
            # Test HRM engine
            hrm_response = await self.hrm_engine.process_request(
                "Health check test", test_context
            )
            if not hrm_response:
                raise InitializationError("HRM Engine health check failed", "HRM_HEALTH_FAIL")
            
            # Test CoAct engine
            from core.interfaces.data_structures import AutomationTask
            test_task = AutomationTask(description="Health check automation test")
            coact_result = await self.coact_engine.execute_task(test_task, {})
            # CoAct engine returns dict, so we just check if it executed
            
            logger.info("System health validation passed")
            
        except Exception as e:
            raise InitializationError(f"System health validation failed: {e}", "HEALTH_CHECK_FAILED")
    
    async def _get_user_context(self, user_id: str, 
                              context: Optional[Dict[str, Any]]) -> UserContext:
        """Get or create user context"""
        if user_id in self.active_sessions:
            user_context = self.active_sessions[user_id]
            user_context.update_activity()
            return user_context
        
        # Create new user context
        user_context = UserContext(
            user_id=user_id,
            personality_mode=PersonalityMode.FRIENDLY,
            role=UserRole.INDIVIDUAL
        )
        
        if context:
            user_context.preferences.update(context)
        
        self.active_sessions[user_id] = user_context
        self.system_metrics["active_users"] = len(self.active_sessions)
        
        return user_context
    
    async def _check_onboarding_status(self, user_id: str) -> bool:
        """Check if user needs onboarding"""
        # TODO: Implement onboarding status check
        return False  # Placeholder
    
    async def _handle_onboarding(self, user_id: str, user_input: str) -> str:
        """Handle user onboarding process"""
        # TODO: Implement onboarding handling
        return "Welcome! Let's get you set up with Universal Soul AI."
    
    async def _check_automation_needs(self, user_input: str, ai_response: str,
                                    user_context: UserContext) -> Optional[Dict[str, Any]]:
        """Check if automation is needed for the request"""
        # Simple automation trigger detection
        automation_keywords = [
            "automate", "schedule", "remind", "execute", "perform",
            "run", "launch", "start", "complete", "finish"
        ]
        
        if any(keyword in user_input.lower() for keyword in automation_keywords):
            from core.interfaces.data_structures import AutomationTask
            
            task = AutomationTask(
                description=user_input,
                task_type="user_request",
                platform="universal_soul_ai"
            )
            
            try:
                result = await self.coact_engine.execute_task(task, {
                    "user_context": user_context.to_dict() if hasattr(user_context, 'to_dict') else {},
                    "ai_response": ai_response
                })
                return result
            except Exception as e:
                logger.error(f"Automation execution failed: {e}")
                return None
        
        return None
    
    async def _integrate_automation_result(self, ai_response: str, 
                                         automation_result: Dict[str, Any]) -> str:
        """Integrate automation results with AI response"""
        if automation_result.get("success"):
            return f"{ai_response}\n\nAutomation completed successfully!"
        else:
            error_msg = automation_result.get("error_message", "Unknown error")
            return f"{ai_response}\n\nAutomation encountered an issue: {error_msg}"
    
    async def _apply_personality_and_values(self, response: str, 
                                          user_context: UserContext) -> str:
        """Apply personality and values to the response"""
        # TODO: Implement personality and values application
        # For now, just return the response with personality indicator
        personality = user_context.personality_mode.value
        return f"[{personality.title()} mode] {response}"
    
    async def _update_user_context(self, user_context: UserContext, 
                                 user_input: str, ai_response: str) -> None:
        """Update user context with conversation history"""
        user_context.conversation_history.append({
            "timestamp": asyncio.get_event_loop().time(),
            "user_input": user_input,
            "ai_response": ai_response
        })
        
        # Keep only last 50 conversations to manage memory
        if len(user_context.conversation_history) > 50:
            user_context.conversation_history = user_context.conversation_history[-50:]
    
    async def _save_system_state(self) -> None:
        """Save system state and user contexts"""
        # TODO: Implement state persistence
        logger.info("System state saved (placeholder)")
    
    def _update_response_time(self, processing_time: float) -> None:
        """Update average response time metric"""
        total_requests = self.system_metrics["total_requests"]
        if total_requests > 0:
            current_avg = self.system_metrics["average_response_time"]
            new_avg = ((current_avg * (total_requests - 1)) + processing_time) / total_requests
            self.system_metrics["average_response_time"] = new_avg


# Main execution
async def main():
    """Main entry point for Universal Soul AI"""
    try:
        # Create Universal Soul AI instance
        soul_ai = UniversalSoulAI()
        
        # Initialize system
        await soul_ai.initialize()
        
        # Interactive mode for testing
        print("\nUniversal Soul AI - Interactive Mode")
        print("Type 'quit' to exit, 'status' for system status")
        print("-" * 50)
        
        while True:
            try:
                user_input = input("\nYou: ").strip()
                
                if user_input.lower() in ['quit', 'exit']:
                    break
                elif user_input.lower() == 'status':
                    status = await soul_ai.get_system_status()
                    print(f"\nSystem Status: {status}")
                    continue
                elif not user_input:
                    continue
                
                # Process user request
                response = await soul_ai.process_user_request(user_input)
                print(f"\nUniversal Soul AI: {response}")
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\nError: {e}")
        
        # Shutdown system
        await soul_ai.shutdown()
        print("\nGoodbye!")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Run the main application
    asyncio.run(main())