"""
Agent Pool
Manages pool of available agents
"""

from typing import Dict, List
from .orchestrator import AgentCapability
import logging

logger = logging.getLogger(__name__)


class AgentPool:
    """Manages available agents"""
    
    def __init__(self):
        self.agents: Dict[str, AgentCapability] = {}
    
    def add_agent(self, agent: AgentCapability):
        """Add agent to pool"""
        self.agents[agent.agent_id] = agent
        logger.info(f"Agent {agent.agent_id} added to pool")
    
    def remove_agent(self, agent_id: str):
        """Remove agent from pool"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            logger.info(f"Agent {agent_id} removed from pool")
    
    def get_available(self) -> List[AgentCapability]:
        """Get available agents"""
        return [
            agent for agent in self.agents.values()
            if agent.availability
        ]
    
    def get_by_specialization(
        self,
        specialization: str
    ) -> List[AgentCapability]:
        """Get agents by specialization"""
        return [
            agent for agent in self.agents.values()
            if specialization in agent.specializations
        ]
