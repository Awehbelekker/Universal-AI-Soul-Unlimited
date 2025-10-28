"""
Custom Exceptions for Universal Soul AI
=======================================

Comprehensive exception hierarchy for the Universal Soul AI system.
"""


class UniversalSoulAIException(Exception):
    """Base exception for all Universal Soul AI errors"""
    
    def __init__(self, message: str, error_code: str = None, 
                 context: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "UNKNOWN_ERROR"
        self.context = context or {}
    
    def to_dict(self) -> dict:
        """Convert exception to dictionary"""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "context": self.context
        }


class InitializationError(UniversalSoulAIException):
    """Raised when component initialization fails"""
    pass


class ConfigurationError(UniversalSoulAIException):
    """Raised when configuration is invalid or missing"""
    pass


class DependencyError(UniversalSoulAIException):
    """Raised when dependencies are missing or incompatible"""
    pass


class AuthenticationError(UniversalSoulAIException):
    """Raised when authentication fails"""
    pass


class AuthorizationError(UniversalSoulAIException):
    """Raised when user lacks required permissions"""
    pass


class ValidationError(UniversalSoulAIException):
    """Raised when data validation fails"""
    pass


class ProcessingError(UniversalSoulAIException):
    """Raised when processing operations fail"""
    pass


class AIEngineError(UniversalSoulAIException):
    """Base exception for AI engine errors"""
    pass


class HRMEngineError(AIEngineError):
    """Raised when HRM engine operations fail"""
    pass


class CoActEngineError(AIEngineError):
    """Raised when CoAct-1 automation engine fails"""
    pass


class PersonalityEngineError(AIEngineError):
    """Raised when personality engine operations fail"""
    pass


class ValuesEngineError(AIEngineError):
    """Raised when values engine operations fail"""
    pass


class VoiceProcessingError(UniversalSoulAIException):
    """Base exception for voice processing errors"""
    pass


class TextToSpeechError(VoiceProcessingError):
    """Raised when text-to-speech conversion fails"""
    pass


class SpeechToTextError(VoiceProcessingError):
    """Raised when speech-to-text conversion fails"""
    pass


class VoiceProviderError(VoiceProcessingError):
    """Raised when voice provider operations fail"""
    pass


class OnboardingError(UniversalSoulAIException):
    """Raised when onboarding process fails"""
    pass


class UserContextError(UniversalSoulAIException):
    """Raised when user context operations fail"""
    pass


class ContainerError(UniversalSoulAIException):
    """Base exception for dependency injection container errors"""
    pass


class ServiceNotFoundError(ContainerError):
    """Raised when requested service is not registered"""
    pass


class CircularDependencyError(ContainerError):
    """Raised when circular dependency is detected"""
    pass


class HealthCheckError(UniversalSoulAIException):
    """Raised when health check operations fail"""
    pass


class MetricsError(UniversalSoulAIException):
    """Raised when metrics collection fails"""
    pass


class StorageError(UniversalSoulAIException):
    """Base exception for storage operations"""
    pass


class DataNotFoundError(StorageError):
    """Raised when requested data is not found"""
    pass


class DataCorruptionError(StorageError):
    """Raised when data corruption is detected"""
    pass


class NetworkError(UniversalSoulAIException):
    """Raised when network operations fail"""
    pass


class TimeoutError(UniversalSoulAIException):
    """Raised when operations timeout"""
    pass


class ResourceExhaustedError(UniversalSoulAIException):
    """Raised when system resources are exhausted"""
    pass


class SecurityError(UniversalSoulAIException):
    """Raised when security violations are detected"""
    pass


class PrivacyError(SecurityError):
    """Raised when privacy constraints are violated"""
    pass


class EncryptionError(SecurityError):
    """Raised when encryption operations fail"""
    pass


class AndroidOverlayError(UniversalSoulAIException):
    """Raised when Android overlay operations fail"""
    pass


class GestureRecognitionError(AndroidOverlayError):
    """Raised when gesture recognition fails"""
    pass


class UIRenderingError(AndroidOverlayError):
    """Raised when UI rendering fails"""
    pass


class MobileIntegrationError(UniversalSoulAIException):
    """Raised when mobile integration operations fail"""
    pass


class TwoSoulIntegrationError(MobileIntegrationError):
    """Raised when TwoSoul system integration fails"""
    pass


class EdgeMindError(UniversalSoulAIException):
    """Raised when EdgeMind optimization fails"""
    pass


def handle_exception(func):
    """Decorator to handle exceptions with logging"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except UniversalSoulAIException as e:
            # Log the exception
            print(f"Universal Soul AI Error: {e.error_code} - {e.message}")
            if e.context:
                print(f"Context: {e.context}")
            raise
        except Exception as e:
            # Wrap unknown exceptions
            wrapped = UniversalSoulAIException(
                message=f"Unexpected error: {str(e)}",
                error_code="UNEXPECTED_ERROR",
                context={"original_exception": type(e).__name__}
            )
            print(f"Unexpected Error: {wrapped.error_code} - {wrapped.message}")
            raise wrapped
    return wrapper


def handle_async_exception(func):
    """Async decorator to handle exceptions with logging"""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except UniversalSoulAIException as e:
            # Log the exception
            print(f"Universal Soul AI Error: {e.error_code} - {e.message}")
            if e.context:
                print(f"Context: {e.context}")
            raise
        except Exception as e:
            # Wrap unknown exceptions
            wrapped = UniversalSoulAIException(
                message=f"Unexpected error: {str(e)}",
                error_code="UNEXPECTED_ERROR",
                context={"original_exception": type(e).__name__}
            )
            print(f"Unexpected Error: {wrapped.error_code} - {wrapped.message}")
            raise wrapped
    return wrapper