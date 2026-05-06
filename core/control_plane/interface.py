from abc import ABC, abstractmethod
from typing import Dict, Any
from core.models.models import CapabilityRequest, CapabilityGrant

class ControlPlaneInterface(ABC):
    @abstractmethod
    def request_capability(self, request: CapabilityRequest) -> CapabilityGrant:
        """
        Handle a capability request from an agent. 
        Triggers policy evaluation and human approval if needed.
        """
        pass

    @abstractmethod
    def validate_grant(self, agent_id: str, capability_type: str, scope: Dict[str, Any]) -> bool:
        """
        Check if a valid grant exists for the given agent and action.
        Used by enforcement layers.
        """
        pass

    @abstractmethod
    def revoke_grant(self, grant_id: str) -> bool:
        """
        Manually revoke an active grant.
        """
        pass
