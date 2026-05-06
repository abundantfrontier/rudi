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
from core.audit.store import AuditStore

class TestPhase3Core(unittest.TestCase):
    def setUp(self):
        # Truncate audit log before tests
        if os.path.exists("audit.log"):
            with open("audit.log", "w") as f:
                f.truncate()
            
        self.config = {
            "default_deny": True,
            "approval_timeout": 1 # Short timeout for tests
        }
        self.ui_mock = MagicMock()
        self.cp = ControlPlaneManager(self.config, ui_handler=self.ui_mock)
        self.store = AuditStore()

    def test_background_flag_logging(self):
        agent_id = "agent-p3-001"
        self.ui_mock.ask_approval.return_value = (True, GrantType.ALLOW_ONCE, 0)
        
        req = CapabilityRequest(
            agent_id=agent_id,
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": "/tmp/bg_test"},
            purpose="Background test",
            background=True
        )
        self.cp.request_capability(req)
        
        # Query audit store
        events = self.store.query(agent_id=agent_id, event_type="grant")
        self.assertTrue(len(events) > 0)
        self.assertTrue(events[0]["details"]["background"])

    def test_stale_grant_detection(self):
        agent_id = "agent-p3-002"
        self.ui_mock.ask_approval.return_value = (True, GrantType.SESSION, 3600)
        
        req = CapabilityRequest(
            agent_id=agent_id,
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": "/tmp/stale"},
            purpose="Stale test"
        )
        self.cp.request_capability(req)
        
        # Initially not stale (idle_seconds = 300 default)
        self.assertEqual(len(self.cp.get_stale_grants(idle_seconds=10)), 0)
        
        # Wait for "staleness"
        time.sleep(2)
        
        # Check with short idle threshold
        stale = self.cp.get_stale_grants(idle_seconds=1)
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0].agent_id, agent_id)

    def test_audit_metrics(self):
        agent_id = "agent-p3-003"
        self.ui_mock.ask_approval.return_value = (True, GrantType.ALLOW_ONCE, 0)
        
        # 1 grant
        self.cp.request_capability(CapabilityRequest(
            agent_id=agent_id, capability=CapabilityType.FILESYSTEM_READ, 
            scope={"path": "/tmp/a"}, purpose="p"
        ))
        
        # 1 denial
        self.ui_mock.ask_approval.return_value = False
        self.cp.request_capability(CapabilityRequest(
            agent_id=agent_id, capability=CapabilityType.FILESYSTEM_READ, 
            scope={"path": "/tmp/b"}, purpose="p"
        ))
        
        metrics = self.store.get_metrics()
        self.assertEqual(metrics["grants"], 1)
        self.assertEqual(metrics["denials"], 1)

if __name__ == "__main__":
    unittest.main()
