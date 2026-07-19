# Voice Processing Module
from .voice_pipeline import VoicePipeline, VoiceConfig

try:
    from core.voice_pipeline.vad import (
        VoiceActivityDetector,
        VADConfig,
        VADResult,
    )
    _VAD_EXPORTS = ['VoiceActivityDetector', 'VADConfig', 'VADResult']
except Exception:
    VoiceActivityDetector = None  # type: ignore
    VADConfig = None  # type: ignore
    VADResult = None  # type: ignore
    _VAD_EXPORTS = []

try:
    from core.voice_pipeline.audio_processor import (
        AudioProcessor,
        AudioProcessorConfig,
    )
    _AUDIO_EXPORTS = ['AudioProcessor', 'AudioProcessorConfig']
except Exception:
    AudioProcessor = None  # type: ignore
    AudioProcessorConfig = None  # type: ignore
    _AUDIO_EXPORTS = []

try:
    from core.voice_pipeline.cloud_providers import (
        ElevenLabsTTSProvider,
        DeepgramSTTProvider,
        OmniVoiceTTSProvider,
        OmniVoiceSTTProvider,
    )
    _CLOUD_EXPORTS = [
        'ElevenLabsTTSProvider',
        'DeepgramSTTProvider',
        'OmniVoiceTTSProvider',
        'OmniVoiceSTTProvider',
    ]
except Exception:
    ElevenLabsTTSProvider = None  # type: ignore
    DeepgramSTTProvider = None  # type: ignore
    OmniVoiceTTSProvider = None  # type: ignore
    OmniVoiceSTTProvider = None  # type: ignore
    _CLOUD_EXPORTS = []

__version__ = '1.0.0'
__all__ = (
    ['VoicePipeline', 'VoiceConfig']
    + _VAD_EXPORTS
    + _AUDIO_EXPORTS
    + _CLOUD_EXPORTS
)
