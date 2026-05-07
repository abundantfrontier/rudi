import sys
import os
import uuid
import asyncio

# Ensure project root is in path
sys.path.append(os.getcwd())

from core.models.models import CapabilityRequest, CapabilityType
from core.control_plane.client import ControlPlaneClient

async def run_toy_agent():
    print("--- R.U.D.I. Toy Agent (IPC Mode) Starting ---")
    
    # 1. Initialize R.U.D.I. Client
    client = ControlPlaneClient()
    try:
        await client.connect()
    except Exception as e:
        print(f"FAILED to connect to R.U.D.I. Server: {e}")
        print("Make sure 'python3 core/control_plane/server.py' is running.")
        return
    
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
        await client.execute(agent_id, CapabilityType.FILESYSTEM_READ, {"path": dummy_path})
    except Exception as e:
        print(f"Blocked as expected: {e}")
    
    # 4. Request capability
    print("\n[Action] Requesting read capability...")
    request = CapabilityRequest(
        agent_id=agent_id,
        capability=CapabilityType.FILESYSTEM_READ,
        scope={"path": dummy_path},
        purpose="Agent needs to read the greeting file."
    )
    
    grant_data = await client.request_capability(request)
    
    if grant_data:
        print(f"Grant obtained: {grant_data['id']}")
        
        # 5. Second attempt (should succeed)
        print("\n[Attempt 2] Reading with grant...")
        result = await client.execute(agent_id, CapabilityType.FILESYSTEM_READ, {"path": dummy_path})
        print(f"Success! File content: '{result['content']}'")
        
        # 6. Third attempt (should fail, Allow Once is consumed)
        print("\n[Attempt 3] Reading again (Allow Once should be expired)...")
        try:
            await client.execute(agent_id, CapabilityType.FILESYSTEM_READ, {"path": dummy_path})
        except Exception as e:
            print(f"Blocked as expected: {e}")
    else:
        print("Grant denied by user.")

    # Cleanup
    if os.path.exists(dummy_path):
        os.remove(dummy_path)
    await client.close()

if __name__ == "__main__":
    asyncio.run(run_toy_agent())
