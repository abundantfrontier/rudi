# R.U.D.I. Capabilities & Approvals System
**Phased Requirements Specification v1.10**  
**Optimized for AI Coding Agents**  
**Date:** May 7, 2026

---

## AI Coding Agent Instructions (READ THESE FIRST — EVERY SESSION)

**CRITICAL RULES — FOLLOW THESE WITHOUT EXCEPTION:**

1. **Always read the full current version of this file** (`rudi-spec.md`) before planning, coding, or suggesting any changes.
2. **Current Active Phase**: Phase 9 — LLM Integration & Real Agent Testing.
3. Never implement features from future phases unless explicitly instructed.
4. Every implementation **must** respect the Core Principles, Cross-Platform Strategy, and Foundational Requirements below.
5. After completing work on any phase, update this spec.md with:
   - What was implemented
   - Any deviations or decisions made
   - Updated "Current Active Phase" marker
6. If any requirement is unclear or contradictory, **ask for clarification** instead of guessing.
7. Prefer clean, well-documented, type-hinted, extensible code.
8. Enforcement must be real and bypass-proof (this is non-negotiable).
9. Always follow the recommended repository structure and cross-platform separation rules.

---

## Overall Vision & Non-Negotiable Core Principles

**Vision**  
R.U.D.I. provides a capability-based mediation layer (Control Plane) that lets agents request bounded authority. The Control Plane evaluates requests, surfaces them for human approval when needed, issues grants with explicit purpose/scope/duration, and **enforces** those grants at runtime. Agents never hold capabilities directly.  

This model enables safe, usable background/autonomous behavior while keeping humans in control of high-impact actions — directly addressing the risks observed in systems like OpenClaw.

**Core Principles**
- **Least Privilege by Default**: Agents start with zero permissions.
- **Mediation over Possession**: Capabilities are **always issued and enforced by the Control Plane**.
- **Metadata-Rich Grants**: Every grant must carry explicit metadata (purpose, scope, duration, requesting agent, human approver).
- **Human visibility**: Easy one-click revocation and visibility into active grants at all times.
- **Durable Audit Trail**: 100% durable audit trail of every request, evaluation, decision, and use.
- **Fail-Secure**: Time-boxed or review-gated authority is preferred; timeouts or unreachable users result in automatic denial.

---

## Documentation Overview

R.U.D.I. maintains several supporting documents to guide development and usage:

- **[rudi-spec.md](./rudi-spec.md)** — The main specification and development guide. This is the primary document for AI coding agents and contributors.
- **[README.md](./README.md)** — High-level project overview and getting started guide.
- **[docs/use_cases.md](./docs/use_cases.md)** — Example use cases, primarily focused on research and information gathering agents.
- **[docs/foundational_design.md](./docs/foundational_design.md)** — Core design decisions around identity, error handling, configuration, and observability.
- **[docs/error_handling.md](./docs/error_handling.md)** — Detailed strategies for handling failures, timeouts, and edge cases.
- **[docs/threat_model.md](./docs/threat_model.md)** — Security threat model and considerations.
- **[docs/progress.md](./docs/progress.md)** — Tracks implementation progress across phases.

---

## Foundational Requirements (COMPLETED)

**Agent Identity & Authentication**
- Agents are identified by a unique `agent_id`.
- **Refinement**: Implemented token-based verification (`agent_token`) and Strict Identity Mode.

**Error Handling & Failure Modes**
- Enforcement failure results in immediate blocking (Fail-Closed).
- Human approval timeouts default to denial.
- Grant expiration checked at time of use.
- Centralized strategy documented in `docs/error_handling.md`.

**Path Normalization**
- All filesystem paths are converted to absolute, real paths (`os.path.realpath`) to prevent symlink and traversal attacks.

---

## Phase 1: Core Interactive Loop MVP (COMPLETED)
- **Objective**: Implement the fundamental request/approve/enforce cycle.
- **Achievements**:
    - Centralized `ControlPlaneManager`.
    - Darwin/Linux Filesystem enforcement adapters.
    - Simple CLI approval dialog (`ui/dialog.py`).
    - Verified with `examples/toy_agent.py`.

---

## Phase 2: Expand Grant Types & Hierarchy (COMPLETED)
- **Objective**: Support time-boxed grants, network capabilities, and hierarchical scoping.
- **Achievements**:
    - Added `TIME_BOXED` and `SESSION` grant types.
    - Implemented `NETWORK_CONNECT` capability with host/port scoping.
    - **Hierarchical Path Scoping**: Granting access to a directory recursively grants access to its children.
    - Multi-agent thread-safety with locks.

---

## Phase 3: Background & Durable Auditing (COMPLETED)
- **Objective**: Support autonomous background behavior and 100% durable logs.
- **Achievements**:
    - High-risk action surfacing for background agents.
    - **Durable Logging**: Every audit event is flushed with `fsync` before action completion.
    - Dashboard improvements for active grants and revocation.

---

## Phase 4: Remaining v1 Capabilities & Hardening (COMPLETED)
- **Objective**: Add Process Execution, Model Escalation, and Permanent grants.
- **Achievements**:
    - **`PROCESS_EXECUTE`**: Added command-prefix matching and sandboxing interface.
    - **`MODEL_ESCALATE`**: Implemented stateful **Token Budgets** that decrement on use.
    - **Permanent Grants**: Added extra "CONFIRM" requirement in UI for zero-expiry grants.
    - **Host Wildcards**: Support for `*.example.com` in network connect grants.

---

## Phase 5: Persistence & State Management (COMPLETED)

**Objective**  
Transition R.U.D.I. from a volatile, in-memory system to a durable service that preserves grants and identity state across restarts.

**Status: COMPLETED**
- Implemented **SQLite persistent storage** for grants and registered agents.
- Developed **`SQLiteStore`** with support for atomic "Write-Through" durability.
- Added **Token Hashing (SHA-256)** to ensure agent tokens are never stored in plain text.
- Implemented **Optional AES Encryption** for sensitive grant scope data using the `cryptography` library.
- Verified that grants and agent registrations survive service restarts with `tests/common/test_persistence.py`.

---

## Phase 6: Tauri Desktop Interface (COMPLETED)

**Objective**  
Build a modern, system-tray-based UI for management and approval.

**Status: COMPLETED**
- Implemented the **Sidecar Pattern**: Rust backend automatically spawns the Python Control Plane.
- Developed a **Bidirectional IPC Bridge**: UDS JSON-RPC messages are bridged to Tauri Frontend events.
- Created a **Reactive Dashboard (Vanilla TS + Vite)**:
    - Real-time **System Metrics** visualization.
    - **Active Grants** list with one-click revocation.
    - **Interactive Approval Modal** triggered by incoming agent requests.
- Integrated **Strict Server-Side Enforcement**: The UI and Server now collaborate to mediate all resource access.

---

## Phase 7: Extensibility & Advanced Capabilities (COMPLETED)

**Objective**  
Support advanced agentic workflows like attenuated sub-grants and dynamic plugins.

**Status: COMPLETED**
- Implemented **Attenuated Grants**: Agents can now derive narrower, auto-approved sub-grants from their existing permissions.
- Added **Advanced Scoping & Constraints**: Supported time-of-day restrictions (`time_range`) and stateful usage limits (`max_calls`).
- Developed **Auto-Approval Rules**: Added a policy engine that handles low-risk requests via configurable wildcard patterns (e.g., `/tmp/public/*`).
- Created a **Dynamic Plugin System**: Standardized `CapabilityPlugin` interface for adding third-party capabilities without core modification.
- Enhanced **Generic Scope Matching**: Integrated `fnmatch` wildcard support for all string-based scope keys.

---

## Phase 8: Production Hardening (COMPLETED)

**Objective**  
Finalize packaging, distribution, and operational readiness.

**Status: COMPLETED**
- **Structured Logging**: Transitioned to pure **JSONL** format with built-in **`RotatingFileHandler`** (10MB, 5 backups).
- **Standardized Metrics**: Integrated **Prometheus** metrics export (port 8000) with counters for requests, grants, and blocks.
- **Packaging**: Enhanced **`pyproject.toml`** with metadata, dependencies, and a **`rudi-server`** console script entry point.
- **Error Handling**: Improved operator experience with structured JSON-RPC error codes and messages.

---

## Phase 9: LLM Integration & Real Agent Testing (ACTIVE)

**Objective**  
End-to-end verification with local LLMs and adversarial testing.

**Requirements**
- Build proper test agents that use local models (Ollama, LM Studio, etc.)
- Run realistic multi-step agent scenarios.
- Evaluate error handling behavior from an agent’s perspective.
- Perform adversarial testing (e.g. prompt injection attempts to request overly broad capabilities).

---

## Change Log

- **2026-05-07 v1.10**: Completed Phase 8. Implemented structured JSONL logging with rotation, Prometheus metrics, and console script packaging. Set Phase 9 as ACTIVE.
- **2026-05-05 v1.9**: Completed Phase 7. Implemented Attenuated Grants, Advanced Scoping (Constraints), Auto-Approval Rules, and a dynamic Plugin System. Enhanced scope matching with wildcards. Set Phase 8 as ACTIVE.
- **2026-05-05 v1.8**: Completed Phase 5. Implemented SQLite persistence, SHA-256 token hashing, and optional AES encryption for grants. Set Phase 6 as ACTIVE.
- **2026-05-05 v1.7**: Restored truncated sections. Revised roadmap to Phases 5-10. Detailed Phase 5 Persistence requirements. Set Phase 5 as ACTIVE.
- **2026-05-05 v1.6**: Completed Phase 4. Implemented Process Execution, Model Escalation (Token Budgets), API Call capabilities, and Permanent Grants with extra confirmation. Improved scope matching (wildcards, command prefixes).
- **2026-05-05 v1.5**: Updated Phase 2 and Phase 3 with durability and safety enhancements.
- **2026-05-05 v1.4**: Added Foundational Requirements (Identity, Error Handling, Observability).

---

**End of spec.md**
