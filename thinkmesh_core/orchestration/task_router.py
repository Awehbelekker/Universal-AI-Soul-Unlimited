"""
Task Router
Routes tasks to appropriate agents based on capabilities
"""

from typing import Dict, List, Optional
from .orchestrator import Task, AgentCapability
import logging

logger = logging.getLogger(__name__)


class TaskRouter:
    """Routes tasks to optimal agents"""
    
    def __init__(self):
        self.routing_rules = {}
    
    async def route(
        self,
        task: Task,
        agents: Dict[str, AgentCapability]
    ) -> List[AgentCapability]:
        """Route task to suitable agents"""
        suitable = []
        
        for agent in agents.values():
            if self._is_suitable(task, agent):
                suitable.append(agent)
        
        return sorted(
            suitable,
            key=lambda a: a.performance_score,
            reverse=True
        )
    
    def _is_suitable(
        self,
        task: Task,
        agent: AgentCapability
    ) -> bool:
        """Check if agent is suitable for task"""
        if not agent.availability:
            return False
        
        required_specs = task.requirements.get('specializations', [])
        if required_specs:
            return any(s in agent.specializations for s in required_specs)
        
        return True
