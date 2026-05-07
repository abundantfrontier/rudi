import subprocess
import os
from typing import Dict, Any, List, Optional
from core.interfaces.enforcement import ProcessEnforcement

class LinuxProcessEnforcement(ProcessEnforcement):
    def __init__(self, control_plane):
        self.control_plane = control_plane

    def check_permission(self, agent_id: str, action: str, resource_details: Dict[str, Any], project_id: Optional[str] = None) -> bool:
        return self.control_plane.validate_grant(agent_id, action, resource_details, project_id=project_id)

    def execute(self, agent_id: str, command: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute a command string."""
        return self.run_command(agent_id, command.split(), project_id=project_id)

    def run_command(self, agent_id: str, command: List[str], cwd: str = None, project_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a command if permitted. 
        Note: For a production R.U.D.I., this would use 'bubblewrap', 
        'firejail', or 'nsjail' for real Linux sandboxing.
        """
        cmd_str = " ".join(command)
        if self.check_permission(agent_id, "process:execute", {"command": cmd_str}, project_id=project_id):
            print(f"[Process] R.U.D.I. ALLOWED execution: {cmd_str}")
            try:
                result = subprocess.run(
                    command, 
                    capture_output=True, 
                    text=True, 
                    cwd=cwd or os.getcwd(),
                    timeout=30
                )
                return {
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode
                }
            except Exception as e:
                return {"error": str(e)}
        else:
            print(f"[Process] R.U.D.I. BLOCKED execution: {cmd_str}")
            raise PermissionError(f"R.U.D.I. blocked process execution: {cmd_str}")
