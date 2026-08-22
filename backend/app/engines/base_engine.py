from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseEngine(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tick_count = 0
        self.is_running = False

    @abstractmethod
    def reset(self) -> None:
        self.tick_count = 0
        self.is_running = False

    @abstractmethod
    def tick(self) -> Dict[str, Any]:
        self.tick_count += 1
        return {}
