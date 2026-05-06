import os
from typing import Dict, Any
from core.interfaces.enforcement import FilesystemEnforcement

class DarwinFilesystemEnforcement(FilesystemEnforcement):
    def __init__(self, control_plane):
        self.control_plane = control_plane

    def validate_path(self, path: str) -> str:
        """Normalize to absolute real path, resolving symlinks."""
        return os.path.realpath(os.path.expanduser(path))

    def check_permission(self, agent_id: str, action: str, resource_details: Dict[str, Any]) -> bool:
        # Normalize the path in resource_details
        if "path" in resource_details:
            resource_details["path"] = self.validate_path(resource_details["path"])
        
        return self.control_plane.validate_grant(agent_id, action, resource_details)

    def read_file(self, agent_id: str, path: str) -> str:
        """Enforced read operation."""
        normalized_path = self.validate_path(path)
        if self.check_permission(agent_id, "filesystem:read", {"path": normalized_path}):
            with open(normalized_path, 'r') as f:
                return f.read()
        else:
            raise PermissionError(f"R.U.D.I. blocked read access to {normalized_path}")
