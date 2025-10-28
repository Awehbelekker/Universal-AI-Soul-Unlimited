"""
Data Structures for Universal Soul AI
=====================================

Core data structures and context objects used throughout the system.
"""

import time
import uuid
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class PersonalityMode(Enum):
    """Available personality modes"""
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    ENERGETIC = "energetic"
    CALM = "calm"
    CREATIVE = "creative"
    ANALYTICAL = "analytical"


class UserRole(Enum):
    """User role types"""
    INDIVIDUAL = "individual"
    FAMILY_MEMBER = "family_member"
    PARENT = "parent"
    CHILD = "child"
    ADMINISTRATOR = "administrator"


@dataclass
class UserContext:
    """User context information"""
    user_id: str
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    personality_mode: PersonalityMode = PersonalityMode.FRIENDLY
    role: UserRole = UserRole.INDIVIDUAL
    preferences: Dict[str, Any] = field(default_factory=dict)
    values_profile: Optional[Dict[str, Any]] = None
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    
    def update_activity(self) -> None:
        """Update last activity timestamp"""
        self.last_active = datetime.now()


@dataclass
class VoiceConfig:
    """Voice processing configuration"""
    language: str = "en-US"
    voice_id: Optional[str] = None
    speed: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0
    provider: str = "local"
    model: Optional[str] = None
    quality: str = "standard"  # standard, high, premium
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "language": self.language,
            "voice_id": self.voice_id,
            "speed": self.speed,
            "pitch": self.pitch,
            "volume": self.volume,
            "provider": self.provider,
            "model": self.model,
            "quality": self.quality
        }


@dataclass
class PersonalityContext:
    """Context for personality processing"""
    mode: PersonalityMode
    intensity: float = 1.0  # 0.0 to 1.0
    user_context: Optional[UserContext] = None
    conversation_state: Dict[str, Any] = field(default_factory=dict)
    emotional_state: Optional[str] = None
    
    def apply_intensity(self, base_response: str) -> str:
        """Apply personality intensity to response"""
        # This would be implemented with actual personality logic
        return base_response


@dataclass
class ValuesContext:
    """Context for values-based processing"""
    user_id: str
    values_profile: Dict[str, Any] = field(default_factory=dict)
    family_values: Dict[str, Any] = field(default_factory=dict)
    current_assessment: Optional[Dict[str, Any]] = None
    privacy_level: str = "high"  # low, medium, high, maximum
    
    def get_core_values(self) -> List[str]:
        """Get list of core values"""
        return self.values_profile.get("core_values", [])
    
    def get_family_priorities(self) -> Dict[str, Any]:
        """Get family priority settings"""
        return self.family_values.get("priorities", {})


@dataclass
class AutomationTask:
    """Automation task definition"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    task_type: str = "general"
    complexity: float = 1.0  # 0.0 to 10.0
    priority: int = 5  # 1-10
    platform: str = "universal"
    requirements: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    estimated_duration: Optional[float] = None
    success_criteria: List[str] = field(default_factory=list)
    
    def is_complex(self) -> bool:
        """Check if task is complex (>5.0 complexity)"""
        return self.complexity > 5.0
    
    def get_timeout(self) -> int:
        """Get timeout in seconds based on complexity"""
        base_timeout = 30
        return int(base_timeout * (1 + self.complexity / 10))


@dataclass
class SystemMetrics:
    """System performance metrics"""
    timestamp: datetime = field(default_factory=datetime.now)
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    response_time: float = 0.0
    success_rate: float = 0.0
    active_sessions: int = 0
    total_requests: int = 0
    errors: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "response_time": self.response_time,
            "success_rate": self.success_rate,
            "active_sessions": self.active_sessions,
            "total_requests": self.total_requests,
            "errors": self.errors
        }


@dataclass
class OnboardingState:
    """User onboarding state"""
    user_id: str
    current_step: str = "welcome"
    completed_steps: List[str] = field(default_factory=list)
    step_data: Dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_complete: bool = False
    
    ONBOARDING_STEPS = [
        "welcome",
        "privacy_setup",
        "personality_selection",
        "values_assessment",
        "preferences_setup",
        "voice_setup",
        "final_confirmation"
    ]
    
    def complete_step(self, step: str, data: Dict[str, Any]) -> None:
        """Complete an onboarding step"""
        if step not in self.completed_steps:
            self.completed_steps.append(step)
        self.step_data[step] = data
        self.updated_at = datetime.now()
        
        # Check if onboarding is complete
        if len(self.completed_steps) >= len(self.ONBOARDING_STEPS):
            self.is_complete = True
    
    def get_progress(self) -> float:
        """Get onboarding progress percentage"""
        return len(self.completed_steps) / len(self.ONBOARDING_STEPS)
    
    def get_next_step(self) -> Optional[str]:
        """Get next onboarding step"""
        for step in self.ONBOARDING_STEPS:
            if step not in self.completed_steps:
                return step
        return None


@dataclass
class HRMRequest:
    """Hierarchical Reasoning Model request"""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_input: str = ""
    context: UserContext = None
    reasoning_depth: int = 3  # 1-5 levels
    use_values: bool = True
    use_personality: bool = True
    priority: int = 5
    timeout: int = 30
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "request_id": self.request_id,
            "user_input": self.user_input,
            "reasoning_depth": self.reasoning_depth,
            "use_values": self.use_values,
            "use_personality": self.use_personality,
            "priority": self.priority,
            "timeout": self.timeout,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class HRMResponse:
    """Hierarchical Reasoning Model response"""
    request_id: str
    response_text: str = ""
    reasoning_chain: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    processing_time: float = 0.0
    tokens_used: int = 0
    model_version: str = "1.0"
    created_at: datetime = field(default_factory=datetime.now)
    
    def add_reasoning_step(self, step: str, result: Any, 
                          confidence: float = 1.0) -> None:
        """Add a reasoning step"""
        self.reasoning_chain.append({
            "step": step,
            "result": result,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "request_id": self.request_id,
            "response_text": self.response_text,
            "reasoning_chain": self.reasoning_chain,
            "confidence": self.confidence,
            "processing_time": self.processing_time,
            "tokens_used": self.tokens_used,
            "model_version": self.model_version,
            "created_at": self.created_at.isoformat()
        }