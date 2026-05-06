from core.interfaces.enforcement import NetworkEnforcement
from typing import Dict, Any

class LinuxNetworkEnforcement(NetworkEnforcement):
    def __init__(self, control_plane):
        self.control_plane = control_plane

    def validate_host(self, host: str) -> str:
        return host.strip().lower()

    def check_permission(self, agent_id: str, action: str, resource_details: Dict[str, Any]) -> bool:
        if "host" in resource_details:
            resource_details["host"] = self.validate_host(resource_details["host"])
        return self.control_plane.validate_grant(agent_id, action, resource_details)
