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
from typing import Dict, Any, Optional, Callable

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
from core.routing.task_router import classify_request

# Set up logging first
Path("logs").mkdir(parents=True, exist_ok=True)
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

try:
    from core.thinkmesh_engine.adapter import ThinkMeshAdapter
    THINKMESH_AVAILABLE = True
except ImportError:
    THINKMESH_AVAILABLE = False
    logger.warning("ThinkMesh adapter not available")

try:
    from thinkmesh_core.voice.voice_pipeline import VoicePipeline
    THINKMESH_VOICE_AVAILABLE = True
except ImportError:
    THINKMESH_VOICE_AVAILABLE = False


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
        self.thinkmesh_adapter: Optional['ThinkMeshAdapter'] = None
        self.voice_pipeline = None
        
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
            logger.info("HRM Engine: %s", "OK" if self.hrm_engine else "MISSING")
            logger.info("CoAct-1 Engine: %s", "OK" if self.coact_engine else "MISSING")
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
        context: Optional[Dict[str, Any]] = None,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Process a user request through the complete system"""
        if not self.is_initialized:
            await self.initialize()
        
        start_time = asyncio.get_event_loop().time()
        self.system_metrics["total_requests"] += 1
        
        try:
            # Get or create user context
            user_context = await self._get_user_context(user_id, context)
            self._update_values_from_message(user_context, user_input)
            
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
            
            # Adaptive routing: fast / standard / deep inference
            route = classify_request(
                user_input,
                has_memory_context=bool(memory_context),
                adaptive=self.config.hrm.adaptive_reasoning,
                default_depth=self.config.hrm.reasoning_depth,
                max_depth=self.config.hrm.max_reasoning_depth,
                fast_tokens=self.config.hrm.layer_max_tokens,
                deep_tokens=self.config.hrm.deep_layer_max_tokens,
            )
            logger.info(
                "Route: %s (depth=%s, tokens=%s)",
                route.mode.value,
                route.reasoning_depth,
                route.max_tokens,
            )

            hrm_input = user_input
            values_context = self._format_values_context(user_context)
            if values_context:
                hrm_input = f"{values_context}\n{hrm_input}"
            if memory_context:
                hrm_input = (
                    f"[Memory Context: {memory_context}]\n"
                    f"User: {user_input}"
                )

            if route.use_thinkmesh:
                await self._ensure_thinkmesh()
                if self.thinkmesh_adapter:
                    think = await self.thinkmesh_adapter.think(user_input)
                    hrm_input = (
                        f"[Analysis: {think.content}]\n{hrm_input}"
                    )

            ai_response = await self.hrm_engine.process_request(
                hrm_input,
                user_context,
                reasoning_depth=route.reasoning_depth,
                max_tokens=route.max_tokens,
                on_token=on_token,
            )

            automation_result = None
            if route.use_automation:
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
                    PersonalityMode.CALM: "calm",
                    PersonalityMode.ENERGETIC: "energetic",
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
                "thinkmesh_enabled": self.thinkmesh_adapter is not None,
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
        self.hrm_engine = self.container.get(IAIEngine)
        if hasattr(self.hrm_engine, 'initialize'):
            init_result = self.hrm_engine.initialize()
            if asyncio.iscoroutine(init_result):
                await init_result
        logger.info("HRM Engine initialized")

        self.coact_engine = self.container.get(IAutomationEngine)
        if hasattr(self.coact_engine, 'initialize'):
            init_result = self.coact_engine.initialize()
            if asyncio.iscoroutine(init_result):
                await init_result
        logger.info("CoAct-1 Engine initialized")

        if COQUI_TTS_AVAILABLE and self.config.coqui_tts.enabled:
            try:
                self.tts_engine = CoquiTTSOptimizer(
                    model_name=self.config.coqui_tts.model,
                    use_gpu=self.config.coqui_tts.use_gpu,
                )
                await self.tts_engine.initialize()
                logger.info("Coqui TTS optimizer initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize TTS: {e}")

        if MEMGPT_AVAILABLE and self.config.memgpt.enabled:
            try:
                storage = Path(self.config.memgpt.storage_path)
                self.memory_engine = MemGPTIntegration(storage_path=storage)
                logger.info("MemGPT memory engine initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize MemGPT: {e}")

        if THINKMESH_AVAILABLE:
            logger.info("ThinkMesh adapter available (lazy init on deep tasks)")

        if THINKMESH_VOICE_AVAILABLE:
            try:
                self.voice_pipeline = VoicePipeline()
                await self.voice_pipeline.initialize()
                self.voice_service = self.voice_pipeline
                logger.info("ThinkMesh voice pipeline initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize voice pipeline: {e}")

        logger.info("Core engines initialized successfully")
    
    async def _ensure_thinkmesh(self) -> None:
        """Lazy-init ThinkMesh for deep reasoning tasks only."""
        if self.thinkmesh_adapter or not THINKMESH_AVAILABLE:
            return
        try:
            self.thinkmesh_adapter = ThinkMeshAdapter()
            await self.thinkmesh_adapter.initialize()
            logger.info(
                "ThinkMesh adapter ready (local=%s)",
                self.thinkmesh_adapter.uses_local_core,
            )
        except Exception as e:
            logger.warning("ThinkMesh init failed: %s", e)

    async def _initialize_services(self) -> None:
        """Initialize system services"""
        logger.info("Services initialization complete")

    async def _setup_integrations(self) -> None:
        """Setup integration points between services"""
        if self.thinkmesh_adapter and self.hrm_engine:
            logger.info("ThinkMesh <-> HRM integration active")
        if self.voice_pipeline and self.tts_engine:
            self.voice_pipeline.attach_tts_engine(self.tts_engine)
        logger.info("Service integrations setup complete")
    
    async def _validate_system_health(self) -> None:
        """Validate system health after initialization"""
        if not self.hrm_engine:
            raise InitializationError("HRM Engine not initialized", "HRM_MISSING")

        if not self.coact_engine:
            raise InitializationError("CoAct-1 Engine not initialized", "COACT_MISSING")

        try:
            if self.config.hrm.light_health_check:
                backend = getattr(self.hrm_engine, "backend", None)
                if backend and hasattr(backend, "health_check"):
                    health = await backend.health_check()
                    if health.get("status") != "healthy":
                        raise InitializationError(
                            f"Ollama unhealthy: {health.get('error', 'unknown')}",
                            "HRM_HEALTH_FAIL",
                        )
                logger.info("Light health check passed (backend ping)")
            else:
                test_context = UserContext(
                    user_id="health_check",
                    personality_mode=PersonalityMode.FRIENDLY,
                    role=UserRole.INDIVIDUAL,
                )
                hrm_response = await self.hrm_engine.process_request(
                    "Health check",
                    test_context,
                    reasoning_depth=1,
                    max_tokens=32,
                )
                if not hrm_response:
                    raise InitializationError(
                        "HRM Engine health check failed", "HRM_HEALTH_FAIL"
                    )
                logger.info("Full health check passed")

        except InitializationError:
            raise
        except Exception as e:
            raise InitializationError(
                f"System health validation failed: {e}", "HEALTH_CHECK_FAILED"
            )
    
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
        return response

    def _update_values_from_message(
        self, user_context: UserContext, user_input: str
    ) -> None:
        """Capture values and boundaries the user states in conversation."""
        lw = user_input.lower()
        triggers = (
            "value", "values", "boundary", "boundaries", "principle",
            "lay down", "laydown", "ground rule", "what matters",
            "structure bound", "our rules", "i believe", "i care about",
            "don't discuss", "do not discuss", "off limits", "never ask",
        )
        if not any(t in lw for t in triggers):
            return

        if user_context.values_profile is None:
            user_context.values_profile = {
                "core_values": [],
                "boundaries": [],
                "notes": [],
                "source": "conversation",
            }

        profile = user_context.values_profile
        notes = profile.setdefault("notes", [])
        notes.append(user_input.strip())
        profile["notes"] = notes[-20:]

        for line in user_input.replace(";", "\n").split("\n"):
            stripped = line.strip()
            low = stripped.lower()
            if not stripped:
                continue
            if any(
                low.startswith(p)
                for p in ("i value ", "my values are ", "values: ")
            ):
                text = stripped.split(":", 1)[-1].strip()
                for part in text.replace(" and ", ",").split(","):
                    val = part.strip()
                    if val and val not in profile["core_values"]:
                        profile["core_values"].append(val)
            if any(
                low.startswith(p)
                for p in (
                    "boundary:", "boundaries:", "my boundary is ",
                    "don't ", "do not ", "never ",
                )
            ):
                if stripped not in profile["boundaries"]:
                    profile["boundaries"].append(stripped)

    def _format_values_context(self, user_context: UserContext) -> str:
        """Build a prompt prefix from the user's values profile."""
        profile = user_context.values_profile
        if not profile:
            return ""

        lines = [
            "[User values & boundaries — honor these in every reply:]",
        ]
        core = profile.get("core_values") or []
        bounds = profile.get("boundaries") or []
        if core:
            lines.append("Core values: " + "; ".join(core))
        if bounds:
            lines.append("Boundaries: " + "; ".join(bounds))
        recent = profile.get("notes") or []
        if recent:
            lines.append("Recent context: " + recent[-1])
        lines.append(
            "If the user asks about values or boundaries, confirm what you "
            "remember and invite them to add or refine rules together."
        )
        return "\n".join(lines)
    
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
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("core.engines.ollama_integration").setLevel(
            logging.WARNING
        )

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
                
                # Process user request (stream tokens when Ollama is active)
                print("\nUniversal Soul AI: ", end="", flush=True)
                streamed = False

                def _print_token(token: str) -> None:
                    nonlocal streamed
                    streamed = True
                    print(token, end="", flush=True)

                response = await soul_ai.process_user_request(
                    user_input, on_token=_print_token
                )
                if not streamed:
                    if response:
                        print(response, end="")
                    else:
                        print("(no response)")
                print()
                
            except KeyboardInterrupt:
                break
            except EOFError:
                print("\n(No input — exiting.)")
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