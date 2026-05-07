import unittest
import asyncio
import os
import uuid
import json
from core.control_plane.manager import ControlPlaneManager
from core.control_plane.server import ControlPlaneServer
from core.control_plane.client import ControlPlaneClient
from core.models.models import CapabilityRequest, CapabilityType, GrantType, CapabilityGrant
from core.interfaces.plugin import CapabilityPlugin
from datetime import datetime, timedelta
from typing import Dict, Any

class MockPlugin(CapabilityPlugin):
    @property
    def capability_type(self) -> str:
        return "custom:test"

    def validate_args(self, args: Dict[str, Any]) -> bool:
        return "msg" in args

    def execute(self, agent_id: str, args: Dict[str, Any]) -> Any:
        return {"response": f"Hello {agent_id}, you said: {args['msg']}"}

class TestPhase7Features(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.socket_path = f"/tmp/rudi_test_p7_{uuid.uuid4().hex[:6]}.sock"
        self.db_path = f"test_p7_{uuid.uuid4().hex[:6]}.db"
        
        # 1. Config with Auto-Approval Rules
        self.config = {
            "default_deny": True,
            "db_path": self.db_path,
            "auto_approve_rules": [
                {
                    "capability": CapabilityType.FILESYSTEM_READ,
                    "scope_pattern": {"path": "/tmp/public/*"}
                }
            ]
        }
        
        self.server = ControlPlaneServer(self.config, socket_path=self.socket_path)
        self.server.register_plugin(MockPlugin())
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

    async def test_auto_approval(self):
        # Request a capability that matches an auto-approval rule
        req = CapabilityRequest(
            agent_id="agent-auto",
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": "/tmp/public/info.txt"},
            purpose="Testing auto-approval"
        )
        # Should return a grant immediately without UI
        grant = await self.client.request_capability(req)
        self.assertIsNotNone(grant)
        self.assertEqual(grant["agent_id"], "agent-auto")

    async def test_constraints_time_range(self):
        # 1. Manually inject a grant with a time constraint that's always valid for test
        # (Assuming current time is within 00:00 - 23:59)
        agent_id = "agent-time"
        grant = CapabilityGrant(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            capability=CapabilityType.NETWORK_CONNECT,
            scope={"host": "example.com", "port": 80},
            grant_type=GrantType.SESSION,
            constraints={"time_range": {"start": "00:00", "end": "23:59"}}
        )
        self.server.manager.grants[grant.id] = grant
        
        # Should succeed
        res = await self.client.execute(agent_id, CapabilityType.NETWORK_CONNECT, {"host": "example.com", "port": 80})
        self.assertTrue(res["success"])

        # 2. Inject one that is EXPIRED (time range)
        grant2 = CapabilityGrant(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            capability=CapabilityType.NETWORK_CONNECT,
            scope={"host": "blocked.com", "port": 80},
            grant_type=GrantType.SESSION,
            constraints={"time_range": {"start": "00:00", "end": "00:01"}} # Tiny window
        )
        # Hack to ensure current time is outside (unless test runs exactly at midnight)
        if datetime.now().strftime("%H:%M") != "00:00":
             self.server.manager.grants[grant2.id] = grant2
             with self.assertRaises(Exception):
                 await self.client.execute(agent_id, CapabilityType.NETWORK_CONNECT, {"host": "blocked.com", "port": 80})

    async def test_constraints_max_calls(self):
        agent_id = "agent-limit"
        grant = CapabilityGrant(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            capability=CapabilityType.NETWORK_CONNECT,
            scope={"host": "limited.com", "port": 80},
            grant_type=GrantType.SESSION,
            constraints={"max_calls": 2},
            project_id="default"
        )
        self.server.manager.grants[grant.id] = grant

        # Use 1
        await self.client.execute(agent_id, CapabilityType.NETWORK_CONNECT, {"host": "limited.com", "port": 80}, project_id="default")
        # Use 2
        await self.client.execute(agent_id, CapabilityType.NETWORK_CONNECT, {"host": "limited.com", "port": 80}, project_id="default")
        # Use 3 (Should fail)
        with self.assertRaises(Exception) as cm:
            await self.client.execute(agent_id, CapabilityType.NETWORK_CONNECT, {"host": "limited.com", "port": 80}, project_id="default")
        self.assertIn("blocked", str(cm.exception))

    async def test_plugin_system(self):
        # 1. Request custom capability (No rule, needs UI or injection)
        agent_id = "agent-plugin"
        grant = CapabilityGrant(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            capability="custom:test",
            scope={"msg": "*"},
            grant_type=GrantType.SESSION,
            project_id="default"
        )
        self.server.manager.grants[grant.id] = grant

        # 2. Execute via plugin
        res = await self.client.execute(agent_id, "custom:test", {"msg": "Ping!"}, project_id="default")
        self.assertEqual(res["response"], f"Hello {agent_id}, you said: Ping!")

if __name__ == "__main__":
    unittest.main()
