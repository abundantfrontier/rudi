import os
from typing import Dict, Any, Optional
from core.interfaces.enforcement import FilesystemEnforcement

class DarwinFilesystemEnforcement(FilesystemEnforcement):
    def __init__(self, control_plane):
        self.control_plane = control_plane

    def validate_path(self, path: str) -> str:
        """Normalize to absolute real path, resolving symlinks."""
        return os.path.realpath(os.path.expanduser(path))

    def check_permission(self, agent_id: str, action: str, resource_details: Dict[str, Any], project_id: Optional[str] = None) -> bool:
        # Normalize the path in resource_details
        if "path" in resource_details:
            resource_details["path"] = self.validate_path(resource_details["path"])
        
        return self.control_plane.validate_grant(agent_id, action, resource_details, project_id=project_id)

    def read_file(self, agent_id: str, path: str, project_id: Optional[str] = None) -> str:
        """Enforced read operation."""
        normalized_path = self.validate_path(path)
        if self.check_permission(agent_id, "filesystem:read", {"path": normalized_path}, project_id=project_id):
            with open(normalized_path, 'r') as f:
                return f.read()
        else:
            raise PermissionError(f"R.U.D.I. blocked read access to {normalized_path}")

    def write_file(self, agent_id: str, path: str, content: str, project_id: Optional[str] = None):
        """Enforced write operation."""
        normalized_path = self.validate_path(path)
        if self.check_permission(agent_id, "filesystem:write", {"path": normalized_path}, project_id=project_id):
            with open(normalized_path, 'w') as f:
                f.write(content)
        else:
            raise PermissionError(f"R.U.D.I. blocked write access to {normalized_path}")
