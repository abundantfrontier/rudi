import unittest
import asyncio
import os
import uuid
from core.control_plane.manager import ControlPlaneManager
from core.models.models import CapabilityRequest, CapabilityType, GrantType, CapabilityGrant
from datetime import datetime, timedelta

class TestAttenuatedGrants(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = f"test_attenuation_{uuid.uuid4().hex[:6]}.db"
        self.config = {"db_path": self.db_path, "default_deny": True}
        self.cp = ControlPlaneManager(self.config)

    async def asyncTearDown(self):
        self.cp.shutdown()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_attenuation_success(self):
        # 1. Setup a parent broad grant
        agent_id = "agent-parent"
        parent_path = os.path.realpath("/tmp/parent_dir")
        parent_grant = CapabilityGrant(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": parent_path},
            grant_type=GrantType.SESSION,
            expires_at=datetime.now() + timedelta(hours=1)
        )
        self.cp.grants[parent_grant.id] = parent_grant
        self.cp.storage.save_grant(parent_grant)

        # 2. Request an attenuated (narrower) grant
        child_path = os.path.realpath(os.path.join(parent_path, "subfile.txt"))
        req = CapabilityRequest(
            agent_id=agent_id,
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": child_path},
            purpose="Need access to just this file",
            parent_grant_id=parent_grant.id
        )
        
        # 3. Request should be auto-approved without UI
        grant = await self.cp.request_capability(req)
        self.assertIsNotNone(grant)
        self.assertEqual(grant.parent_id, parent_grant.id)
        self.assertEqual(os.path.realpath(grant.scope["path"]), child_path)
        self.assertEqual(grant.agent_id, agent_id)

    async def test_attenuation_fails_if_too_broad(self):
        # 1. Setup parent
        agent_id = "agent-parent"
        parent_path = os.path.abspath("/tmp/parent_dir")
        parent_grant = CapabilityGrant(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": parent_path},
            grant_type=GrantType.SESSION
        )
        self.cp.grants[parent_grant.id] = parent_grant

        # 2. Request a broader path
        req = CapabilityRequest(
            agent_id=agent_id,
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": os.path.abspath("/etc")},
            purpose="Maliciously broad request",
            parent_grant_id=parent_grant.id
        )
        
        # 3. Should be denied
        grant = await self.cp.request_capability(req)
        self.assertIsNone(grant)
        self.assertEqual(self.cp.metrics["total_denials"], 1)

    async def test_attenuation_fails_if_agent_mismatch(self):
        # 1. Setup parent for agent A
        parent_grant = CapabilityGrant(
            id=str(uuid.uuid4()),
            agent_id="agent-A",
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": "/tmp"},
            grant_type=GrantType.SESSION
        )
        self.cp.grants[parent_grant.id] = parent_grant

        # 2. Agent B tries to derive from Agent A's grant
        req = CapabilityRequest(
            agent_id="agent-B",
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": "/tmp/sub"},
            purpose="Theft attempt",
            parent_grant_id=parent_grant.id
        )
        
        # 3. Should be denied
        grant = await self.cp.request_capability(req)
        self.assertIsNone(grant)

if __name__ == "__main__":
    unittest.main()
