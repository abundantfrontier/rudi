import unittest
import asyncio
import os
import uuid
from core.control_plane.manager import ControlPlaneManager
from core.models.models import CapabilityRequest, CapabilityType

class TestAgentIdentity(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = f"test_identity_{uuid.uuid4().hex[:6]}.db"
        self.config = {"approval_timeout": 60, "db_path": self.db_path}
        self.cp = ControlPlaneManager(self.config)

    async def asyncTearDown(self):
        self.cp.shutdown()
        if os.path.exists(self.db_path): os.remove(self.db_path)

    async def test_unregistered_agent_passes(self):
        # By default, if no agents are registered, it passes for backward compatibility
        req = CapabilityRequest(
            agent_id="agent-001",
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": "/tmp/test.txt"},
            purpose="Testing"
        )
        self.cp.register_agent("other-agent", "secret-token")
        
        # Now agent-001 is NOT registered, and there ARE registered agents
        grant = await self.cp.request_capability(req)
        self.assertIsNone(grant)
        self.assertEqual(self.cp.metrics["total_denials"], 1)

    async def test_registered_agent_correct_token(self):
        self.cp.register_agent("agent-001", "secret-token")
        req = CapabilityRequest(
            agent_id="agent-001",
            agent_token="secret-token",
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": "/tmp/test.txt"},
            purpose="Testing"
        )
        # Identity passes, but denied by policy (no ui handler)
        grant = await self.cp.request_capability(req)
        self.assertIsNone(grant)
        self.assertEqual(self.cp.metrics["total_denials"], 1)
        
    async def test_registered_agent_wrong_token(self):
        self.cp.register_agent("agent-001", "secret-token")
        req = CapabilityRequest(
            agent_id="agent-001",
            agent_token="wrong-token",
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": "/tmp/test.txt"},
            purpose="Testing"
        )
        grant = await self.cp.request_capability(req)
        self.assertIsNone(grant)
        self.assertEqual(self.cp.metrics["total_denials"], 1)

    async def test_strict_identity_mode(self):
        # Enable strict mode
        self.cp.strict_identity = True
        
        # 1. Unregistered agent should fail
        req = CapabilityRequest(
            agent_id="unregistered-agent",
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": "/tmp/test.txt"},
            purpose="Testing"
        )
        grant = await self.cp.request_capability(req)
        self.assertIsNone(grant)
        self.assertEqual(self.cp.metrics["identity_failures"], 1)
        
        # 2. Registered agent with correct token should pass identity
        self.cp.register_agent("agent-001", "secret-token")
        req = CapabilityRequest(
            agent_id="agent-001",
            agent_token="secret-token",
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": "/tmp/test.txt"},
            purpose="Testing"
        )
        grant = await self.cp.request_capability(req)
        self.assertEqual(self.cp.metrics["identity_failures"], 1) 
        self.assertEqual(self.cp.metrics["total_denials"], 2)

    async def test_metrics_exposure(self):
        self.cp.register_agent("agent-001", "secret-token")
        req = CapabilityRequest(
            agent_id="agent-001",
            agent_token="secret-token",
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": "/tmp/test.txt"},
            purpose="Testing"
        )
        await self.cp.request_capability(req)
        metrics = self.cp.get_metrics()
        self.assertIn("total_requests", metrics)
        self.assertEqual(metrics["total_requests"], 1)
        self.assertEqual(metrics["registered_agents_count"], 1)

if __name__ == "__main__":
    unittest.main()
