import sys
import os
import uuid

# Ensure project root is in path
sys.path.append(os.getcwd())

from core.models.models import CapabilityRequest, CapabilityType
from core.control_plane.manager import ControlPlaneManager
from ui.dialog import CLIDialog
from adapters.platform_adapter import get_platform_adapter

def run_toy_agent():
    print("--- R.U.D.I. Toy Agent Starting ---")
    
    # 1. Initialize R.U.D.I.
    config = {"default_deny": True}
    ui = CLIDialog()
    cp = ControlPlaneManager(config, ui_handler=ui)
    adapter = get_platform_adapter(cp)
    fs = adapter["fs"]
    
    agent_id = f"agent-{uuid.uuid4().hex[:6]}"
    
    # 2. Create a dummy file to read
    dummy_path = os.path.abspath("hello_rudi.txt")
    with open(dummy_path, "w") as f:
        f.write("Hello from the R.U.D.I. secure environment!")
    
    print(f"Agent ID: {agent_id}")
    print(f"Attempting to read: {dummy_path}")
    
    try:
        # 3. First attempt (should fail without grant)
        print("\n[Attempt 1] Reading without grant...")
        fs.read_file(agent_id, dummy_path)
    except PermissionError as e:
        print(f"Blocked as expected: {e}")
    
    # 4. Request capability
    print("\n[Action] Requesting read capability...")
    request = CapabilityRequest(
        agent_id=agent_id,
        capability=CapabilityType.FILESYSTEM_READ,
        scope={"path": dummy_path},
        purpose="Agent needs to read the greeting file."
    )
    
    grant = cp.request_capability(request)
    
    if grant:
        print(f"Grant obtained: {grant.id}")
        
        # 5. Second attempt (should succeed)
        print("\n[Attempt 2] Reading with grant...")
        content = fs.read_file(agent_id, dummy_path)
        print(f"Success! File content: '{content}'")
        
        # 6. Third attempt (should fail, Allow Once is consumed)
        print("\n[Attempt 3] Reading again (Allow Once should be expired)...")
        try:
            fs.read_file(agent_id, dummy_path)
        except PermissionError as e:
            print(f"Blocked as expected: {e}")
    else:
        print("Grant denied by user.")

    # Cleanup
    if os.path.exists(dummy_path):
        os.remove(dummy_path)

if __name__ == "__main__":
    run_toy_agent()
