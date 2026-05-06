import unittest
from unittest.mock import MagicMock
import os
import sys
import time
from datetime import datetime, timedelta
import shutil

# Ensure project root is in path
sys.path.append(os.getcwd())

from core.models.models import CapabilityRequest, CapabilityType, GrantType
from core.control_plane.manager import ControlPlaneManager
from core.audit.store import AuditStore
from adapters.platform_adapter import get_platform_adapter

class TestComprehensiveEdgeCases(unittest.TestCase):
    def setUp(self):
        self.config = {
            "default_deny": True,
            "approval_timeout": 5
        }
        self.ui_mock = MagicMock()
        self.cp = ControlPlaneManager(self.config, ui_handler=self.ui_mock)
        self.adapter = get_platform_adapter(self.cp)
        self.fs = self.adapter["fs"]
        self.net = self.adapter["net"]
        self.store = AuditStore()

    def test_directory_vs_file_scoping(self):
        """Verify that a grant for a directory allows reading files within it."""
        # Note: Currently, R.U.D.I. Phase 2 uses exact equality for scope.
        # This test checks if we need to implement hierarchical scoping.
        test_dir = os.path.abspath("test_scope_dir")
        os.makedirs(test_dir, exist_ok=True)
        test_file = os.path.join(test_dir, "inside.txt")
        with open(test_file, "w") as f: f.write("inside data")

        agent_id = "agent-scope"
        self.ui_mock.ask_approval.return_value = (True, GrantType.SESSION, 3600)

        # Grant for the DIRECTORY
        req = CapabilityRequest(
            agent_id=agent_id,
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": test_dir},
            purpose="Directory-level access"
        )
        self.cp.request_capability(req)

        # Attempt to read the FILE inside the directory
        # This is expected to FAIL with current exact-match logic, 
        # which identifies a gap for Phase 3/4.
        try:
            self.fs.read_file(agent_id, test_file)
            access_allowed = True
        except PermissionError:
            access_allowed = False
        
        # We document this result. If it's False, it's a gap.
        print(f"\n[Review] Hierarchical FS Scoping implemented: {access_allowed}")
        
        shutil.rmtree(test_dir)

    def test_concurrent_overlapping_grants(self):
        """Verify that most permissive grant wins when multiple exist."""
        agent_id = "agent-overlap"
        test_file = os.path.abspath("overlap.txt")
        with open(test_file, "w") as f: f.write("data")

        # Grant 1: Allow Once (consumed after use)
        # Grant 2: Session (persistent)
        self.ui_mock.ask_approval.side_effect = [
            (True, GrantType.ALLOW_ONCE, 0),
            (True, GrantType.SESSION, 3600)
        ]

        req1 = CapabilityRequest(agent_id=agent_id, capability=CapabilityType.FILESYSTEM_READ, scope={"path": test_file}, purpose="p1")
        req2 = CapabilityRequest(agent_id=agent_id, capability=CapabilityType.FILESYSTEM_READ, scope={"path": test_file}, purpose="p2")
        
        self.cp.request_capability(req1)
        self.cp.request_capability(req2)

        # Use 1: Should succeed
        self.assertEqual(self.fs.read_file(agent_id, test_file), "data")
        
        # Use 2: Should STILL succeed because of the Session grant
        self.assertEqual(self.fs.read_file(agent_id, test_file), "data")
        
        os.remove(test_file)

    def test_rapid_request_flooding(self):
        """Verify system handles high volume of requests/grants/audits."""
        agent_id = "agent-flood"
        self.ui_mock.ask_approval.return_value = (True, GrantType.ALLOW_ONCE, 0)
        
        # Issue 100 requests
        for i in range(100):
            req = CapabilityRequest(
                agent_id=agent_id,
                capability=CapabilityType.FILESYSTEM_READ,
                scope={"path": f"/tmp/flood_{i}"},
                purpose="Flooding test"
            )
            self.cp.request_capability(req)
        
        metrics = self.store.get_metrics()
        # total_events should be at least 200 (100 requests + 100 grants)
        self.assertGreaterEqual(metrics["total_events"], 200)

    def test_non_existent_path_normalization(self):
        """Verify normalization works even if file doesn't exist yet."""
        # os.path.realpath handles non-existent paths by normalizing the components it can.
        path = "none/exists/../../file.txt"
        normalized = self.fs.validate_path(path)
        self.assertTrue(normalized.endswith("file.txt"))
        self.assertTrue(os.path.isabs(normalized))

if __name__ == "__main__":
    unittest.main()
