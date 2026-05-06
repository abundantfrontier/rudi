import unittest
from core.control_plane.manager import ControlPlaneManager
from core.models.models import CapabilityRequest, CapabilityType

class TestAgentIdentity(unittest.TestCase):
    def setUp(self):
        self.config = {"approval_timeout": 60}
        self.cp = ControlPlaneManager(self.config)

    def test_unregistered_agent_passes(self):
        # By default, if no agents are registered, it passes for backward compatibility
        req = CapabilityRequest(
            agent_id="agent-001",
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": "/tmp/test.txt"},
            purpose="Testing"
        )
        # Should not be blocked by identity verification
        # It might be blocked by policy, but we check if it gets past _verify_agent
        # PolicyEngine might return 'manual_review' or 'deny'
        self.cp.register_agent("other-agent", "secret-token")
        
        # Now agent-001 is NOT registered, and there ARE registered agents
        grant = self.cp.request_capability(req)
        self.assertIsNone(grant)
        self.assertEqual(self.cp.metrics["total_denials"], 1)

    def test_registered_agent_correct_token(self):
        self.cp.register_agent("agent-001", "secret-token")
        req = CapabilityRequest(
            agent_id="agent-001",
            agent_token="secret-token",
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": "/tmp/test.txt"},
            purpose="Testing"
        )
        # Should pass identity verification
        # We don't have a UI handler, so it might fail at manual_review, 
        # but let's see if it gets past identity.
        grant = self.cp.request_capability(req)
        # It should fail at manual_review (no ui handler) or policy denial
        # but the denial reason in audit log would be different.
        
    def test_registered_agent_wrong_token(self):
        self.cp.register_agent("agent-001", "secret-token")
        req = CapabilityRequest(
            agent_id="agent-001",
            agent_token="wrong-token",
            capability=CapabilityType.FILESYSTEM_READ,
            scope={"path": "/tmp/test.txt"},
            purpose="Testing"
        )
        grant = self.cp.request_capability(req)
        self.assertIsNone(grant)
        self.assertEqual(self.cp.metrics["total_denials"], 1)

if __name__ == "__main__":
    unittest.main()
