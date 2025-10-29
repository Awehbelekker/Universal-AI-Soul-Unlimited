# AI Provider Manager
import logging
from enum import Enum
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    LOCAL = "local"
    CLOUD = "cloud"
    HYBRID = "hybrid"


class ProviderPriority(Enum):
    PRIMARY = 1
    SECONDARY = 2
    FALLBACK = 3


class AIProviderManager:
    """Manages multiple AI providers with fallback and load balancing"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.providers = {}
        self.health_status = {}
        logger.info("AIProviderManager initialized")

    def register_provider(
        self,
        provider_id: str,
        provider: Any,
        provider_type: ProviderType,
        priority: ProviderPriority = ProviderPriority.PRIMARY
    ):
        """Register an AI provider"""
        self.providers[provider_id] = {
            'provider': provider,
            'type': provider_type,
            'priority': priority,
            'active': True
        }
        logger.info(
            f"Registered provider: {provider_id} "
            f"({provider_type.value}, priority: {priority.name})"
        )

    async def generate(
        self, prompt: str, provider_id: Optional[str] = None, **kwargs
    ) -> str:
        """Generate response using specified or optimal provider"""
        if provider_id and provider_id in self.providers:
            return await self._generate_with_provider(
                provider_id, prompt, **kwargs
            )

        # Select optimal provider
        selected = self._select_provider()
        if not selected:
            raise ValueError("No active providers available")

        try:
            return await self._generate_with_provider(
                selected, prompt, **kwargs
            )
        except Exception as e:
            logger.warning(f"Provider {selected} failed: {e}")
            return await self._fallback_generate(
                prompt, exclude=[selected], **kwargs
            )

    def _select_provider(self) -> Optional[str]:
        """Select best available provider"""
        active = [
            (pid, p) for pid, p in self.providers.items() if p['active']
        ]
        if not active:
            return None

        # Sort by priority
        active.sort(key=lambda x: x[1]['priority'].value)
        return active[0][0]

    async def _generate_with_provider(
        self, provider_id: str, prompt: str, **kwargs
    ) -> str:
        """Generate with specific provider"""
        provider_info = self.providers[provider_id]
        provider = provider_info['provider']

        # Call provider (adapt to your provider interface)
        if hasattr(provider, 'generate'):
            return await provider.generate(prompt, **kwargs)
        elif callable(provider):
            return await provider(prompt, **kwargs)

        raise ValueError(f"Provider {provider_id} has no generate method")

    async def _fallback_generate(
        self, prompt: str, exclude: List[str], **kwargs
    ) -> str:
        """Try fallback providers"""
        for pid, pinfo in self.providers.items():
            if pid not in exclude and pinfo['active']:
                try:
                    logger.info(f"Trying fallback provider: {pid}")
                    return await self._generate_with_provider(
                        pid, prompt, **kwargs
                    )
                except Exception as e:
                    logger.warning(f"Fallback provider {pid} failed: {e}")
                    continue

        raise RuntimeError("All providers failed")

    def get_status(self) -> Dict:
        """Get status of all providers"""
        return {
            pid: {
                'type': p['type'].value,
                'priority': p['priority'].name,
                'active': p['active']
            }
            for pid, p in self.providers.items()
        }
