import unittest
from unittest.mock import AsyncMock
import os
import sys
import uuid
from datetime import datetime

# Ensure project root is in path
sys.path.append(os.getcwd())

from core.models.models import CapabilityRequest, CapabilityType, GrantType
from core.control_plane.manager import ControlPlaneManager
from adapters.platform_adapter import get_platform_adapter

class TestSecurityEdgeCases(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_id = uuid.uuid4().hex[:8]
        self.db_path = f"test_sec_{self.test_id}.db"
        self.log_path = f"test_sec_{self.test_id}.log"
        self.config = {
            "default_deny": True,
            "db_path": self.db_path,
            "log_path": self.log_path
        }
        self.ui_mock = AsyncMock()
        self.cp = ControlPlaneManager(self.config, ui_handler=self.ui_mock)
        self.adapter = get_platform_adapter(self.cp)
        self.fs = self.adapter["fs"]
        self.net = self.adapter["net"]

    async def asyncTearDown(self):
        self.cp.shutdown()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.log_path):
            os.remove(self.log_path)

    async def test_identity_spoofing_prevention(self):
        """Verify Agent B cannot use Agent A's grant."""
        agent_a = "agent-A"
        agent_b = "agent-B"
        test_file = os.path.abspath("spoof_test.txt")
        with open(test_file, "w") as f: f.write("secret")

        # Grant to Agent A
        self.ui_mock.ask_approval.return_value = (True, GrantType.SESSION, 3600)
        req = CapabilityRequest(
            agent_id=agent_a,
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": test_file},
            purpose="A's grant"
        )
        await self.cp.request_capability(req)

        # Agent A can read
        self.assertEqual(self.fs.read_file(agent_a, test_file), "secret")

        # Agent B should be blocked
        with self.assertRaises(PermissionError):
            self.fs.read_file(agent_b, test_file)

        os.remove(test_file)

    async def test_symlink_bypass_prevention(self):
        """Verify that symlinks are resolved and checked against the real path."""
        real_file = os.path.abspath("real_data.txt")
        link_file = os.path.abspath("link_to_data.txt")
        with open(real_file, "w") as f: f.write("real content")
        if os.path.exists(link_file): os.remove(link_file)
        os.symlink(real_file, link_file)

        agent_id = "agent-symlink"
        
        # Grant access ONLY to the link path string (if it were naive)
        # But we want to see if it correctly blocks access if we don't have a grant for the REAL path
        self.ui_mock.ask_approval.return_value = (True, GrantType.ALLOW_ONCE, 0)
        
        # Case 1: Grant for the link path
        req = CapabilityRequest(
            agent_id=agent_id,
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": link_file}, # Requesting the link
            purpose="Link access"
        )
        await self.cp.request_capability(req)
        
        # Should succeed because the enforcement layer normalizes link_file to real_file
        # and the manager matches it.
        # Wait, the enforcement layer normalizes the path BEFORE checking with the manager.
        # So the manager receives the REAL path.
        content = self.fs.read_file(agent_id, link_file)
        self.assertEqual(content, "real content")

        # Cleanup
        os.remove(link_file)
        os.remove(real_file)

    async def test_network_scope_boundary(self):
        """Verify strict host and port matching."""
        agent_id = "agent-net-boundary"
        self.ui_mock.ask_approval.return_value = (True, GrantType.SESSION, 3600)
        
        # Grant for host A port 80
        req = CapabilityRequest(
            agent_id=agent_id,
            capability=CapabilityType.NETWORK_CONNECT,
            scope={"host": "example.com", "port": 80},
            purpose="Port 80 only"
        )
        await self.cp.request_capability(req)

        # Correct connection
        self.assertTrue(self.net.connect(agent_id, "example.com", 80))

        # Wrong port
        self.assertFalse(self.net.connect(agent_id, "example.com", 443))

        # Wrong host
        self.assertFalse(self.net.connect(agent_id, "google.com", 80))

    async def test_fail_closed_no_ui(self):
        """Verify denial if no UI handler is present."""
        cp_no_ui = ControlPlaneManager(self.config, ui_handler=None)
        req = CapabilityRequest(
            agent_id="agent-no-ui",
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": "/tmp/test"},
            purpose="No UI test"
        )
        
        grant = await cp_no_ui.request_capability(req)
        self.assertIsNone(grant)

    async def test_network_host_normalization(self):
        """Verify that CASE and whitespace in hosts don't cause bypasses or false denials."""
        agent_id = "agent-net-norm"
        self.ui_mock.ask_approval.return_value = (True, GrantType.SESSION, 3600)
        
        req = CapabilityRequest(
            agent_id=agent_id,
            capability=CapabilityType.NETWORK_CONNECT,
            scope={"host": "API.Example.COM", "port": 443},
            purpose="Normalization test"
        )
        await self.cp.request_capability(req)

        # Should match despite different casing
        self.assertTrue(self.net.connect(agent_id, "api.example.com", 443))
        # Should match despite trailing spaces
        self.assertTrue(self.net.connect(agent_id, " api.example.com  ", 443))

    async def test_symlink_target_change_vulnerability(self):
        """Verify that changing a symlink target doesn't grant access to the new target if not approved."""
        secret_a = os.path.abspath("secret_a.txt")
        secret_b = os.path.abspath("secret_b.txt")
        link_file = os.path.abspath("active_link.txt")

        with open(secret_a, "w") as f: f.write("AAA")
        with open(secret_b, "w") as f: f.write("BBB")
        if os.path.exists(link_file): os.remove(link_file)
        os.symlink(secret_a, link_file)

        agent_id = "agent-link-vun"
        self.ui_mock.ask_approval.return_value = (True, GrantType.SESSION, 3600)

        # Grant access to secret_a via the link
        req = CapabilityRequest(
            agent_id=agent_id,
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": link_file},
            purpose="Link access"
        )
        await self.cp.request_capability(req)

        # Should work for secret_a
        self.assertEqual(self.fs.read_file(agent_id, link_file), "AAA")

        # Now, malicious user/agent changes the link to point to secret_b
        os.remove(link_file)
        os.symlink(secret_b, link_file)

        # Access should now be BLOCKED because the grant is for secret_a (the realpath), 
        # but the new realpath is secret_b.
        with self.assertRaises(PermissionError):
            self.fs.read_file(agent_id, link_file)

        # Cleanup
        for f in [secret_a, secret_b, link_file]:
            if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    unittest.main()
