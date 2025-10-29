"""
ThinkMesh Orchestrator
Central coordination system for multi-agent AI workflows
"""

import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


class OrchestrationStrategy(Enum):
    """Orchestration strategies"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HIERARCHICAL = "hierarchical"
    CONSENSUS = "consensus"
    COMPETITIVE = "competitive"
    COLLABORATIVE = "collaborative"
    ADAPTIVE = "adaptive"


class TaskPriority(Enum):
    """Task priority levels"""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


@dataclass
class Task:
    """Task definition"""
    id: str
    type: str
    priority: TaskPriority
    requirements: Dict[str, Any]
    context: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)
    deadline: Optional[float] = None
    status: str = "pending"
    assigned_agents: List[str] = field(default_factory=list)
    result: Optional[Any] = None


@dataclass
class AgentCapability:
    """Agent capability definition"""
    agent_id: str
    specializations: List[str]
    performance_score: float
    availability: bool
    current_load: int
    max_load: int = 10
    skills: Dict[str, float] = field(default_factory=dict)


class ThinkMeshOrchestrator:
    """
    Advanced Multi-Agent Orchestration System

    Coordinates multiple AI agents, distributes tasks intelligently,
    and ensures optimal resource utilization with privacy controls.

    Features:
    - 7 orchestration strategies
    - Intelligent task routing
    - Load balancing
    - Consensus mechanisms
    - Performance tracking
    - Privacy-first design
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.agents: Dict[str, AgentCapability] = {}
        self.active_tasks: Dict[str, Task] = {}
        self.completed_tasks: List[Task] = []
        self.strategy = OrchestrationStrategy.ADAPTIVE
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self._running = False

    async def initialize(self):
        """Initialize orchestrator"""
        logger.info("Initializing ThinkMesh Orchestrator")
        self._running = True

        # Start task processor
        asyncio.create_task(self._process_task_queue())

        logger.info(
            f"Orchestrator initialized with strategy: "
            f"{self.strategy.value}"
        )

    async def register_agent(
        self,
        agent_id: str,
        specializations: List[str],
        capabilities: Dict[str, Any]
    ) -> bool:
        """Register a new agent with the orchestrator"""
        try:
            self.agents[agent_id] = AgentCapability(
                agent_id=agent_id,
                specializations=specializations,
                performance_score=capabilities.get('performance_score', 0.5),
                availability=True,
                current_load=0,
                max_load=capabilities.get('max_load', 10),
                skills=capabilities.get('skills', {})
            )
            logger.info(
                f"✅ Agent {agent_id} registered - "
                f"Specializations: {specializations}"
            )
            return True
        except Exception as e:
            logger.error(f"❌ Failed to register agent {agent_id}: {e}")
            return False

    async def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            logger.info(f"Agent {agent_id} unregistered")
            return True
        return False

    async def submit_task(
        self,
        task_type: str,
        requirements: Dict[str, Any],
        context: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        deadline: Optional[float] = None
    ) -> str:
        """Submit a task for orchestration"""
        task_id = str(uuid.uuid4())

        task = Task(
            id=task_id,
            type=task_type,
            priority=priority,
            requirements=requirements,
            context=context,
            deadline=deadline
        )

        self.active_tasks[task_id] = task
        await self.task_queue.put(task)

        logger.info(
            f"📋 Task {task_id} submitted - "
            f"Type: {task_type}, Priority: {priority.name}"
        )
        return task_id

    async def _process_task_queue(self):
        """Process tasks from the queue"""
        while self._running:
            try:
                task = await asyncio.wait_for(
                    self.task_queue.get(), timeout=1.0
                )
                await self._route_task(task)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing task queue: {e}")

    async def _route_task(self, task: Task):
        """Route task to appropriate agent(s) based on strategy"""
        try:
            if self.strategy == OrchestrationStrategy.SEQUENTIAL:
                await self._sequential_routing(task)
            elif self.strategy == OrchestrationStrategy.PARALLEL:
                await self._parallel_routing(task)
            elif self.strategy == OrchestrationStrategy.CONSENSUS:
                await self._consensus_routing(task)
            elif self.strategy == OrchestrationStrategy.HIERARCHICAL:
                await self._hierarchical_routing(task)
            elif self.strategy == OrchestrationStrategy.COMPETITIVE:
                await self._competitive_routing(task)
            elif self.strategy == OrchestrationStrategy.COLLABORATIVE:
                await self._collaborative_routing(task)
            else:  # ADAPTIVE
                await self._adaptive_routing(task)
        except Exception as e:
            logger.error(f"Error routing task {task.id}: {e}")
            task.status = "failed"

    async def _sequential_routing(self, task: Task):
        """Route task sequentially through agents"""
        suitable_agents = self._find_suitable_agents(task)
        if not suitable_agents:
            logger.warning(f"No suitable agents for task {task.id}")
            task.status = "failed"
            return

        # Execute on best agent
        best_agent = suitable_agents[0]
        task.assigned_agents = [best_agent.agent_id]
        logger.info(
            f"🎯 Sequential routing: Task {task.id} → "
            f"Agent {best_agent.agent_id}"
        )

        result = await self._execute_on_agent(best_agent, task)
        task.result = result
        task.status = "completed"

        # Move to completed
        self._complete_task(task)

    async def _parallel_routing(self, task: Task):
        """Route task to multiple agents in parallel"""
        suitable_agents = self._find_suitable_agents(task)
        if not suitable_agents:
            task.status = "failed"
            return

        # Execute on up to 3 agents in parallel
        selected_agents = suitable_agents[:min(3, len(suitable_agents))]
        task.assigned_agents = [a.agent_id for a in selected_agents]

        logger.info(
            f"⚡ Parallel routing: Task {task.id} → "
            f"{len(selected_agents)} agents"
        )

        results = await asyncio.gather(*[
            self._execute_on_agent(agent, task)
            for agent in selected_agents
        ], return_exceptions=True)

        # Use first successful result
        task.result = next(
            (r for r in results if not isinstance(r, Exception)),
            None
        )
        task.status = "completed" if task.result else "failed"

        self._complete_task(task)

    async def _consensus_routing(self, task: Task):
        """Route task to multiple agents and achieve consensus"""
        suitable_agents = self._find_suitable_agents(task)
        if len(suitable_agents) < 3:
            # Fallback to parallel if not enough agents
            await self._parallel_routing(task)
            return

        # Execute on 3-5 agents
        selected_agents = suitable_agents[:min(5, len(suitable_agents))]
        task.assigned_agents = [a.agent_id for a in selected_agents]

        logger.info(
            f"🤝 Consensus routing: Task {task.id} → "
            f"{len(selected_agents)} agents"
        )

        results = await asyncio.gather(*[
            self._execute_on_agent(agent, task)
            for agent in selected_agents
        ], return_exceptions=True)

        # Achieve consensus
        valid_results = [r for r in results if not isinstance(r, Exception)]
        if valid_results:
            consensus = await self._achieve_consensus(valid_results)
            task.result = consensus
            task.status = "completed"
        else:
            task.status = "failed"

        self._complete_task(task)

    async def _hierarchical_routing(self, task: Task):
        """Route task hierarchically (coordinator → specialized agents)"""
        # Find coordinator agent
        coordinator = next(
            (a for a in self.agents.values()
             if 'coordinator' in a.specializations
             or 'general' in a.specializations),
            None
        )

        if coordinator:
            task.assigned_agents = [coordinator.agent_id]
            logger.info(
                f"📊 Hierarchical routing: Task {task.id} → "
                f"Coordinator {coordinator.agent_id}"
            )

            result = await self._execute_on_agent(coordinator, task)
            task.result = result
            task.status = "completed"
        else:
            # Fallback to adaptive
            await self._adaptive_routing(task)
            return

        self._complete_task(task)

    async def _competitive_routing(self, task: Task):
        """Route task competitively (first to complete wins)"""
        suitable_agents = self._find_suitable_agents(task)
        if not suitable_agents:
            task.status = "failed"
            return

        selected_agents = suitable_agents[:min(3, len(suitable_agents))]
        task.assigned_agents = [a.agent_id for a in selected_agents]

        logger.info(
            f"🏁 Competitive routing: Task {task.id} → "
            f"{len(selected_agents)} agents (race)"
        )

        # Race - first to complete wins
        done, pending = await asyncio.wait(
            [self._execute_on_agent(agent, task) for agent in selected_agents],
            return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel remaining tasks
        for p in pending:
            p.cancel()

        # Get first result
        task.result = next(iter(done)).result() if done else None
        task.status = "completed" if task.result else "failed"

        self._complete_task(task)

    async def _collaborative_routing(self, task: Task):
        """Route task collaboratively (agents work together)"""
        suitable_agents = self._find_suitable_agents(task)
        if not suitable_agents:
            task.status = "failed"
            return

        # Break task into subtasks and distribute
        selected_agents = suitable_agents[:min(4, len(suitable_agents))]
        task.assigned_agents = [a.agent_id for a in selected_agents]

        logger.info(
            f"👥 Collaborative routing: Task {task.id} → "
            f"{len(selected_agents)} agents"
        )

        # Each agent handles a subtask
        subtasks = self._create_subtasks(task, len(selected_agents))
        results = await asyncio.gather(*[
            self._execute_subtask(agent, subtask)
            for agent, subtask in zip(selected_agents, subtasks)
        ], return_exceptions=True)

        # Merge results
        valid_results = [r for r in results if not isinstance(r, Exception)]
        if valid_results:
            task.result = await self._merge_results(valid_results)
            task.status = "completed"
        else:
            task.status = "failed"

        self._complete_task(task)

    async def _adaptive_routing(self, task: Task):
        """
        Adaptively route based on agent performance, load,
        and task requirements
        """
        suitable_agents = self._find_suitable_agents(task)
        if not suitable_agents:
            logger.warning(f"No suitable agents found for task {task.id}")
            task.status = "failed"
            return

        # Sophisticated scoring: performance × availability × skill match
        def score_agent(agent: AgentCapability) -> float:
            # Base performance score
            score = agent.performance_score

            # Load penalty
            load_factor = 1 - (agent.current_load / agent.max_load)
            score *= load_factor

            # Skill match bonus
            required_skills = task.requirements.get('skills', {})
            if required_skills:
                skill_match = sum(
                    agent.skills.get(skill, 0) * weight
                    for skill, weight in required_skills.items()
                ) / len(required_skills)
                score *= (1 + skill_match)

            return score

        # Select best agent
        best_agent = max(suitable_agents, key=score_agent)
        task.assigned_agents = [best_agent.agent_id]

        logger.info(
            f"🎯 Adaptive routing: Task {task.id} → "
            f"Agent {best_agent.agent_id} "
            f"(score: {score_agent(best_agent):.2f})"
        )

        result = await self._execute_on_agent(best_agent, task)
        task.result = result
        task.status = "completed"

        self._complete_task(task)

    def _find_suitable_agents(self, task: Task) -> List[AgentCapability]:
        """Find agents suitable for the task"""
        suitable = []
        required_specializations = task.requirements.get('specializations', [])

        for agent in self.agents.values():
            # Check availability
            if not agent.availability or agent.current_load >= agent.max_load:
                continue

            # Check specializations
            if required_specializations:
                if any(
                    spec in agent.specializations
                    for spec in required_specializations
                ):
                    suitable.append(agent)
            else:
                suitable.append(agent)

        # Sort by performance score and load
        suitable.sort(
            key=lambda a: (
                a.performance_score * (1 - a.current_load / a.max_load)
            ),
            reverse=True
        )

        return suitable

    async def _execute_on_agent(
        self, agent: AgentCapability, task: Task
    ) -> Any:
        """Execute task on specific agent"""
        agent.current_load += 1

        try:
            # Simulate agent execution (replace with actual agent call)
            logger.debug(f"Executing task {task.id} on agent {agent.agent_id}")
            await asyncio.sleep(0.1)  # Placeholder for actual execution

            # Update performance score based on success
            agent.performance_score = min(1.0, agent.performance_score + 0.01)

            result = {
                "status": "success",
                "agent_id": agent.agent_id,
                "task_id": task.id,
                "timestamp": datetime.now().isoformat()
            }

            return result

        except Exception as e:
            logger.error(
                f"Task {task.id} failed on agent "
                f"{agent.agent_id}: {e}"
            )
            # Decrease performance score
            agent.performance_score = max(0.0, agent.performance_score - 0.05)
            raise

        finally:
            agent.current_load -= 1

    async def _execute_subtask(
        self, agent: AgentCapability, subtask: Dict
    ) -> Any:
        """Execute subtask on agent"""
        # Similar to _execute_on_agent but for subtasks
        return await self._execute_on_agent(agent, Task(
            id=subtask['id'],
            type=subtask['type'],
            priority=TaskPriority.NORMAL,
            requirements=subtask.get('requirements', {}),
            context=subtask.get('context', {})
        ))

    def _create_subtasks(self, task: Task, num_subtasks: int) -> List[Dict]:
        """Break task into subtasks"""
        subtasks = []
        for i in range(num_subtasks):
            subtasks.append({
                'id': f"{task.id}_sub_{i}",
                'type': f"{task.type}_part",
                'requirements': task.requirements,
                'context': {
                    **task.context,
                    'subtask_index': i,
                    'total_subtasks': num_subtasks
                }
            })
        return subtasks

    async def _merge_results(self, results: List[Any]) -> Any:
        """Merge results from collaborative execution"""
        # Simple merge - can be enhanced based on task type
        return {
            "merged": True,
            "results": results,
            "count": len(results)
        }

    async def _achieve_consensus(self, results: List[Any]) -> Any:
        """Achieve consensus from multiple agent results"""
        # Majority voting or weighted consensus
        # For now, return most common result or first result
        if not results:
            return None

        # Count occurrences
        from collections import Counter
        result_counter = Counter(str(r) for r in results)
        most_common = result_counter.most_common(1)[0][0]

        # Find original result
        consensus_result = next(r for r in results if str(r) == most_common)

        logger.info(f"Consensus achieved: {result_counter.most_common()}")
        return consensus_result

    def _complete_task(self, task: Task):
        """Move task to completed"""
        if task.id in self.active_tasks:
            del self.active_tasks[task.id]
        self.completed_tasks.append(task)
        logger.info(f"✅ Task {task.id} completed with status: {task.status}")

    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get status of a task"""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            return {
                "id": task.id,
                "type": task.type,
                "status": task.status,
                "priority": task.priority.name,
                "assigned_agents": task.assigned_agents,
                "created_at": task.created_at.isoformat()
            }

        # Check completed tasks
        completed = next(
            (t for t in self.completed_tasks if t.id == task_id),
            None
        )
        if completed:
            return {
                "id": completed.id,
                "type": completed.type,
                "status": completed.status,
                "priority": completed.priority.name,
                "result": completed.result,
                "created_at": completed.created_at.isoformat()
            }

        return None

    async def get_status(self) -> Dict[str, Any]:
        """Get orchestrator status"""
        return {
            "running": self._running,
            "total_agents": len(self.agents),
            "active_agents": sum(
                1 for a in self.agents.values() if a.availability
            ),
            "active_tasks": len(self.active_tasks),
            "completed_tasks": len(self.completed_tasks),
            "queue_size": self.task_queue.qsize(),
            "strategy": self.strategy.value,
            "agents": {
                agent_id: {
                    "specializations": agent.specializations,
                    "performance": agent.performance_score,
                    "load": f"{agent.current_load}/{agent.max_load}",
                    "available": agent.availability
                }
                for agent_id, agent in self.agents.items()
            }
        }

    async def set_strategy(self, strategy: OrchestrationStrategy):
        """Change orchestration strategy"""
        self.strategy = strategy
        logger.info(f"Strategy changed to: {strategy.value}")

    async def shutdown(self):
        """Shutdown orchestrator"""
        logger.info("Shutting down orchestrator...")
        self._running = False

        # Wait for active tasks to complete
        while self.active_tasks:
            await asyncio.sleep(0.1)

        logger.info("Orchestrator shutdown complete")
