"""
ThinkMesh Core - Advanced AI System Architecture
Complete implementation of privacy-first, multi-agent AI system

Modules:
- orchestration: Multi-agent coordination and task distribution
- ai_providers: Unified AI provider abstraction layer
- voice: Enhanced voice processing pipeline
- localai: Local model management (CPT-OSS 20B, etc.)
- monitoring: System health and performance tracking
- cogniflow: Advanced reasoning and decision-making
- automation: Enhanced automation engine
- sync: Cloud sync with privacy controls
- bridges: Integration bridges for external systems
- synergycore: Core coordination and messaging hub
- hrm: Human Relationship Management
- reasoning: Strategic planning and reasoning
"""

__version__ = "1.0.0"
__author__ = "Universal Soul AI Team"

from .orchestration import ThinkMeshOrchestrator
from .ai_providers import AIProviderManager
from .voice import VoicePipeline
from .localai import LocalModelManager

__all__ = [
    'ThinkMeshOrchestrator',
    'AIProviderManager',
    'VoicePipeline',
    'LocalModelManager'
]
