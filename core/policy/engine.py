import fnmatch
from core.models.models import CapabilityRequest

class PolicyEngine:
    def __init__(self, config: dict):
        self.config = config

    def evaluate(self, request: CapabilityRequest) -> str:
        """
        Evaluate a request against static policies and auto-approval rules.
        Returns: "approve", "deny", or "manual_review"
        """
        # 1. Check Auto-Approval Rules
        rules = self.config.get("auto_approve_rules", [])
        for rule in rules:
            if self._rule_matches(rule, request):
                return "approve"

        # 2. Default behavior: Manual Review
        return "manual_review"

    def _rule_matches(self, rule: dict, request: CapabilityRequest) -> bool:
        # Match Capability
        if rule.get("capability") != request.capability:
            return False
        
        # Match Scope Patterns
        scope_pattern = rule.get("scope_pattern", {})
        for key, pattern in scope_pattern.items():
            val = request.scope.get(key)
            if not val:
                return False
            
            # Simple wildcard matching for strings (like paths)
            if isinstance(val, str) and isinstance(pattern, str):
                if not fnmatch.fnmatch(val, pattern):
                    return False
            elif val != pattern:
                return False
                
        return True
