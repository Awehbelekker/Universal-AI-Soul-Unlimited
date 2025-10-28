"""
Universal Soul AI - Core Interfaces
===================================

Complete interface definitions for the unified Universal Soul AI system.
All components implement these interfaces for seamless integration.
"""

from .base_interfaces import (
    IAIEngine,
    IAutomationEngine,
    IVoiceProcessor,
    IPersonalityEngine,
    IValuesEngine,
    IOnboardingSystem,
    IHealthCheck
)

from .data_structures import (
    UserContext,
    PersonalityContext,
    ValuesContext,
    VoiceConfig,
    AutomationTask,
    PersonalityMode,
    UserRole
)

from .base_interfaces import (
    ComponentStatus,
    HealthStatus
)

from .exceptions import (
    UniversalSoulAIException,
    InitializationError,
    AIEngineError,
    CoActEngineError
)

__all__ = [
    # Base Interfaces
    'IAIEngine',
    'IAutomationEngine', 
    'IVoiceProcessor',
    'IPersonalityEngine',
    'IValuesEngine',
    'IOnboardingSystem',
    'IHealthCheck',
    
    # Data Structures
    'UserContext',
    'PersonalityContext',
    'ValuesContext',
    'VoiceConfig',
    'AutomationTask',
    'HealthStatus',
    'ComponentStatus',
    
    # Exceptions
    'UniversalSoulAIException',
    'InitializationError',
    'AIEngineError',
    'ValidationException'
]

__version__ = "1.0.0"
__author__ = "Universal Soul AI Team"