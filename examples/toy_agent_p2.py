import sys
import os
import uuid
import time

# Ensure project root is in path
sys.path.append(os.getcwd())

from core.models.models import CapabilityRequest, CapabilityType, GrantType
from core.control_plane.manager import ControlPlaneManager
from ui.dialog import CLIDialog
from adapters.platform_adapter import get_platform_adapter

def run_phase2_toy_agent():
    print("--- R.U.D.I. Phase 2 Toy Agent Starting ---")
    
    config = {"default_deny": True}
    ui = CLIDialog()
    cp = ControlPlaneManager(config, ui_handler=ui)
    adapter = get_platform_adapter(cp)
    fs = adapter["fs"]
    net = adapter["net"]
    
    agent_id = f"agent-{uuid.uuid4().hex[:6]}"
    print(f"Agent ID: {agent_id}\n")

    # 1. Demonstrate Time-Boxed Filesystem Access
    test_path = os.path.abspath("phase2_demo.txt")
    with open(test_path, "w") as f: f.write("Phase 2 content")
    
    print("[Action] Requesting TIME-BOXED read for filesystem...")
    print("(Tip: Choose option [2] and enter '5' seconds)")
    
    request_fs = CapabilityRequest(
        agent_id=agent_id,
        capability=CapabilityType.FILESYSTEM_READ,
        scope={"path": test_path},
        purpose="Demonstrating time-boxed access."
    )
    
    grant_fs = cp.request_capability(request_fs)
    if grant_fs:
        print(f"\n[Success] Reading file: {fs.read_file(agent_id, test_path)}")
        print("Waiting 6 seconds for grant to expire...")
        time.sleep(6)
        try:
            fs.read_file(agent_id, test_path)
        except PermissionError as e:
            print(f"[Blocked] Access denied after expiration: {e}")

    # 2. Demonstrate Session Network Access
    print("\n" + "="*40)
    print("[Action] Requesting SESSION access for network...")
    print("(Tip: Choose option [3] for Session)")
    
    host = "api.example.com"
    request_net = CapabilityRequest(
        agent_id=agent_id,
        capability=CapabilityType.NETWORK_CONNECT,
        scope={"host": host, "port": 443},
        purpose="Demonstrating session-based network access."
    )
    
    grant_net = cp.request_capability(request_net)
    if grant_net:
        print("\n[Success] First connection attempt...")
        net.connect(agent_id, host, 443)
        print("[Success] Second connection attempt (no prompt needed)...")
        net.connect(agent_id, host, 443)
        
        # 3. Demonstrate Revocation
        print("\n[Action] Manually revoking the network grant...")
        cp.revoke_grant(grant_net.id)
        print("[Blocked] Third attempt after revocation...")
        net.connect(agent_id, host, 443)

    # 4. Show Active Grants
    active = cp.get_active_grants(agent_id)
    ui.show_active_grants(active)

    # Cleanup
    if os.path.exists(test_path):
        os.remove(test_path)

if __name__ == "__main__":
    run_phase2_toy_agent()
