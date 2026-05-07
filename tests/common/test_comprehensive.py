import unittest
from unittest.mock import AsyncMock, MagicMock
import os
import sys
import time
import uuid
from datetime import datetime, timedelta
import shutil

# Ensure project root is in path
sys.path.append(os.getcwd())

from core.models.models import CapabilityRequest, CapabilityType, GrantType
from core.control_plane.manager import ControlPlaneManager
from core.audit.store import AuditStore
from core.audit.logger import AuditLogger
from adapters.platform_adapter import get_platform_adapter

class TestComprehensiveEdgeCases(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_db = f"test_comprehensive_{uuid.uuid4().hex[:6]}.db"
        self.test_log = f"test_audit_{uuid.uuid4().hex[:6]}.log"
        if os.path.exists(self.test_db): os.remove(self.test_db)
        if os.path.exists(self.test_log): os.remove(self.test_log)
        
        self.config = {
            "default_deny": True,
            "approval_timeout": 5,
            "db_path": self.test_db,
            "log_path": self.test_log
        }
        self.ui_mock = AsyncMock()
        self.cp = ControlPlaneManager(self.config, ui_handler=self.ui_mock)
        self.adapter = get_platform_adapter(self.cp)
        self.fs = self.adapter["fs"]
        self.net = self.adapter["net"]
        self.store = AuditStore(log_path=self.test_log)

    async def asyncTearDown(self):
        self.cp.shutdown()
        if os.path.exists(self.test_db): os.remove(self.test_db)
        if os.path.exists(self.test_log): os.remove(self.test_log)

    async def test_directory_vs_file_scoping(self):
        """Verify that a grant for a directory allows reading files within it."""
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
        await self.cp.request_capability(req)

        # Attempt to read the FILE inside the directory
        try:
            self.fs.read_file(agent_id, test_file)
            access_allowed = True
        except PermissionError:
            access_allowed = False
        
        self.assertTrue(access_allowed)
        shutil.rmtree(test_dir)

    async def test_concurrent_overlapping_grants(self):
        """Verify that most permissive grant wins when multiple exist."""
        agent_id = "agent-overlap"
        test_file = os.path.abspath("overlap.txt")
        with open(test_file, "w") as f: f.write("data")

        self.ui_mock.ask_approval.side_effect = [
            (True, GrantType.ALLOW_ONCE, 0),
            (True, GrantType.SESSION, 3600)
        ]

        req1 = CapabilityRequest(agent_id=agent_id, capability=CapabilityType.FILESYSTEM_READ, scope={"path": test_file}, purpose="p1")
        req2 = CapabilityRequest(agent_id=agent_id, capability=CapabilityType.FILESYSTEM_READ, scope={"path": test_file}, purpose="p2")
        
        await self.cp.request_capability(req1)
        await self.cp.request_capability(req2)

        self.assertEqual(self.fs.read_file(agent_id, test_file), "data")
        self.assertEqual(self.fs.read_file(agent_id, test_file), "data")
        
        os.remove(test_file)

    async def test_rapid_request_flooding(self):
        """Verify system handles high volume of requests/grants/audits."""
        agent_id = "agent-flood"
        self.ui_mock.ask_approval.return_value = (True, GrantType.ALLOW_ONCE, 0)
        
        for i in range(100):
            req = CapabilityRequest(
                agent_id=agent_id,
                capability=CapabilityType.FILESYSTEM_READ,
                scope={"path": f"/tmp/flood_{i}"},
                purpose="Flooding test"
            )
            await self.cp.request_capability(req)
        
        metrics = self.store.get_metrics()
        self.assertGreaterEqual(metrics["total_events"], 200)

    async def test_non_existent_path_normalization(self):
        """Verify normalization works even if file doesn't exist yet."""
        path = "none/exists/../../file.txt"
        normalized = self.fs.validate_path(path)
        self.assertTrue(normalized.endswith("file.txt"))
        self.assertTrue(os.path.isabs(normalized))

if __name__ == "__main__":
    unittest.main()
