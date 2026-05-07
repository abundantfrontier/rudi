import unittest
import asyncio
import os
import json
import uuid
from core.control_plane.server import ControlPlaneServer
from core.control_plane.client import ControlPlaneClient
from core.models.models import CapabilityRequest, CapabilityType, GrantType

class TestPhase6IPC(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.socket_path = f"/tmp/rudi_test_{uuid.uuid4().hex[:6]}.sock"
        self.db_path = f"test_phase6_{uuid.uuid4().hex[:6]}.db"
        self.config = {
            "default_deny": True,
            "db_path": self.db_path,
            "approval_timeout": 5
        }
        self.server = ControlPlaneServer(self.config, socket_path=self.socket_path)
        self.server_task = asyncio.create_task(self.server.start())
        
        # Wait for server
        for _ in range(20):
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
        
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_ping(self):
        result = await self.client.ping()
        self.assertEqual(result, "pong")

    async def test_capability_request_flow_with_mock_ui(self):
        # 1. Setup UI via raw connection to avoid client listener conflict
        ui_reader, ui_writer = await asyncio.open_unix_connection(self.socket_path)
        
        # Register UI
        reg_msg = {"jsonrpc": "2.0", "method": "system.register_ui", "params": {}, "id": "reg-1"}
        ui_writer.write((json.dumps(reg_msg) + "\n").encode())
        await ui_writer.drain()
        await ui_reader.readline() # Consume registration response

        # 2. Agent requests capability
        req = CapabilityRequest(
            agent_id="test-agent",
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": "/tmp/test.txt"},
            purpose="Testing IPC"
        )
        request_task = asyncio.create_task(self.client.request_capability(req))

        # 3. UI receives notification
        line = await asyncio.wait_for(ui_reader.readline(), timeout=2.0)
        notification = json.loads(line.decode())
        self.assertEqual(notification["method"], "approval.required")
        approval_id = notification["params"]["approval_id"]

        # 4. UI approves
        app_msg = {
            "jsonrpc": "2.0", 
            "method": "grant.approve", 
            "params": {"approval_id": approval_id, "grant_type": "allow_once"},
            "id": "app-1"
        }
        ui_writer.write((json.dumps(app_msg) + "\n").encode())
        await ui_writer.drain()
        await ui_reader.readline() # Consume approval response

        # 5. Agent receives grant
        grant = await asyncio.wait_for(request_task, timeout=2.0)
        self.assertIsNotNone(grant)
        self.assertEqual(grant["agent_id"], "test-agent")

        ui_writer.close()
        await ui_writer.wait_closed()

    async def test_strict_server_side_enforcement(self):
        agent_id = "agent-strict"
        path = os.path.abspath("test_strict.txt")
        with open(path, "w") as f: f.write("top secret")
        
        from core.models.models import CapabilityGrant
        grant = CapabilityGrant(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": path},
            grant_type=GrantType.SESSION
        )
        self.server.manager.grants[grant.id] = grant

        result = await self.client.execute(agent_id, CapabilityType.FILESYSTEM_READ, {"path": path})
        self.assertEqual(result["content"], "top secret")

        with self.assertRaises(Exception) as cm:
            await self.client.execute(agent_id, CapabilityType.FILESYSTEM_READ, {"path": "/etc/passwd"})
        self.assertIn("blocked", str(cm.exception))

        os.remove(path)

if __name__ == "__main__":
    unittest.main()
