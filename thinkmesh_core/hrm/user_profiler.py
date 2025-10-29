# User Profiler
import logging
logger = logging.getLogger(__name__)


class UserProfiler:
    def __init__(self):
        self.profiles = {}

    async def create_profile(self, user_id, data):
        self.profiles[user_id] = data
        logger.info(f"Profile created for {user_id}")
        return self.profiles[user_id]
