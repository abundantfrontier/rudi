from abc import ABC, abstractmethod
from typing import Any, Dict, List
from core.models.models import CapabilityRequest

class CapabilityPlugin(ABC):
    @property
    @abstractmethod
    def capability_type(self) -> str:
        """Return the string identifier for this capability (e.g. 'database:query')"""
        pass

    @abstractmethod
    def validate_args(self, args: Dict[str, Any]) -> bool:
        """Verify that the execution arguments are valid for this capability."""
        pass

    @abstractmethod
    def execute(self, agent_id: str, args: Dict[str, Any]) -> Any:
        """Perform the actual action."""
        pass
