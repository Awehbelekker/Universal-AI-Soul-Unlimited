"""
Base Interfaces for Universal Soul AI
=====================================

Core abstract interfaces that all Universal Soul AI components implement.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from enum import Enum

# Status Enums
class ComponentStatus(Enum):
    """Component status enumeration"""
    INITIALIZING = "initializing"
    READY = "ready"
    PROCESSING = "processing"
    ERROR = "error"
    DISABLED = "disabled"

class HealthStatus(Enum):
    """Health status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class IAIEngine(ABC):
    """Abstract interface for AI engines"""
    
    @abstractmethod
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Initialize the AI engine"""
        pass
    
    @abstractmethod
    async def process_request(self, request: str, context: 'UserContext') -> str:
        """Process a user request and return response"""
        pass
    
    @abstractmethod
    async def get_capabilities(self) -> List[str]:
        """Get list of engine capabilities"""
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the engine"""
        pass


class IAutomationEngine(ABC):
    """Abstract interface for automation engines"""
    
    @abstractmethod
    async def execute_task(self, task: 'AutomationTask', context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an automation task"""
        pass
    
    @abstractmethod
    async def analyze_task_complexity(self, task: str) -> Dict[str, Any]:
        """Analyze task complexity and requirements"""
        pass
    
    @abstractmethod
    async def get_success_rate(self) -> float:
        """Get current success rate"""
        pass


class IVoiceProcessor(ABC):
    """Abstract interface for voice processing"""
    
    @abstractmethod
    async def text_to_speech(self, text: str, config: 'VoiceConfig') -> bytes:
        """Convert text to speech"""
        pass
    
    @abstractmethod
    async def speech_to_text(self, audio_data: bytes, config: 'VoiceConfig') -> str:
        """Convert speech to text"""
        pass
    
    @abstractmethod
    async def detect_voice_activity(self, audio_data: bytes) -> bool:
        """Detect voice activity in audio"""
        pass


class IPersonalityEngine(ABC):
    """Abstract interface for personality systems"""
    
    @abstractmethod
    async def apply_personality(self, text: str, context: 'PersonalityContext') -> str:
        """Apply personality to text response"""
        pass
    
    @abstractmethod
    async def get_personality_modes(self) -> List[str]:
        """Get available personality modes"""
        pass
    
    @abstractmethod
    async def set_personality_mode(self, mode: str) -> bool:
        """Set current personality mode"""
        pass


class IValuesEngine(ABC):
    """Abstract interface for values-based processing"""
    
    @abstractmethod
    async def assess_values_alignment(self, content: str, context: 'ValuesContext') -> Dict[str, Any]:
        """Assess how well content aligns with user values"""
        pass
    
    @abstractmethod
    async def get_values_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user's values profile"""
        pass
    
    @abstractmethod
    async def conduct_values_assessment(self, user_id: str) -> Dict[str, Any]:
        """Conduct interactive values assessment"""
        pass


class IOnboardingSystem(ABC):
    """Abstract interface for user onboarding"""
    
    @abstractmethod
    async def start_onboarding(self, user_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Start user onboarding process"""
        pass
    
    @abstractmethod
    async def get_onboarding_status(self, user_id: str) -> Dict[str, Any]:
        """Get onboarding status for user"""
        pass
    
    @abstractmethod
    async def complete_onboarding_step(self, user_id: str, step: str, data: Dict[str, Any]) -> bool:
        """Complete a specific onboarding step"""
        pass


class IHealthCheck(ABC):
    """Abstract interface for health monitoring"""
    
    @abstractmethod
    async def check_health(self) -> HealthStatus:
        """Check component health"""
        pass
    
    @abstractmethod
    async def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        pass
    
    @abstractmethod
    async def get_dependencies(self) -> List[str]:
        """Get list of dependencies"""
        pass


class IContainer(ABC):
    """Abstract interface for dependency injection container"""
    
    @abstractmethod
    def register(self, interface: type, implementation: type, singleton: bool = True) -> None:
        """Register an implementation for an interface"""
        pass
    
    @abstractmethod
    def register_instance(self, interface: type, instance: Any) -> None:
        """Register a specific instance"""
        pass
    
    @abstractmethod
    def get(self, interface: type) -> Any:
        """Get implementation for interface"""
        pass
    
    @abstractmethod
    def resolve(self, target_type: type) -> Any:
        """Resolve all dependencies for target type"""
        pass