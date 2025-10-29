"""
Strategy Manager
Manages and switches between orchestration strategies
"""

from .orchestrator import OrchestrationStrategy
import logging

logger = logging.getLogger(__name__)


class StrategyManager:
    """Manages orchestration strategies"""

    def __init__(self):
        self.current_strategy = OrchestrationStrategy.ADAPTIVE
        self.strategy_history = []

    def set_strategy(self, strategy: OrchestrationStrategy):
        """Set orchestration strategy"""
        self.strategy_history.append({
            'from': self.current_strategy,
            'to': strategy
        })
        self.current_strategy = strategy
        logger.info(f"Strategy changed to: {strategy.value}")

    def get_strategy(self) -> OrchestrationStrategy:
        """Get current strategy"""
        return self.current_strategy

    def get_all_strategies(self) -> list:
        """Get all available strategies"""
        return list(OrchestrationStrategy)
