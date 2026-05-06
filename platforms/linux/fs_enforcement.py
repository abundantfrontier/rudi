from core.interfaces.enforcement import FilesystemEnforcement
from typing import Dict, Any

class LinuxFilesystemEnforcement(FilesystemEnforcement):
    def __init__(self, control_plane):
        self.control_plane = control_plane

    def validate_path(self, path: str) -> str:
        import os
        return os.path.realpath(os.path.expanduser(path))

    def check_permission(self, agent_id: str, action: str, resource_details: Dict[str, Any]) -> bool:
        if "path" in resource_details:
            resource_details["path"] = self.validate_path(resource_details["path"])
        return self.control_plane.validate_grant(agent_id, action, resource_details)
