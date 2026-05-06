from core.models.models import CapabilityRequest

class PolicyEngine:
    def __init__(self, config: dict):
        self.config = config

    def evaluate(self, request: CapabilityRequest) -> str:
        """
        Evaluate a request against static policies.
        Returns: "approve", "deny", or "manual_review"
        """
        # Phase 1: Default to manual review for all requests
        return "manual_review"
