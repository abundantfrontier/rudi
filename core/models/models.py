from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class CapabilityType(str, Enum):
    FILESYSTEM_READ = "filesystem:read"
    FILESYSTEM_WRITE = "filesystem:write"
    NETWORK_CONNECT = "network:connect"
    PROCESS_EXECUTE = "process:execute"
    MODEL_ESCALATE = "model:escalate"
    API_CALL = "api:call"

class GrantType(str, Enum):
    ALLOW_ONCE = "allow_once"
    TIME_BOXED = "time_boxed"
    SESSION = "session"
    PERMANENT = "permanent"

class CapabilityRequest(BaseModel):
    agent_id: str
    agent_token: Optional[str] = None  # For cryptographic binding/verification
    capability: CapabilityType
    scope: Dict[str, Any]  # e.g., {"path": "/tmp/test.txt"}
    purpose: str
    parent_grant_id: Optional[str] = None # ID of a broader grant to derive from
    constraints: Optional[Dict[str, Any]] = None # Advanced rules (time, rate limits, etc.)
    background: bool = False  # Is the agent running in the background?
    requested_at: datetime = Field(default_factory=datetime.now)

class CapabilityGrant(BaseModel):
    id: str
    agent_id: str
    capability: str # Allow strings for dynamic plugins
    scope: Dict[str, Any]
    grant_type: GrantType
    risk_level: str = "low"  # "low", "medium", "high"
    parent_id: Optional[str] = None # ID of the parent grant if this is derived
    constraints: Optional[Dict[str, Any]] = None # Inherited or applied constraints
    expires_at: Optional[datetime] = None
    granted_at: datetime = Field(default_factory=datetime.now)
    last_used_at: Optional[datetime] = None
    metadata: Dict[str, Any] = {}

class AuditEvent(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: str  # "request", "grant", "denial", "use", "revocation"
    agent_id: str
    action: str
    resource: str
    status: str  # "success", "blocked", "expired"
    details: Optional[Dict[str, Any]] = None
