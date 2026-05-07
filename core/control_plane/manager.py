import uuid
import os
import threading
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from core.models.models import CapabilityRequest, CapabilityGrant, GrantType, AuditEvent, CapabilityType, Persona, Project, HistorySummary
from core.control_plane.interface import ControlPlaneInterface
from core.policy.engine import PolicyEngine
from core.audit.logger import AuditLogger
from core.audit.store import AuditStore
from core.storage.sqlite_store import SQLiteStore

try:
    from prometheus_client import Counter, Gauge
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

# Define Prometheus metrics
if PROMETHEUS_AVAILABLE:
    REQ_COUNTER = Counter('rudi_capability_requests_total', 'Total capability requests received')
    GRANT_COUNTER = Counter('rudi_grants_total', 'Total grants issued', ['type', 'risk'])
    DENY_COUNTER = Counter('rudi_denials_total', 'Total capability requests denied', ['reason'])
    USE_COUNTER = Counter('rudi_capability_uses_total', 'Total successful resource accesses', ['capability'])
    BLOCK_COUNTER = Counter('rudi_blocked_access_total', 'Total blocked resource accesses', ['capability'])
    ID_FAIL_COUNTER = Counter('rudi_identity_failures_total', 'Total agent identity verification failures')
    ACTIVE_GRANTS_GAUGE = Gauge('rudi_active_grants', 'Current number of active grants')

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
        self.audit_logger = AuditLogger(log_path=config.get("log_path", "audit.log"))
        self.audit_store = AuditStore(log_path=config.get("log_path", "audit.log"))
        self.ui_handler = ui_handler
        self.strict_identity = config.get("strict_identity", False)
        
        # Persistence
        self.storage = storage or SQLiteStore(config.get("db_path", "rudi.db"))
        self.grants: Dict[str, CapabilityGrant] = {g.id: g for g in self.storage.load_all_grants()}
        self.registered_agents: Dict[str, str] = self.storage.get_all_agents() # agent_id -> token_hash
        
        # Ensure Default Persona/Project exists
        self._ensure_defaults()

        self.metrics = {
            "total_requests": 0,
            "total_grants": 0,
            "total_denials": 0,
            "total_uses": 0,
            "total_blocked": 0,
            "identity_failures": 0
        }
        
        if PROMETHEUS_AVAILABLE:
            ACTIVE_GRANTS_GAUGE.set(len(self.grants))

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

    async def request_capability(self, request: CapabilityRequest) -> Optional[CapabilityGrant]:
        """
        Evaluate and potentially grant a requested capability.
        """
        self.metrics["total_requests"] += 1
        if PROMETHEUS_AVAILABLE:
            REQ_COUNTER.inc()
        
        # Log the request itself
        self._log_event(request, "request", "received")
        
        # Verify Agent Identity
        if not self._verify_agent(request.agent_id, request.agent_token):
            self.metrics["identity_failures"] += 1
            if PROMETHEUS_AVAILABLE:
                ID_FAIL_COUNTER.inc()
            self._log_event(request, "denial", "invalid_agent_token")
            return None

        # 1. Check for Attenuated Grant Request
        parent_grant = None
        if request.parent_grant_id:
            with self.lock:
                parent_grant = self.grants.get(request.parent_grant_id)
            
            if not parent_grant:
                self._log_event(request, "denial", "parent_grant_not_found")
                return None
            
            # Security checks for attenuation
            if parent_grant.agent_id != request.agent_id:
                self._log_event(request, "denial", "parent_grant_agent_mismatch")
                return None
            
            if parent_grant.capability != request.capability:
                self._log_event(request, "denial", "parent_grant_capability_mismatch")
                return None
            
            if not self._scope_matches(parent_grant.scope, request.scope):
                self._log_event(request, "denial", "parent_grant_scope_too_broad")
                return None
            
            # Check expiry of parent
            if parent_grant.expires_at and datetime.now() > parent_grant.expires_at:
                self._log_event(request, "denial", "parent_grant_expired")
                return None

            decision = "allow"
            grant_type = GrantType.ALLOW_ONCE
            duration = 0
            if parent_grant.expires_at:
                duration = (parent_grant.expires_at - datetime.now()).total_seconds()
        else:
            # 2. Normal Request Flow
            decision = self.policy_engine.evaluate(request)
            
            if decision == "deny":
                if PROMETHEUS_AVAILABLE:
                    DENY_COUNTER.labels(reason="policy").inc()
                self._log_event(request, "denial", "policy_denied")
                return None
            
            grant_type = GrantType.ALLOW_ONCE
            duration = 0
            
            if decision == "manual_review":
                if not self.ui_handler:
                    self._log_event(request, "denial", "no_ui_handler")
                    return None
                
                timeout = self.config.get("approval_timeout", 60)
                result = await self.ui_handler.ask_approval(request, timeout=timeout)
                
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
            project_id=request.project_id,
            parent_id=request.parent_grant_id,
            constraints=request.constraints,
            expires_at=expires_at
        )
        
        with self.lock:
            self.grants[grant_id] = grant
            self.storage.save_grant(grant)
            if PROMETHEUS_AVAILABLE:
                ACTIVE_GRANTS_GAUGE.inc()
            
        self._log_event(request, "grant", "granted", {
            "grant_id": grant_id, 
            "type": grant_type,
            "background": request.background,
            "expires_at": str(expires_at) if expires_at else None
        })
        return grant

    def validate_grant(self, agent_id: str, capability_type: str, scope: Dict[str, Any], project_id: Optional[str] = None) -> bool:
        """
        Check if an agent currently holds a valid grant for a specific action.
        Ensures strict project_id isolation.
        """
        now = datetime.now()
        with self.lock:
            for grant_id, grant in list(self.grants.items()):
                # Expiry check
                if grant.expires_at and now > grant.expires_at:
                    self.audit_logger.log_event(AuditEvent(
                        agent_id=agent_id, event_type="expiration",
                        action=capability_type, resource=str(scope),
                        status="expired", project_id=grant.project_id, details={"grant_id": grant_id}
                    ))
                    del self.grants[grant_id]
                    self.storage.delete_grant(grant_id)
                    continue

                # Project Isolation check
                if project_id and grant.project_id != project_id:
                    continue

                # Identity and Capability match
                if grant.agent_id == agent_id and grant.capability == capability_type:
                    # Scope match
                    if self._scope_matches(grant.scope, scope):
                        # 1. Advanced Constraints Check
                        if not self._check_constraints(grant, scope):
                            continue

                        # 2. Stateful consumption for Token Budgets
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
                        if PROMETHEUS_AVAILABLE:
                            USE_COUNTER.labels(capability=capability_type).inc()
                        self.audit_logger.log_event(AuditEvent(
                            agent_id=agent_id, event_type="use",
                            action=capability_type, resource=str(scope),
                            status="success"
                        ))
                        return True
        
        self.metrics["total_blocked"] += 1
        if PROMETHEUS_AVAILABLE:
            BLOCK_COUNTER.labels(capability=capability_type).inc()
        self.audit_logger.log_event(AuditEvent(
            agent_id=agent_id, event_type="use",
            action=capability_type, resource=str(scope),
            status="blocked"
        ))
        return False

    def _scope_matches(self, grant_scope: Dict[str, Any], requested_scope: Dict[str, Any]) -> bool:
        """
        Check if requested_scope is covered by grant_scope.
        All keys in grant_scope must be satisfied.
        """
        import fnmatch
        for key, g_val in grant_scope.items():
            # Special case: token_budget matches against tokens
            if key == "token_budget":
                if "tokens" not in requested_scope or requested_scope["tokens"] > g_val:
                    return False
                continue
            
            # Special case: command_prefix matches against command
            if key == "command_prefix":
                if "command" not in requested_scope or not requested_scope["command"].startswith(g_val):
                    return False
                continue

            # Special case: allowed_methods matches against method
            if key == "allowed_methods":
                if "method" in requested_scope:
                    if str(requested_scope["method"]).upper() not in [m.upper() for m in g_val]:
                        return False
                # If 'method' not in request, we assume it's a generic check, but usually it's there
                continue

            # Special case: url_pattern matches against url
            if key == "url_pattern":
                if "url" in requested_scope:
                    if not fnmatch.fnmatch(str(requested_scope["url"]), g_val):
                        return False
                continue

            # Standard keys must be present in requested_scope
            if key not in requested_scope:
                return False
            
            r_val = requested_scope[key]
            
            # Special handling for paths
            if key == "path":
                try:
                    g_path = os.path.realpath(os.path.expanduser(str(g_val)))
                    r_path = os.path.realpath(os.path.expanduser(str(r_val)))
                    if os.path.commonpath([g_path, r_path]) != g_path:
                        return False
                except (ValueError, OSError):
                    if g_val != r_val: return False
                continue

            # Special handling for host wildcards (network:connect)
            if key == "host" and isinstance(g_val, str) and g_val.startswith("*."):
                suffix = g_val[1:]
                if not (r_val.lower().endswith(suffix.lower()) or r_val.lower() == g_val[2:].lower()):
                    return False
                continue

            # Generic matching (wildcard if string, equality otherwise)
            if isinstance(g_val, str) and isinstance(r_val, str):
                if not fnmatch.fnmatch(r_val, g_val):
                    return False
            elif g_val != r_val:
                return False
                
        return True

    def _check_constraints(self, grant: CapabilityGrant, requested_scope: Dict[str, Any]) -> bool:
        """
        Validate advanced constraints like time-of-day or usage limits.
        """
        if not grant.constraints:
            return True

        now = datetime.now()

        # 1. Time Range Constraint: {"time_range": {"start": "09:00", "end": "17:00"}}
        if "time_range" in grant.constraints:
            tr = grant.constraints["time_range"]
            current_time = now.strftime("%H:%M")
            if not (tr["start"] <= current_time <= tr["end"]):
                return False

        # 2. Max Usage Count: {"max_calls": 100}
        if "max_calls" in grant.constraints:
            used = grant.metadata.get("usage_count", 0)
            if used >= grant.constraints["max_calls"]:
                return False
            # Increment usage in metadata (stateful)
            grant.metadata["usage_count"] = used + 1
            # We don't save to storage here to avoid excessive DB writes during high-volume use,
            # but for strict accuracy we should. Let's do it for now.
            self.storage.save_grant(grant)

        # 3. Max File Size: {"max_file_size": 1048576}
        if "max_file_size" in grant.constraints:
            if "size" in requested_scope:
                if requested_scope["size"] > grant.constraints["max_file_size"]:
                    return False

        return True

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
                if PROMETHEUS_AVAILABLE:
                    ACTIVE_GRANTS_GAUGE.dec()
                return True
        return False

    def _log_event(self, request: CapabilityRequest, event_type: str, status: str, details: Optional[Dict[str, Any]] = None):
        if event_type == "grant":
            self.metrics["total_grants"] += 1
            if PROMETHEUS_AVAILABLE:
                GRANT_COUNTER.labels(
                    type=details.get("type", "unknown") if details else "unknown",
                    risk="low"
                ).inc()
        elif event_type == "denial":
            self.metrics["total_denials"] += 1
            if PROMETHEUS_AVAILABLE:
                if status == "user_denied":
                    DENY_COUNTER.labels(reason="user").inc()
                elif status == "no_ui_handler":
                    DENY_COUNTER.labels(reason="no_ui").inc()
                elif status == "invalid_agent_token":
                    pass # Handled in request_capability
                else:
                    DENY_COUNTER.labels(reason=status).inc()

        event = AuditEvent(
            agent_id=request.agent_id, event_type=event_type,
            action=request.capability, resource=str(request.scope),
            status=status, project_id=request.project_id, details=details
        )
        self.audit_logger.log_event(event)

    def shutdown(self):
        """Perform graceful shutdown, closing storage connections."""
        self.storage.close()

    # --- New Phase 11 Features ---

    def _ensure_defaults(self):
        """Bootstrap the system with a default persona and project."""
        personas = self.storage.load_all_personas()
        if not personas:
            default_persona = Persona(name="Default Persona", description="Auto-generated default context.")
            self.storage.save_persona(default_persona)
            default_project = Project(persona_id=default_persona.id, name="Default Project")
            self.storage.save_project(default_project)

    def create_persona(self, name: str, description: Optional[str] = None) -> Persona:
        p = Persona(name=name, description=description)
        self.storage.save_persona(p)
        return p

    def create_project(self, persona_id: str, name: str, description: Optional[str] = None) -> Project:
        p = Project(persona_id=persona_id, name=name, description=description)
        self.storage.save_project(p)
        return p

    def list_personas(self) -> List[Persona]:
        return self.storage.load_all_personas()

    def list_projects(self, persona_id: Optional[str] = None) -> List[Project]:
        return self.storage.load_projects(persona_id)

    def add_history_summary(self, project_id: str, agent_id: str, summary: str, metadata: Dict[str, Any] = {}):
        s = HistorySummary(project_id=project_id, agent_id=agent_id, summary=summary, metadata=metadata)
        self.storage.save_history_summary(s)
        # Log to audit too
        self.audit_logger.log_event(AuditEvent(
            agent_id=agent_id, event_type="history", action="summarize", 
            resource=project_id, status="success", project_id=project_id,
            details={"summary": summary}
        ))

    def query_history(self, project_id: str, query: Optional[str] = None) -> List[HistorySummary]:
        return self.storage.query_history(project_id, query)
