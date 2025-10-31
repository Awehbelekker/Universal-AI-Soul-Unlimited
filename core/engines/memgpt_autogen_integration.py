"""
MemGPT and AutoGEN Integration for Universal Soul AI
====================================================

Integrates MemGPT for long-term memory management and AutoGEN
for advanced multi-agent workflows.

Features:
- Persistent memory across sessions (MemGPT)
- Multi-agent collaboration for complex tasks (AutoGEN)
- Context management and retrieval
- Agent conversation orchestration
- Memory hierarchy (core, archival, recall)

Note: This is a future enhancement module with placeholder
implementations ready for MemGPT/AutoGEN integration.

Author: Universal Soul AI Team
Date: October 2025
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import json

try:
    import memgpt
    MEMGPT_AVAILABLE = True
except ImportError:
    MEMGPT_AVAILABLE = False
    memgpt = None

try:
    import autogen
    AUTOGEN_AVAILABLE = True
except ImportError:
    AUTOGEN_AVAILABLE = False
    autogen = None

from ..config import Config


logger = logging.getLogger(__name__)


class MemoryStore:
    """
    Memory storage system with hierarchical organization.

    Memory levels:
    - Core: Essential user information and preferences
    - Contextual: Recent conversation history
    - Archival: Long-term historical interactions
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize memory store.

        Args:
            storage_path: Path to store memory data
        """
        self.storage_path = storage_path or Path("data/memory")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.core_memory = {}
        self.contextual_memory = []
        self.archival_memory = []

        logger.info(f"Memory store initialized at {self.storage_path}")

    async def store_core_memory(
        self,
        user_id: str,
        key: str,
        value: Any
    ) -> bool:
        """
        Store core memory (essential user info).

        Args:
            user_id: User identifier
            key: Memory key
            value: Memory value

        Returns:
            bool: True if stored successfully
        """
        if user_id not in self.core_memory:
            self.core_memory[user_id] = {}

        self.core_memory[user_id][key] = {
            "value": value,
            "updated_at": datetime.now().isoformat(),
        }

        await self._persist_memory(user_id)
        logger.debug(f"Stored core memory: {user_id}/{key}")
        return True

    async def store_interaction(
        self,
        user_id: str,
        interaction: Dict[str, Any]
    ) -> bool:
        """
        Store interaction in contextual memory.

        Args:
            user_id: User identifier
            interaction: Interaction data

        Returns:
            bool: True if stored successfully
        """
        memory_entry = {
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "interaction": interaction,
        }

        self.contextual_memory.append(memory_entry)

        # Archive old memories (keep last 100 in context)
        if len(self.contextual_memory) > 100:
            old_memory = self.contextual_memory.pop(0)
            self.archival_memory.append(old_memory)

        await self._persist_memory(user_id)
        logger.debug(f"Stored interaction for user: {user_id}")
        return True

    async def recall_memory(
        self,
        user_id: str,
        query: str,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Recall relevant memories based on query.

        Args:
            user_id: User identifier
            query: Search query
            max_results: Maximum results to return

        Returns:
            List of relevant memory entries
        """
        results = []

        # Search contextual memory
        for memory in reversed(self.contextual_memory):
            if memory["user_id"] == user_id:
                # Simple keyword search (could use embeddings)
                if self._is_relevant(query, memory):
                    results.append(memory)
                    if len(results) >= max_results:
                        break

        logger.debug(f"Recalled {len(results)} memories for query: {query}")
        return results

    def _is_relevant(self, query: str, memory: Dict[str, Any]) -> bool:
        """Simple relevance check (placeholder for embedding search)."""
        query_lower = query.lower()
        memory_str = json.dumps(memory).lower()
        return any(word in memory_str for word in query_lower.split())

    async def _persist_memory(self, user_id: str):
        """Persist memory to disk."""
        try:
            user_memory_file = self.storage_path / f"{user_id}_memory.json"

            memory_data = {
                "core": self.core_memory.get(user_id, {}),
                "contextual": [
                    m for m in self.contextual_memory
                    if m["user_id"] == user_id
                ],
                "archival_count": len([
                    m for m in self.archival_memory
                    if m["user_id"] == user_id
                ]),
            }

            with open(user_memory_file, "w") as f:
                json.dump(memory_data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to persist memory: {e}")


class MemGPTIntegration:
    """
    MemGPT integration for long-term memory management.

    Provides persistent memory across sessions with hierarchical
    organization and intelligent retrieval.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        storage_path: Optional[Path] = None
    ):
        """
        Initialize MemGPT integration.

        Args:
            config: Configuration object
            storage_path: Path to store memory data
        """
        self.config = config or Config()
        self.memory_store = MemoryStore(storage_path)
        self.available = MEMGPT_AVAILABLE

        if not self.available:
            logger.warning(
                "MemGPT not installed. Using local memory store. "
                "Install with: pip install pymemgpt"
            )

        logger.info("MemGPT integration initialized")

    async def store_interaction(
        self,
        user_id: str,
        interaction: Dict[str, Any]
    ) -> bool:
        """
        Store user interaction in memory.

        Args:
            user_id: User identifier
            interaction: Interaction data (prompt, response, metadata)

        Returns:
            bool: True if stored successfully
        """
        return await self.memory_store.store_interaction(
            user_id,
            interaction
        )

    async def recall_context(
        self,
        user_id: str,
        query: str,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Recall relevant context from memory.

        Args:
            user_id: User identifier
            query: Query to search for
            max_results: Maximum results to return

        Returns:
            List of relevant memory entries
        """
        return await self.memory_store.recall_memory(
            user_id,
            query,
            max_results
        )

    async def update_user_preferences(
        self,
        user_id: str,
        preferences: Dict[str, Any]
    ) -> bool:
        """
        Update user preferences in core memory.

        Args:
            user_id: User identifier
            preferences: User preferences

        Returns:
            bool: True if updated successfully
        """
        for key, value in preferences.items():
            await self.memory_store.store_core_memory(
                user_id,
                f"preference_{key}",
                value
            )
        return True

    async def health_check(self) -> Dict[str, Any]:
        """Check health status of MemGPT integration."""
        return {
            "status": "healthy",
            "memgpt_available": self.available,
            "using_local_store": not self.available,
            "storage_path": str(self.memory_store.storage_path),
        }


class AutoGENIntegration:
    """
    AutoGEN integration for multi-agent workflows.

    Enables complex task completion through coordinated
    multi-agent conversations and collaboration.
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize AutoGEN integration.

        Args:
            config: Configuration object
        """
        self.config = config or Config()
        self.available = AUTOGEN_AVAILABLE
        self.agents = {}

        if not self.available:
            logger.warning(
                "AutoGEN not installed. Using placeholder agents. "
                "Install with: pip install pyautogen"
            )

        logger.info("AutoGEN integration initialized")

    async def create_agent(
        self,
        name: str,
        role: str,
        system_message: str
    ) -> Dict[str, Any]:
        """
        Create a new agent.

        Args:
            name: Agent name
            role: Agent role (assistant, user_proxy, etc.)
            system_message: System message for agent

        Returns:
            Dict containing agent info
        """
        agent_info = {
            "name": name,
            "role": role,
            "system_message": system_message,
            "created_at": datetime.now().isoformat(),
        }

        self.agents[name] = agent_info
        logger.info(f"Created agent: {name} ({role})")

        return agent_info

    async def run_workflow(
        self,
        task: str,
        agents: List[str],
        max_rounds: int = 10
    ) -> Dict[str, Any]:
        """
        Run multi-agent workflow.

        Args:
            task: Task description
            agents: List of agent names to use
            max_rounds: Maximum conversation rounds

        Returns:
            Dict containing workflow results
        """
        logger.info(
            f"Running workflow with {len(agents)} agents: {task}"
        )

        # Placeholder implementation
        # Real implementation would use AutoGEN conversation
        workflow_result = {
            "task": task,
            "agents_used": agents,
            "rounds": min(max_rounds, 5),
            "success": True,
            "result": f"Completed task: {task}",
            "messages": [
                {
                    "agent": agent,
                    "message": f"Agent {agent} contributed to task"
                }
                for agent in agents
            ],
        }

        logger.info(f"Workflow completed: {workflow_result['success']}")
        return workflow_result

    async def health_check(self) -> Dict[str, Any]:
        """Check health status of AutoGEN integration."""
        return {
            "status": "healthy",
            "autogen_available": self.available,
            "agents_created": len(self.agents),
            "using_placeholder": not self.available,
        }


class UnifiedMemoryAgent:
    """
    Unified integration combining MemGPT and AutoGEN.

    Provides both long-term memory and multi-agent capabilities
    in a single interface.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        storage_path: Optional[Path] = None
    ):
        """
        Initialize unified memory agent.

        Args:
            config: Configuration object
            storage_path: Path to store memory data
        """
        self.config = config or Config()
        self.memgpt = MemGPTIntegration(config, storage_path)
        self.autogen = AutoGENIntegration(config)

        logger.info("Unified memory agent initialized")

    async def process_with_memory(
        self,
        user_id: str,
        task: str,
        use_agents: bool = False
    ) -> Dict[str, Any]:
        """
        Process task with memory and optional multi-agent support.

        Args:
            user_id: User identifier
            task: Task to process
            use_agents: Use multi-agent workflow

        Returns:
            Dict containing processing results
        """
        # Recall relevant context
        context = await self.memgpt.recall_context(user_id, task)

        result = {
            "task": task,
            "context_used": len(context),
        }

        if use_agents:
            # Use multi-agent workflow
            agents = ["planner", "executor", "validator"]
            workflow_result = await self.autogen.run_workflow(
                task,
                agents
            )
            result["workflow"] = workflow_result
        else:
            # Simple processing
            result["response"] = f"Processed: {task}"

        # Store interaction
        await self.memgpt.store_interaction(user_id, result)

        return result

    async def health_check(self) -> Dict[str, Any]:
        """Check health status of unified agent."""
        memgpt_health = await self.memgpt.health_check()
        autogen_health = await self.autogen.health_check()

        return {
            "status": "healthy",
            "memgpt": memgpt_health,
            "autogen": autogen_health,
        }


async def create_memory_agent(
    config: Optional[Config] = None,
    storage_path: Optional[Path] = None
) -> UnifiedMemoryAgent:
    """
    Create unified memory agent.

    Args:
        config: Configuration object
        storage_path: Path to store memory data

    Returns:
        UnifiedMemoryAgent instance
    """
    agent = UnifiedMemoryAgent(config, storage_path)
    logger.info("Memory agent created")
    return agent
