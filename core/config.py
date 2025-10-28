"""
Configuration Management for Universal Soul AI
===============================================

Centralized configuration system with environment-specific settings.
"""

import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HRMConfig:
    """Configuration for Hierarchical Reasoning Model"""
    model_path: str = "models/hrm_27m.bin"
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9
    reasoning_depth: int = 3
    batch_size: int = 1
    device: str = "auto"  # auto, cpu, cuda
    use_cache: bool = True
    cache_size: int = 1000
    backend: str = "ollama"  # ollama, llama_cpp, placeholder
    ollama_model: str = "qwen2.5:3b"
    ollama_url: str = "http://localhost:11434"
    llama_cpp_threads: str = "auto"
    llama_cpp_batch_size: str = "auto"
    context_window: int = 32768


@dataclass
class CoActConfig:
    """Configuration for CoAct-1 Automation Engine"""
    success_threshold: float = 0.6
    max_retries: int = 3
    timeout_seconds: int = 30
    parallel_tasks: int = 5
    learning_enabled: bool = True
    feedback_weight: float = 0.8
    complexity_scaling: bool = True
    terminalbench_enabled: bool = True
    use_multi_agent: bool = True
    target_success_rate: float = 0.75


@dataclass
class VoiceConfig:
    """Configuration for voice processing"""
    default_provider: str = "local"
    tts_model: str = "espeak"
    stt_model: str = "whisper-tiny"
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    timeout: int = 10
    language: str = "en-US"
    quality: str = "standard"


@dataclass
class PersonalityConfig:
    """Configuration for personality system"""
    default_mode: str = "friendly"
    intensity_range: tuple = (0.1, 1.0)
    adaptation_enabled: bool = True
    learning_rate: float = 0.1
    memory_duration: int = 3600  # seconds
    context_window: int = 10  # messages


@dataclass
class ValuesConfig:
    """Configuration for values system"""
    assessment_questions: int = 15
    privacy_level: str = "high"
    family_coordination: bool = True
    values_weight: float = 0.7
    update_frequency: int = 86400  # 24 hours in seconds
    backup_enabled: bool = True


@dataclass
class OnboardingConfig:
    """Configuration for onboarding system"""
    skip_completed: bool = True
    timeout_minutes: int = 30
    save_progress: bool = True
    allow_restart: bool = True
    required_steps: list = field(default_factory=lambda: [
        "welcome", "privacy_setup", "personality_selection", 
        "values_assessment", "preferences_setup"
    ])


@dataclass
class AndroidConfig:
    """Configuration for Android overlay"""
    overlay_enabled: bool = True
    gesture_sensitivity: float = 0.8
    ui_theme: str = "dark"
    animation_speed: float = 1.0
    vibration_enabled: bool = True
    touch_feedback: bool = True
    auto_hide_timeout: int = 5000  # milliseconds


@dataclass
class SecurityConfig:
    """Configuration for security settings"""
    encryption_enabled: bool = True
    key_rotation_days: int = 90
    session_timeout: int = 3600  # seconds
    max_login_attempts: int = 3
    require_biometric: bool = False
    audit_logging: bool = True


@dataclass
class PerformanceConfig:
    """Configuration for performance optimization"""
    max_memory_mb: int = 2048
    max_cpu_percent: float = 80.0
    cache_enabled: bool = True
    compression_enabled: bool = True
    batch_processing: bool = True
    background_tasks: int = 3


@dataclass
class UniversalSoulConfig:
    """Main configuration class"""
    # Core components
    hrm: HRMConfig = field(default_factory=HRMConfig)
    coact: CoActConfig = field(default_factory=CoActConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    personality: PersonalityConfig = field(default_factory=PersonalityConfig)
    values: ValuesConfig = field(default_factory=ValuesConfig)
    onboarding: OnboardingConfig = field(default_factory=OnboardingConfig)
    android: AndroidConfig = field(default_factory=AndroidConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    
    # Global settings
    debug_mode: bool = False
    log_level: str = "INFO"
    data_directory: str = "data"
    models_directory: str = "models"
    cache_directory: str = "cache"
    logs_directory: str = "logs"
    config_version: str = "1.0.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "hrm": self.hrm.__dict__,
            "coact": self.coact.__dict__,
            "voice": self.voice.__dict__,
            "personality": self.personality.__dict__,
            "values": self.values.__dict__,
            "onboarding": self.onboarding.__dict__,
            "android": self.android.__dict__,
            "security": self.security.__dict__,
            "performance": self.performance.__dict__,
            "debug_mode": self.debug_mode,
            "log_level": self.log_level,
            "data_directory": self.data_directory,
            "models_directory": self.models_directory,
            "cache_directory": self.cache_directory,
            "logs_directory": self.logs_directory,
            "config_version": self.config_version
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UniversalSoulConfig':
        """Create configuration from dictionary"""
        config = cls()
        
        # Update component configs
        if 'hrm' in data:
            config.hrm = HRMConfig(**data['hrm'])
        if 'coact' in data:
            config.coact = CoActConfig(**data['coact'])
        if 'voice' in data:
            config.voice = VoiceConfig(**data['voice'])
        if 'personality' in data:
            config.personality = PersonalityConfig(**data['personality'])
        if 'values' in data:
            config.values = ValuesConfig(**data['values'])
        if 'onboarding' in data:
            config.onboarding = OnboardingConfig(**data['onboarding'])
        if 'android' in data:
            config.android = AndroidConfig(**data['android'])
        if 'security' in data:
            config.security = SecurityConfig(**data['security'])
        if 'performance' in data:
            config.performance = PerformanceConfig(**data['performance'])
        
        # Update global settings
        for key in ['debug_mode', 'log_level', 'data_directory', 
                   'models_directory', 'cache_directory', 'logs_directory', 
                   'config_version']:
            if key in data:
                setattr(config, key, data[key])
        
        return config


class ConfigManager:
    """Configuration manager for loading and saving settings"""
    
    def __init__(self, config_path: str = "config/universal_soul.json"):
        self.config_path = Path(config_path)
        self._config: Optional[UniversalSoulConfig] = None
    
    def load_config(self) -> UniversalSoulConfig:
        """Load configuration from file"""
        if self._config is not None:
            return self._config
        
        # Create default config
        self._config = UniversalSoulConfig()
        
        # Load from file if exists
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._config = UniversalSoulConfig.from_dict(data)
            except Exception as e:
                print(f"Warning: Failed to load config from {self.config_path}: {e}")
                print("Using default configuration")
        
        # Override with environment variables
        self._apply_env_overrides()
        
        return self._config
    
    def save_config(self, config: UniversalSoulConfig) -> None:
        """Save configuration to file"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
        
        self._config = config
    
    def get_config(self) -> UniversalSoulConfig:
        """Get current configuration"""
        if self._config is None:
            return self.load_config()
        return self._config
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides"""
        if not self._config:
            return
        
        # Debug mode
        if os.getenv('UNIVERSAL_SOUL_DEBUG'):
            self._config.debug_mode = os.getenv('UNIVERSAL_SOUL_DEBUG').lower() == 'true'
        
        # Log level
        if os.getenv('UNIVERSAL_SOUL_LOG_LEVEL'):
            self._config.log_level = os.getenv('UNIVERSAL_SOUL_LOG_LEVEL')
        
        # Data directory
        if os.getenv('UNIVERSAL_SOUL_DATA_DIR'):
            self._config.data_directory = os.getenv('UNIVERSAL_SOUL_DATA_DIR')
        
        # Models directory
        if os.getenv('UNIVERSAL_SOUL_MODELS_DIR'):
            self._config.models_directory = os.getenv('UNIVERSAL_SOUL_MODELS_DIR')
        
        # HRM device
        if os.getenv('UNIVERSAL_SOUL_HRM_DEVICE'):
            self._config.hrm.device = os.getenv('UNIVERSAL_SOUL_HRM_DEVICE')
        
        # Voice provider
        if os.getenv('UNIVERSAL_SOUL_VOICE_PROVIDER'):
            self._config.voice.default_provider = os.getenv('UNIVERSAL_SOUL_VOICE_PROVIDER')
    
    def reset_to_defaults(self) -> UniversalSoulConfig:
        """Reset configuration to defaults"""
        self._config = UniversalSoulConfig()
        return self._config


# Global config manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_path: str = "config/universal_soul.json") -> ConfigManager:
    """Get the global configuration manager"""
    global _config_manager
    if _config_manager is None or _config_manager.config_path != Path(config_path):
        _config_manager = ConfigManager(config_path)
    return _config_manager


def get_config() -> UniversalSoulConfig:
    """Get the current configuration"""
    manager = get_config_manager()
    return manager.get_config()


def save_config(config: UniversalSoulConfig) -> None:
    """Save configuration"""
    manager = get_config_manager()
    manager.save_config(config)


def reset_config() -> UniversalSoulConfig:
    """Reset configuration to defaults"""
    manager = get_config_manager()
    return manager.reset_to_defaults()