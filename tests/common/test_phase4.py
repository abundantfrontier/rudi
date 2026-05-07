import unittest
from unittest.mock import AsyncMock, patch
import os
import sys
import time
import uuid

# Ensure project root is in path
sys.path.append(os.getcwd())

from core.models.models import CapabilityRequest, CapabilityType, GrantType
from core.control_plane.manager import ControlPlaneManager
from adapters.platform_adapter import get_platform_adapter

class TestPhase4(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_id = uuid.uuid4().hex[:8]
        self.db_path = f"test_p4_{self.test_id}.db"
        self.log_path = f"test_p4_{self.test_id}.log"
        self.config = {
            "default_deny": True,
            "db_path": self.db_path,
            "log_path": self.log_path
        }
        self.ui_mock = AsyncMock()
        self.cp = ControlPlaneManager(self.config, ui_handler=self.ui_mock)
        self.adapter = get_platform_adapter(self.cp)
        self.proc = self.adapter.get("proc")
        self.net = self.adapter.get("net")

    async def asyncTearDown(self):
        self.cp.shutdown()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.log_path):
            os.remove(self.log_path)

    async def test_process_execute_darwin(self):
        if sys.platform != "darwin":
            self.skipTest("This test requires Darwin")
        
        agent_id = "agent-p4-001"
        command = ["echo", "hello"]
        cmd_str = " ".join(command)
        
        # 1. Grant permission for 'echo'
        self.ui_mock.ask_approval.return_value = (True, GrantType.ALLOW_ONCE, 0)
        request = CapabilityRequest(
            agent_id=agent_id,
            capability=CapabilityType.PROCESS_EXECUTE,
            scope={"command": cmd_str},
            purpose="test echo"
        )
        await self.cp.request_capability(request)
        
        # 2. Run command
        result = self.proc.run_command(agent_id, command)
        self.assertEqual(result["stdout"].strip(), "hello")
        self.assertEqual(result["returncode"], 0)

    async def test_permanent_grant(self):
        agent_id = "agent-p4-002"
        # UI returns (approved, type, duration)
        self.ui_mock.ask_approval.return_value = (True, GrantType.PERMANENT, 0)
        
        request = CapabilityRequest(
            agent_id=agent_id,
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": "/tmp/perm"},
            purpose="permanent access"
        )
        grant = await self.cp.request_capability(request)
        
        self.assertEqual(grant.grant_type, GrantType.PERMANENT)
        self.assertIsNone(grant.expires_at)
        
        # Verify it still works after some simulated time
        self.assertTrue(self.cp.validate_grant(agent_id, CapabilityType.FILESYSTEM_READ, {"path": "/tmp/perm"}))

    async def test_model_escalate_token_budget(self):
        agent_id = "agent-p4-003"
        self.ui_mock.ask_approval.return_value = (True, GrantType.SESSION, 3600)
        
        # Grant 1000 tokens
        request = CapabilityRequest(
            agent_id=agent_id,
            capability=CapabilityType.MODEL_ESCALATE,
            scope={"model_name": "gpt-4", "token_budget": 1000},
            purpose="AI reasoning"
        )
        await self.cp.request_capability(request)
        
        # Use 400 tokens
        self.assertTrue(self.cp.validate_grant(agent_id, CapabilityType.MODEL_ESCALATE, {"model_name": "gpt-4", "tokens": 400}))
        
        # Use 500 tokens
        self.assertTrue(self.cp.validate_grant(agent_id, CapabilityType.MODEL_ESCALATE, {"model_name": "gpt-4", "tokens": 500}))
        
        # Use 200 tokens (should fail, only 100 left)
        self.assertFalse(self.cp.validate_grant(agent_id, CapabilityType.MODEL_ESCALATE, {"model_name": "gpt-4", "tokens": 200}))

    async def test_host_wildcard_matching(self):
        agent_id = "agent-p4-004"
        self.ui_mock.ask_approval.return_value = (True, GrantType.SESSION, 3600)
        
        # Grant access to *.google.com
        request = CapabilityRequest(
            agent_id=agent_id,
            capability=CapabilityType.NETWORK_CONNECT,
            scope={"host": "*.google.com", "port": 443},
            purpose="Google services"
        )
        await self.cp.request_capability(request)
        
        # Validate mail.google.com
        self.assertTrue(self.cp.validate_grant(agent_id, CapabilityType.NETWORK_CONNECT, {"host": "mail.google.com", "port": 443}))
        
        # Validate google.com
        self.assertTrue(self.cp.validate_grant(agent_id, CapabilityType.NETWORK_CONNECT, {"host": "google.com", "port": 443}))
        
        # Block bing.com
        self.assertFalse(self.cp.validate_grant(agent_id, CapabilityType.NETWORK_CONNECT, {"host": "bing.com", "port": 443}))

if __name__ == "__main__":
    unittest.main()
