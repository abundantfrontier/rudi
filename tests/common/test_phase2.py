import unittest
from unittest.mock import MagicMock
import os
import sys
import time
from datetime import datetime, timedelta

# Ensure project root is in path
sys.path.append(os.getcwd())

from core.models.models import CapabilityRequest, CapabilityType, GrantType
from core.control_plane.manager import ControlPlaneManager
from adapters.platform_adapter import get_platform_adapter

class TestPhase2Core(unittest.TestCase):
    def setUp(self):
        self.config = {"default_deny": True}
        self.ui_mock = MagicMock()
        self.cp = ControlPlaneManager(self.config, ui_handler=self.ui_mock)
        self.adapter = get_platform_adapter(self.cp)
        self.fs = self.adapter["fs"]
        self.net = self.adapter["net"]

    def test_time_boxed_expiration(self):
        agent_id = "agent-p2-001"
        test_file = os.path.abspath("test_p2_expiry.txt")
        with open(test_file, "w") as f: f.write("data")

        # 1. Request a 2-second time-boxed grant
        # result = (approved, grant_type, duration_seconds)
        self.ui_mock.ask_approval.return_value = (True, GrantType.TIME_BOXED, 2)
        
        request = CapabilityRequest(
            agent_id=agent_id,
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": test_file},
            purpose="Testing time-box"
        )
        self.cp.request_capability(request)

        # 2. Use it immediately (should work)
        self.assertEqual(self.fs.read_file(agent_id, test_file), "data")

        # 3. Wait for expiration
        time.sleep(2.5)

        # 4. Use it again (should fail)
        with self.assertRaises(PermissionError):
            self.fs.read_file(agent_id, test_file)

        os.remove(test_file)

    def test_session_grant(self):
        agent_id = "agent-p2-002"
        host = "example.com"
        port = 443

        # 1. Request a session grant (default 1h)
        self.ui_mock.ask_approval.return_value = (True, GrantType.SESSION, 3600)
        
        request = CapabilityRequest(
            agent_id=agent_id,
            capability=CapabilityType.NETWORK_CONNECT,
            scope={"host": host, "port": port},
            purpose="Testing session"
        )
        self.cp.request_capability(request)

        # 2. Use it multiple times (should work)
        self.assertTrue(self.net.connect(agent_id, host, port))
        self.assertTrue(self.net.connect(agent_id, host, port))
        self.assertTrue(self.net.connect(agent_id, host, port))

    def test_revocation(self):
        agent_id = "agent-p2-003"
        host = "malicious.com"
        
        self.ui_mock.ask_approval.return_value = (True, GrantType.SESSION, 3600)
        request = CapabilityRequest(
            agent_id=agent_id,
            capability=CapabilityType.NETWORK_CONNECT,
            scope={"host": host, "port": 80},
            purpose="Testing revocation"
        )
        grant = self.cp.request_capability(request)
        self.assertTrue(self.net.connect(agent_id, host, 80))

        # Revoke
        self.cp.revoke_grant(grant.id)

        # Should fail now
        self.assertFalse(self.net.connect(agent_id, host, 80))

    def test_active_grants_listing(self):
        agent_id = "agent-p2-004"
        self.ui_mock.ask_approval.return_value = (True, GrantType.ALLOW_ONCE, 0)
        
        req1 = CapabilityRequest(
            agent_id=agent_id,
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": "/tmp/1"},
            purpose="p1"
        )
        req2 = CapabilityRequest(
            agent_id=agent_id,
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": "/tmp/2"},
            purpose="p2"
        )
        
        self.cp.request_capability(req1)
        self.cp.request_capability(req2)
        
        active = self.cp.get_active_grants(agent_id)
        self.assertEqual(len(active), 2)

    def test_hierarchical_scoping(self):
        agent_id = "agent-h"
        parent_dir = os.path.abspath("test_parent")
        child_file = os.path.abspath("test_parent/subdir/file.txt")
        
        self.ui_mock.ask_approval.return_value = (True, GrantType.SESSION, 3600)
        request = CapabilityRequest(
            agent_id=agent_id,
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": parent_dir},
            purpose="Testing hierarchy"
        )
        self.cp.request_capability(request)
        
        self.assertTrue(self.cp.validate_grant(agent_id, CapabilityType.FILESYSTEM_READ, {"path": child_file}))
        self.assertTrue(self.cp.validate_grant(agent_id, CapabilityType.FILESYSTEM_READ, {"path": parent_dir}))
        self.assertFalse(self.cp.validate_grant(agent_id, CapabilityType.FILESYSTEM_READ, {"path": os.path.abspath("other")}))

    def test_thread_safety_stress(self):
        import threading
        agent_id = "agent-stress"
        num_threads = 5
        iterations = 20
        self.ui_mock.ask_approval.return_value = (True, GrantType.SESSION, 3600)
        
        def worker(thread_id):
            for i in range(iterations):
                path = os.path.abspath(f"file_{thread_id}_{i}")
                req = CapabilityRequest(
                    agent_id=agent_id,
                    capability=CapabilityType.FILESYSTEM_READ,
                    scope={"path": path},
                    purpose="stress"
                )
                self.cp.request_capability(req)
                self.assertTrue(self.cp.validate_grant(agent_id, CapabilityType.FILESYSTEM_READ, {"path": path}))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        active = self.cp.get_active_grants(agent_id)
        self.assertEqual(len(active), num_threads * iterations)

if __name__ == "__main__":
    unittest.main()
