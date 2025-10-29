# Strategic Planning
import logging
logger = logging.getLogger(__name__)


class StrategicPlanner:
    def __init__(self):
        self.plans = []

    async def create_plan(self, goal):
        plan = {"goal": goal, "steps": []}
        self.plans.append(plan)
        return plan
