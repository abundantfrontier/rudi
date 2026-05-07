import asyncio
import os
import uuid
import sys

# Ensure project root is in path
sys.path.append(os.getcwd())

from core.models.models import CapabilityRequest, CapabilityType
from core.control_plane.client import ControlPlaneClient

async def manual_verify():
    client = ControlPlaneClient()
    try:
        await client.connect()
    except Exception as e:
        print(f"FAILED to connect to R.U.D.I. Server: {e}")
        return
    
    agent_id = f"agent-verify-{uuid.uuid4().hex[:4]}"
    url = "https://example.com"
    
    print(f"--- Verifying Phase 10: Network Mediation ---")
    print(f"URL: {url}")

    # 1. Request Read-Only (GET) Grant
    print("\n[Action] Requesting GET capability...")
    request = CapabilityRequest(
        agent_id=agent_id,
        capability=CapabilityType.NETWORK_HTTP,
        scope={"url_pattern": "https://example.com*", "allowed_methods": ["GET"]},
        purpose="Verification of read-only network mediation."
    )
    
    grant = await client.request_capability(request)
    if not grant:
        print("FAILED: Grant denied.")
        return
    
    # 2. Test GET (Should Succeed)
    print("\n[Attempt 1] GET request (Expected: Success)...")
    res = await client.http_request(agent_id, "GET", url)
    print(f"Result Status: {res['status_code']}")
    if res['status_code'] == 200:
        print("SUCCESS: GET mediated correctly.")
    
    # 3. Test POST (Should Fail)
    print("\n[Attempt 2] POST request (Expected: Blocked)...")
    try:
        await client.http_request(agent_id, "POST", url, body="malicious data")
        print("FAILED: POST was NOT blocked!")
    except Exception as e:
        print(f"SUCCESS: POST blocked as expected: {e}")

    await client.close()

if __name__ == "__main__":
    asyncio.run(manual_verify())
