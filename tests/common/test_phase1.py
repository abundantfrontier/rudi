import unittest
from unittest.mock import MagicMock
import os
import sys

# Ensure project root is in path
sys.path.append(os.getcwd())

from core.models.models import CapabilityRequest, CapabilityType, GrantType
from core.control_plane.manager import ControlPlaneManager
from adapters.platform_adapter import get_platform_adapter

class TestPhase1Core(unittest.TestCase):
    def setUp(self):
        self.config = {
            "default_deny": True,
            "approval_timeout": 60
        }
        self.ui_mock = MagicMock()
        self.cp = ControlPlaneManager(self.config, ui_handler=self.ui_mock)
        self.adapter = get_platform_adapter(self.cp)
        self.fs = self.adapter["fs"]

    def test_end_to_end_loop_success(self):
        # 1. Setup a test file
        test_file = os.path.abspath("test_secret.txt")
        with open(test_file, "w") as f:
            f.write("top secret data")
        
        agent_id = "test-agent-001"
        request = CapabilityRequest(
            agent_id=agent_id,
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": test_file},
            purpose="Testing the loop"
        )

        # 2. Mock user approval
        self.ui_mock.ask_approval.return_value = True

        # 3. Request capability
        grant = self.cp.request_capability(request)
        self.assertIsNotNone(grant)
        self.assertEqual(grant.agent_id, agent_id)

        # 4. Use capability through enforcement layer
        data = self.fs.read_file(agent_id, test_file)
        self.assertEqual(data, "top secret data")

        # 5. Verify "Allow Once" consumption (next attempt should fail)
        with self.assertRaises(PermissionError):
            self.fs.read_file(agent_id, test_file)

        # Cleanup
        os.remove(test_file)

    def test_enforcement_block_on_denial(self):
        test_file = os.path.abspath("test_secret_2.txt")
        with open(test_file, "w") as f:
            f.write("data")
            
        agent_id = "test-agent-002"
        request = CapabilityRequest(
            agent_id=agent_id,
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": test_file},
            purpose="Testing denial"
        )

        # Mock user denial
        self.ui_mock.ask_approval.return_value = False

        # Request capability (should return None)
        grant = self.cp.request_capability(request)
        self.assertIsNone(grant)

        # Try to read (should fail)
        with self.assertRaises(PermissionError):
            self.fs.read_file(agent_id, test_file)

        os.remove(test_file)

    def test_path_normalization_enforcement(self):
        # Verify that relative paths are normalized and still matched
        test_file = "test_norm.txt"
        abs_path = os.path.abspath(test_file)
        with open(abs_path, "w") as f:
            f.write("normalized data")

        agent_id = "test-agent-003"
        # Request with absolute path
        request = CapabilityRequest(
            agent_id=agent_id,
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": abs_path},
            purpose="Testing normalization"
        )
        self.ui_mock.ask_approval.return_value = True
        self.cp.request_capability(request)

        # Try to read with relative path (should be normalized and allowed)
        data = self.fs.read_file(agent_id, test_file)
        self.assertEqual(data, "normalized data")

        os.remove(abs_path)

if __name__ == "__main__":
    unittest.main()
