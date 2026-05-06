import uuid
import os
import threading
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from core.models.models import CapabilityRequest, CapabilityGrant, GrantType, AuditEvent, CapabilityType
from core.control_plane.interface import ControlPlaneInterface
from core.policy.engine import PolicyEngine
from core.audit.logger import AuditLogger
from core.audit.store import AuditStore
from core.storage.sqlite_store import SQLiteStore

class ControlPlaneManager(ControlPlaneInterface):
    """
    The central mediation layer for capability requests and enforcement.
    Handles the lifecycle of capability grants, including evaluation, 
    validation, and revocation.
    """
    def __init__(self, config: dict, ui_handler: Any = None, storage: Optional[SQLiteStore] = None):
        self.config = config
        self.lock = threading.Lock()
        self.policy_engine = PolicyEngine(config)
        self.audit_logger = AuditLogger()
        self.audit_store = AuditStore()
        self.ui_handler = ui_handler
        self.strict_identity = config.get("strict_identity", False)
        
        # Persistence
        self.storage = storage or SQLiteStore(config.get("db_path", "rudi.db"))
        self.grants: Dict[str, CapabilityGrant] = {g.id: g for g in self.storage.load_all_grants()}
        self.registered_agents: Dict[str, str] = self.storage.get_all_agents() # agent_id -> token_hash
        
        self.metrics = {
            "total_requests": 0,
            "total_grants": 0,
            "total_denials": 0,
            "total_uses": 0,
            "total_blocked": 0,
            "identity_failures": 0
        }

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256((token or "").encode()).hexdigest()

    def register_agent(self, agent_id: str, token: str):
        token_hash = self._hash_token(token)
        with self.lock:
            self.registered_agents[agent_id] = token_hash
            self.storage.save_agent(agent_id, token_hash)

    def _verify_agent(self, agent_id: str, token: Optional[str]) -> bool:
        """
        Verify agent identity. In 'strict_identity' mode, agents must be
        registered and the token must match.
        """
        registered_hash = self.registered_agents.get(agent_id)
        
        if self.strict_identity:
            if not registered_hash:
                return False
            return registered_hash == self._hash_token(token)
        
        # Backward compatibility mode
        if not self.registered_agents:
            return True
        if not registered_hash:
            return True # Allow unregistered if others are registered but not this one
        return registered_hash == self._hash_token(token)

    def get_metrics(self) -> Dict[str, Any]:
        """Expose current system metrics for observability."""
        with self.lock:
            return {
                **self.metrics,
                "active_grants_count": len(self.grants),
                "registered_agents_count": len(self.registered_agents)
            }

    def get_status(self) -> Dict[str, Any]:
        """Returns a high-level health and status report."""
        return {
            "status": "healthy",
            "strict_identity": self.strict_identity,
            "active_grants": len(self.get_active_grants())
        }

    def request_capability(self, request: CapabilityRequest) -> Optional[CapabilityGrant]:
        """
        Evaluate and potentially grant a requested capability.
        """
        self.metrics["total_requests"] += 1
        
        # Verify Agent Identity
        if not self._verify_agent(request.agent_id, request.agent_token):
            self.metrics["identity_failures"] += 1
            self._log_event(request, "denial", "invalid_agent_token")
            return None

        decision = self.policy_engine.evaluate(request)
        
        if decision == "deny":
            self._log_event(request, "denial", "policy_denied")
            return None
        
        grant_type = GrantType.ALLOW_ONCE
        duration = 0
        
        if decision == "manual_review":
            if not self.ui_handler:
                self._log_event(request, "denial", "no_ui_handler")
                return None
            
            # UI returns (approved: bool, type: GrantType, duration_seconds: int)
            timeout = self.config.get("approval_timeout", 60)
            result = self.ui_handler.ask_approval(request, timeout=timeout)
            
            if isinstance(result, bool):
                if not result:
                    self._log_event(request, "denial", "user_denied")
                    return None
            else:
                approved, grant_type, duration = result
                if not approved:
                    self._log_event(request, "denial", "user_denied")
                    return None

        # Normalize scope before granting
        normalized_scope = request.scope.copy()
        if request.capability in [CapabilityType.FILESYSTEM_READ, CapabilityType.FILESYSTEM_WRITE]:
            if "path" in normalized_scope:
                normalized_scope["path"] = os.path.realpath(os.path.expanduser(normalized_scope["path"]))
        elif request.capability == CapabilityType.NETWORK_CONNECT:
            if "host" in normalized_scope:
                normalized_scope["host"] = normalized_scope["host"].strip().lower()

        # Create the grant
        grant_id = str(uuid.uuid4())
        expires_at = None
        if duration > 0:
            expires_at = datetime.now() + timedelta(seconds=duration)
        
        if grant_type == GrantType.SESSION and not expires_at:
            expires_at = datetime.now() + timedelta(hours=1)
        elif grant_type == GrantType.PERMANENT:
            expires_at = None # No expiry

        # Basic risk assessment
        risk_level = "low"
        if request.capability in [CapabilityType.NETWORK_CONNECT, CapabilityType.PROCESS_EXECUTE]:
            risk_level = "medium"
        if request.capability == CapabilityType.MODEL_ESCALATE or grant_type == GrantType.PERMANENT:
            risk_level = "high"

        grant = CapabilityGrant(
            id=grant_id,
            agent_id=request.agent_id,
            capability=request.capability,
            scope=normalized_scope,
            grant_type=grant_type,
            risk_level=risk_level,
            expires_at=expires_at
        )
        
        with self.lock:
            self.grants[grant_id] = grant
            self.storage.save_grant(grant)
            
        self._log_event(request, "grant", "granted", {
            "grant_id": grant_id, 
            "type": grant_type,
            "background": request.background,
            "expires_at": str(expires_at) if expires_at else None
        })
        return grant

    def validate_grant(self, agent_id: str, capability_type: str, scope: Dict[str, Any]) -> bool:
        """
        Check if an agent currently holds a valid grant for a specific action.
        """
        now = datetime.now()
        with self.lock:
            for grant_id, grant in list(self.grants.items()):
                # Expiry check
                if grant.expires_at and now > grant.expires_at:
                    self.audit_logger.log_event(AuditEvent(
                        agent_id=agent_id, event_type="expiration",
                        action=capability_type, resource=str(scope),
                        status="expired", details={"grant_id": grant_id}
                    ))
                    del self.grants[grant_id]
                    self.storage.delete_grant(grant_id)
                    continue

                # Identity and Capability match
                if grant.agent_id == agent_id and grant.capability == capability_type:
                    # Scope match
                    if self._scope_matches(grant.scope, scope):
                        
                        # Stateful consumption for Token Budgets
                        if capability_type == CapabilityType.MODEL_ESCALATE and "tokens" in scope:
                            if "token_budget" in grant.scope:
                                grant.scope["token_budget"] -= scope["tokens"]

                        # Consume "Allow Once" grant
                        if grant.grant_type == GrantType.ALLOW_ONCE:
                            del self.grants[grant_id]
                            self.storage.delete_grant(grant_id)
                        else:
                            grant.last_used_at = now
                            self.storage.save_grant(grant)
                        
                        self.metrics["total_uses"] += 1
                        self.audit_logger.log_event(AuditEvent(
                            agent_id=agent_id, event_type="use",
                            action=capability_type, resource=str(scope),
                            status="success"
                        ))
                        return True
        
        self.metrics["total_blocked"] += 1
        self.audit_logger.log_event(AuditEvent(
            agent_id=agent_id, event_type="use",
            action=capability_type, resource=str(scope),
            status="blocked"
        ))
        return False

    def _scope_matches(self, grant_scope: Dict[str, Any], requested_scope: Dict[str, Any]) -> bool:
        """
        Check if requested_scope is within grant_scope.
        """
        if grant_scope == requested_scope:
            return True

        # 1. Path hierarchy
        if "path" in grant_scope and "path" in requested_scope:
            try:
                # Use realpath to resolve symlinks consistently (esp. on macOS /tmp)
                g_path = os.path.realpath(os.path.expanduser(grant_scope["path"]))
                r_path = os.path.realpath(os.path.expanduser(requested_scope["path"]))
                if os.path.commonpath([g_path, r_path]) == g_path:
                    return True
            except (ValueError, OSError):
                pass

        # 2. Host wildcards
        if "host" in grant_scope and "host" in requested_scope:
            g_host = grant_scope["host"].lower()
            r_host = requested_scope["host"].lower()
            if g_host.startswith("*."):
                suffix = g_host[1:]
                if r_host.endswith(suffix) or r_host == g_host[2:]:
                    return True

        # 3. Token Budgets
        if "token_budget" in grant_scope and "tokens" in requested_scope:
            if requested_scope["tokens"] <= grant_scope["token_budget"]:
                return True

        # 4. Command prefix (for process:execute)
        if "command_prefix" in grant_scope and "command" in requested_scope:
            if requested_scope["command"].startswith(grant_scope["command_prefix"]):
                return True

        return False

    def get_stale_grants(self, idle_seconds: int = 300) -> List[CapabilityGrant]:
        now = datetime.now()
        stale = []
        with self.lock:
            for grant in self.grants.values():
                if grant.grant_type == GrantType.ALLOW_ONCE:
                    continue
                last_activity = grant.last_used_at or grant.granted_at
                if (now - last_activity).total_seconds() > idle_seconds:
                    stale.append(grant)
        return stale

    def get_active_grants(self, agent_id: Optional[str] = None) -> List[CapabilityGrant]:
        now = datetime.now()
        active = []
        with self.lock:
            for grant in self.grants.values():
                if grant.expires_at and now > grant.expires_at:
                    continue
                if agent_id and grant.agent_id != agent_id:
                    continue
                active.append(grant)
        return active

    def revoke_grant(self, grant_id: str) -> bool:
        with self.lock:
            if grant_id in self.grants:
                grant = self.grants[grant_id]
                self.audit_logger.log_event(AuditEvent(
                    agent_id=grant.agent_id, event_type="revocation",
                    action=grant.capability, resource=str(grant.scope),
                    status="success", details={"grant_id": grant_id}
                ))
                del self.grants[grant_id]
                self.storage.delete_grant(grant_id)
                return True
        return False

    def _log_event(self, request: CapabilityRequest, event_type: str, status: str, details: Optional[Dict[str, Any]] = None):
        if event_type == "grant":
            self.metrics["total_grants"] += 1
        elif event_type == "denial":
            self.metrics["total_denials"] += 1

        event = AuditEvent(
            agent_id=request.agent_id, event_type=event_type,
            action=request.capability, resource=str(request.scope),
            status=status, details=details
        )
        self.audit_logger.log_event(event)

    def shutdown(self):
        """Perform graceful shutdown, closing storage connections."""
        self.storage.close()
