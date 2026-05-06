# R.U.D.I. (Responsible User-Delegated Interface)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform: macOS / Linux](https://img.shields.io/badge/Platform-macOS%20%2F%20Linux-lightgrey.svg)](#)

R.U.D.I. is a capability-based mediation layer (Control Plane) designed to give AI agents bounded, revocable, and human-approved authority. Instead of agents holding direct access to system resources, they must request specific "capabilities" from R.U.D.I., which are then evaluated, approved by a human (when necessary), and strictly enforced at runtime.

This model enables safe, autonomous agent behavior by addressing the risks of over-privileged access and lack of human oversight in modern AI systems.

---

## 🌟 Core Principles

- **Least Privilege by Default**: Agents start with zero permissions.
- **Mediation over Possession**: Agents never hold capabilities directly; the Control Plane manages and enforces all access.
- **Human-in-the-Loop**: High-impact actions require explicit human approval via an interactive dialog.
- **Explicit Metadata**: Every grant includes purpose, scope, duration, requesting agent, and human approver.
- **Full Auditability**: 100% durable audit trail (with `fsync`) of every request, decision, and resource use.
- **Time-Bounded Authority**: Preference for session-based or time-boxed grants to prevent "privilege creep."

---

## 🏗️ Architecture

R.U.D.I. is built with a cross-platform strategy, maximizing shared logic while using specialized adapters for platform-specific enforcement (macOS and Linux).

```text
rudi/
├── core/                  # Platform-independent logic
│   ├── control_plane/     # Central request management & evaluation
│   ├── policy/            # Logic for matching requests to existing grants
│   ├── audit/             # Durable logging and event storage
│   ├── models/            # Pydantic data models for grants/requests
│   └── common/            # Shared configuration and utilities
├── platforms/             # Platform-specific enforcement layers
│   ├── darwin/            # macOS implementation (Process, FS, Network)
│   └── linux/             # Linux implementation (Placeholders/Real)
├── adapters/              # Platform adapter selector
├── ui/                    # User interface (Dialogs for approval)
├── examples/              # Usage demonstrations for agents
└── tests/                 # Comprehensive test suite
```

---

## 🛡️ Security Features

- **Strict Identity Mode**: When enabled (`strict_identity: true` in config), all agents MUST be registered with a token. Unregistered agents or invalid tokens result in immediate denial.
- **Hierarchical Scoping**: Path-based capabilities support directory-level grants (e.g., granting `/tmp/` allows access to all sub-files).
- **Token Budgets**: Model escalation capabilities can be bounded by stateful token limits that decrement on use.

---

## 📊 Observability & Metrics

The Control Plane exposes real-time metrics for system monitoring:

- `total_requests`: Number of capability requests received.
- `total_grants`: Number of approved grants.
- `total_denials`: Number of denied requests.
- `total_uses`: Number of successful resource accesses.
- `total_blocked`: Number of blocked resource accesses.
- `identity_failures`: Number of requests with invalid or missing agent tokens.

Operators can query this state via `cp.get_metrics()` or check overall health via `cp.get_status()`.

---

## 🛡️ Capabilities Supported (v1)

| Capability | Description | Scope Support |
| :--- | :--- | :--- |
| `filesystem:read` | Read access to files/directories | Realpath normalization, hierarchical scoping |
| `filesystem:write` | Write access to files/directories | Realpath normalization, hierarchical scoping |
| `network:connect` | Outbound network connections | Hostnames, IPs, Wildcards (`*.example.com`) |
| `process:execute` | Execution of system commands | Command prefixes, sandboxing (interface-level) |
| `model:escalate` | Access to more powerful LLMs | Stateful **Token Budgets** |
| `api:call` | Generic API calls | Service/Endpoint matching |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- macOS (Darwin) or Linux

### Installation
```bash
git clone https://github.com/your-repo/rudi.git
cd rudi
pip install -r requirements.txt  # If requirements.txt is provided
```

### Running Tests
Verify the installation and platform compatibility:
```bash
pytest tests/common/test_comprehensive.py
```

---

## 📖 Usage Example

Here is a simplified example of how an agent interacts with R.U.D.I.:

```python
from core.control_plane.manager import ControlPlane
from core.models.models import CapabilityRequest, CapabilityType

# 1. Initialize Control Plane
cp = ControlPlane()

# 2. Agent requests access to read a sensitive file
request = CapabilityRequest(
    agent_id="agent-001",
    capability=CapabilityType.FILESYSTEM_READ,
    scope={"path": "/etc/hosts"},
    purpose="Checking local host configurations"
)

# 3. Request evaluation (triggers UI dialog if not already granted)
grant = cp.request_capability(request)

if grant:
    print(f"Access granted! Grant ID: {grant.id}")
    # 4. Use the capability through the enforcement layer
    content = cp.fs_enforcement.read_file("agent-001", "/etc/hosts")
else:
    print("Access denied by user.")
```

---

## 📜 Audit Logging
R.U.D.I. maintains an `audit.log` in the root directory. Every interaction is recorded as a JSON entry and flushed to disk using `fsync` to ensure no event is lost, even in the event of a crash.

---

## 🗺️ Roadmap
- **Phase 5**: Post-v1 Extensibility (Plugin system for new capabilities).
- **Remote Control Plane**: Managing capabilities across multiple machines.
- **Advanced Sandboxing**: Deeper integration with macOS `sandbox-exec` and Linux `namespaces/cgroups`.

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
