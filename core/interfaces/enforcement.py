from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class BaseEnforcement(ABC):
    @abstractmethod
    def check_permission(self, agent_id: str, action: str, resource_details: Dict[str, Any], project_id: Optional[str] = None) -> bool:
        """
        The low-level check that actually blocks or allows access.
        This will call back into the ControlPlaneManager.
        """
        pass

class FilesystemEnforcement(BaseEnforcement):
    @abstractmethod
    def validate_path(self, path: str) -> str:
        """
        Normalize and validate a path for the specific platform.
        """
        pass

class NetworkEnforcement(BaseEnforcement):
    @abstractmethod
    def validate_host(self, host: str) -> str:
        """
        Normalize and validate a host/domain.
        """
        pass

class ProcessEnforcement(BaseEnforcement):
    @abstractmethod
    def execute(self, agent_id: str, command: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a command string.
        """
        pass

    @abstractmethod
    def run_command(self, agent_id: str, command: List[str], cwd: str = None, project_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a command in a platform-specific sandbox.
        """
        pass
