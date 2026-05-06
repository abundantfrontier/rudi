# R.U.D.I. Capabilities & Approvals System
**Phased Requirements Specification v1.7**  
**Optimized for AI Coding Agents**  
**Date:** May 5, 2026

---

## AI Coding Agent Instructions (READ THESE FIRST — EVERY SESSION)

**CRITICAL RULES — FOLLOW THESE WITHOUT EXCEPTION:**

1. **Always read the full current version of this file** (`rudi-spec.md`) before planning, coding, or suggesting any changes.
2. **Current Active Phase**: Phase 5 — Persistence & State Management.
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

## Phase 5: Persistence & State Management (ACTIVE)

**Objective**  
Transition R.U.D.I. from a volatile, in-memory system to a durable service that preserves grants and identity state across restarts.

**Technical Requirements**
- **Persistent Storage**: Implement SQLite storage for grants and registered agents.
- **Schema**:
    - `grants` table: `id` (PK), `agent_id`, `capability`, `scope` (JSON), `grant_type`, `risk_level`, `expires_at`, `metadata`.
    - `agents` table: `agent_id` (PK), `token_hash` (SHA-256), `created_at`.
- **Durability**: 
    - Write-through: Persistence to DB must occur *before* grant issuance.
    - On Startup: Load all unexpired/permanent grants from DB into memory cache.
- **Encryption**: Support optional AES encryption (using `cryptography`) for sensitive `scope` data (like API keys or specific file paths).

---

## Phase 6: Tauri Desktop Interface (BACKLOG)

**Objective**  
Build a modern, system-tray-based UI for management and approval.

**Technical Requirements**
- **Sidecar Pattern**: Run the Python Control Plane as a separate process.
- **IPC Protocol**: JSON-RPC or similar over a local pipe/socket.
- **Real-time Notifications**: Trigger desktop notifications for background agent requests.

---

## Phase 7: Extensibility & Advanced Capabilities (BACKLOG)

**Objective**  
Support advanced agentic workflows like attenuated sub-grants and dynamic plugins.

**Requirements**
- **Attenuated Grants**: Allow agents to create narrower grants from their existing broad grants.
- **Plugin System**: Standardized interface for adding new `CapabilityType` handlers without core modification.
- **Auto-Approval Rules**: User-defined policies for low-risk, frequent actions.

---

## Change Log

- **2026-05-05 v1.7**: Restored truncated sections. Revised roadmap to Phases 5-10. Detailed Phase 5 Persistence requirements. Set Phase 5 as ACTIVE.
- **2026-05-05 v1.6**: Completed Phase 4. Implemented Process Execution, Model Escalation (Token Budgets), API Call capabilities, and Permanent Grants with extra confirmation. Improved scope matching (wildcards, command prefixes).
- **2026-05-05 v1.5**: Updated Phase 2 and Phase 3 with durability and safety enhancements.
- **2026-05-05 v1.4**: Added Foundational Requirements (Identity, Error Handling, Observability).

---

**End of spec.md**
