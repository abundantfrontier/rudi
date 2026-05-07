from typing import Dict, Any, Optional
from core.interfaces.enforcement import NetworkEnforcement

class LinuxNetworkEnforcement(NetworkEnforcement):
    def __init__(self, control_plane):
        self.control_plane = control_plane

    def validate_host(self, host: str) -> str:
        """Normalize host (lower case, trim)."""
        return host.strip().lower()

    def check_permission(self, agent_id: str, action: str, resource_details: Dict[str, Any], project_id: Optional[str] = None) -> bool:
        if "host" in resource_details:
            resource_details["host"] = self.validate_host(resource_details["host"])
        
        return self.control_plane.validate_grant(agent_id, action, resource_details, project_id=project_id)

    def connect(self, agent_id: str, host: str, port: int, project_id: Optional[str] = None) -> bool:
        """Enforced network connection."""
        normalized_host = self.validate_host(host)
        if self.check_permission(agent_id, "network:connect", {"host": normalized_host, "port": port}, project_id=project_id):
            # In a real implementation, this would open the socket
            print(f"[Network] R.U.D.I. ALLOWED connection to {normalized_host}:{port}")
            return True
        else:
            print(f"[Network] R.U.D.I. BLOCKED connection to {normalized_host}:{port}")
            return False
