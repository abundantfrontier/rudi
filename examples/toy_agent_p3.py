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

def run_phase3_toy_agent():
    print("--- R.U.D.I. Phase 3 Toy Agent Starting ---")
    
    config = {
        "default_deny": True,
        "approval_timeout": 5  # Short timeout for demo
    }
    ui = CLIDialog()
    cp = ControlPlaneManager(config, ui_handler=ui)
    adapter = get_platform_adapter(cp)
    fs = adapter["fs"]
    
    agent_id = f"agent-p3-{uuid.uuid4().hex[:6]}"
    print(f"Agent ID: {agent_id}\n")

    # 1. Demonstrate Background Request with Timeout
    print("[Action] Requesting BACKGROUND read for filesystem...")
    print("(Tip: Wait 5 seconds and let it timeout to see 'Unreachable User' logic)")
    
    request_bg = CapabilityRequest(
        agent_id=agent_id,
        capability=CapabilityType.FILESYSTEM_READ,
        scope={"path": "/tmp/bg_test"},
        purpose="Autonomous background task.",
        background=True
    )
    
    grant_bg = cp.request_capability(request_bg)
    if not grant_bg:
        print("\n[Result] Background request denied (likely due to timeout).")
    
    # 2. Demonstrate Stale Grant Detection
    print("\n" + "="*40)
    print("[Action] Requesting a long-lived Session grant...")
    print("(Tip: Choose [3] for Session)")
    
    request_session = CapabilityRequest(
        agent_id=agent_id,
        capability=CapabilityType.FILESYSTEM_READ,
        scope={"path": "/tmp/session_test"},
        purpose="Simulating a persistent task."
    )
    cp.request_capability(request_session)
    
    print("\nSimulating 2 seconds of inactivity...")
    time.sleep(2)
    
    # Check for stale grants (idle > 1s for demo)
    stale = cp.get_stale_grants(idle_seconds=1)
    if stale:
        print(f"\n[Security Alert] Found {len(stale)} stale grant(s):")
        for g in stale:
            print(f" - Stale Grant: {g.capability} for {g.scope}")
            print(f"   Action: Suggesting REVOCATION of {g.id[:8]}")
            cp.revoke_grant(g.id)
            print("   Status: Revoked.")

    # 3. Show Audit Metrics
    print("\n" + "="*40)
    print("R.U.D.I. SYSTEM OBSERVABILITY")
    metrics = cp.audit_store.get_metrics()
    for m, val in metrics.items():
        print(f" {m:15}: {val}")

if __name__ == "__main__":
    run_phase3_toy_agent()
