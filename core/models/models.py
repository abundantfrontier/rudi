from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import uuid4
from pydantic import BaseModel, Field

class CapabilityType(str, Enum):
    FILESYSTEM_READ = "filesystem:read"
    FILESYSTEM_WRITE = "filesystem:write"
    NETWORK_CONNECT = "network:connect"
    NETWORK_HTTP = "network:http"
    PROCESS_EXECUTE = "process:execute"
    MODEL_ESCALATE = "model:escalate"
    API_CALL = "api:call"

class GrantType(str, Enum):
    ALLOW_ONCE = "allow_once"
    TIME_BOXED = "time_boxed"
    SESSION = "session"
    PERMANENT = "permanent"

class Persona(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: Optional[str] = None
    metadata: Dict[str, Any] = {}

class Project(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    persona_id: str
    name: str
    description: Optional[str] = None
    metadata: Dict[str, Any] = {}

class CapabilityRequest(BaseModel):
    agent_id: str
    agent_token: Optional[str] = None  # For cryptographic binding/verification
    capability: CapabilityType
    scope: Dict[str, Any]  # e.g., {"path": "/tmp/test.txt"}
    purpose: str
    project_id: Optional[str] = None # Context isolation
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
    project_id: Optional[str] = None
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
    project_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class DelegatedTask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    label: str
    instruction: str
    project_id: Optional[str] = None
    schedule_type: str = "manual"  # "manual", "once", "repeat"
    target_time: Optional[datetime] = None  # For "once"
    interval_seconds: Optional[int] = None  # For "repeat"
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    metadata: Dict[str, Any] = {}

class HistorySummary(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    agent_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    summary: str # High-level summary for the LLM index
    content_hash: Optional[str] = None # Reference to full data if needed
    metadata: Dict[str, Any] = {}

class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    role: str # "user", "assistant", "system", "thought"
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = {}
