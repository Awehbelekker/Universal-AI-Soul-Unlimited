# Message Hub
import logging
logger = logging.getLogger(__name__)

class MessageHub:
    def __init__(self):
        self.messages = []
    
    async def broadcast(self, message):
        self.messages.append(message)
        logger.info(f"Broadcasted: {message}")
        return len(self.messages)
