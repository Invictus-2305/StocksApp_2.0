from abc import ABC, abstractmethod

class BaseBroker(ABC):
    """
    Abstract base class for all brokers.
    """
    
    @abstractmethod
    async def authenticate(self, user_config: dict) -> bool:
        """
        Authenticate with the broker using user's configuration.
        """
        pass
        
    @abstractmethod
    async def place_bracket_order(self, signal: dict, quantity: int) -> dict:
        """
        Place a bracket order (Entry, Target, Stop-loss).
        """
        pass
