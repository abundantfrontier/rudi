import unittest
import asyncio
import os
import uuid
from core.control_plane.server import ControlPlaneServer
from core.control_plane.client import ControlPlaneClient
from core.models.models import CapabilityRequest, CapabilityType, GrantType, CapabilityGrant

class TestPhase10Network(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.socket_path = f"/tmp/rudi_test_p10_{uuid.uuid4().hex[:6]}.sock"
        self.db_path = f"test_p10_{uuid.uuid4().hex[:6]}.db"
        self.config = {
            "default_deny": True,
            "db_path": self.db_path
        }
        self.server = ControlPlaneServer(self.config, socket_path=self.socket_path)
        self.server_task = asyncio.create_task(self.server.start())
        
        for _ in range(10):
            if os.path.exists(self.socket_path): break
            await asyncio.sleep(0.1)
            
        self.client = ControlPlaneClient(socket_path=self.socket_path)
        await self.client.connect()

    async def asyncTearDown(self):
        await self.client.close()
        self.server_task.cancel()
        try:
            await self.server_task
        except asyncio.CancelledError:
            pass
        if os.path.exists(self.socket_path): os.remove(self.socket_path)
        if os.path.exists(self.db_path): os.remove(self.db_path)

    async def test_http_get_success(self):
        agent_id = "agent-http"
        url = "https://example.com"
        
        # Inject grant
        grant = CapabilityGrant(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            capability=CapabilityType.NETWORK_HTTP,
            scope={"url_pattern": "https://example.com*", "allowed_methods": ["GET"]},
            grant_type=GrantType.SESSION
        )
        self.server.manager.grants[grant.id] = grant
        
        # Execute GET
        res = await self.client.http_request(agent_id, "GET", url)
        self.assertEqual(res["status_code"], 200)
        self.assertIn("Example Domain", str(res["content"]))

    async def test_http_post_blocked_by_method(self):
        agent_id = "agent-http"
        url = "https://example.com"
        
        # Grant only allows GET
        grant = CapabilityGrant(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            capability=CapabilityType.NETWORK_HTTP,
            scope={"url_pattern": "https://example.com*", "allowed_methods": ["GET"]},
            grant_type=GrantType.SESSION
        )
        self.server.manager.grants[grant.id] = grant
        
        # Attempt POST
        with self.assertRaises(Exception) as cm:
            await self.client.http_request(agent_id, "POST", url, body="data")
        self.assertIn("blocked", str(cm.exception))

    async def test_http_blocked_by_url_pattern(self):
        agent_id = "agent-http"
        
        # Grant only allows example.com
        grant = CapabilityGrant(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            capability=CapabilityType.NETWORK_HTTP,
            scope={"url_pattern": "https://example.com/*", "allowed_methods": ["GET"]},
            grant_type=GrantType.SESSION
        )
        self.server.manager.grants[grant.id] = grant
        
        # Attempt to access google.com
        with self.assertRaises(Exception) as cm:
            await self.client.http_request(agent_id, "GET", "https://google.com")
        self.assertIn("blocked", str(cm.exception))

if __name__ == "__main__":
    unittest.main()
