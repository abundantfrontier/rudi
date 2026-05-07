# R.U.D.I. Capabilities & Approvals System
**Phased Requirements Specification v1.14**  
**Optimized for AI Coding Agents**  
**Date:** May 7, 2026

---

## AI Coding Agent Instructions (READ THESE FIRST — EVERY SESSION)

**CRITICAL RULES — FOLLOW THESE WITHOUT EXCEPTION:**

1. **Always read the full current version of this file** (`rudi-spec.md`) before planning, coding, or suggesting any changes.
2. **Current Active Phase**: Phase 11 — Personas, Projects & Semantic Memory.
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
- **Achievements**: Implemented token-based verification (`agent_token`) and **Strict Identity Mode** which mandates valid tokens for all requests.

**Error Handling & Failure Modes**
- Enforcement failure results in immediate blocking (Fail-Closed).
- Human approval timeouts default to denial.
- Grant expiration checked at time of use.
- **Achievements**: Centralized strategy documented in `docs/error_handling.md`.

**Path Normalization**
- All filesystem paths are converted to absolute, real paths (`os.path.realpath`) to prevent symlink and traversal attacks.

---

## Phase 1: Core Interactive Loop MVP (COMPLETED)
- **Achievements**: Centralized `ControlPlaneManager`, realpath-based FS enforcement, CLI approval dialog.

---

## Phase 2: Expand Grant Types & Hierarchy (COMPLETED)
- **Achievements**: `TIME_BOXED`/`SESSION` grants, `NETWORK_CONNECT` with scoping, Hierarchical Path Scoping.

---

## Phase 3: Background & Durable Auditing (COMPLETED)
- **Achievements**: High-risk action surfacing, 100% durable audit logs with `os.fsync`, revocation dashboard.

---

## Phase 4: Remaining v1 Capabilities & Hardening (COMPLETED)
- **Achievements**: `PROCESS_EXECUTE` with sandboxing, `MODEL_ESCALATE` with Token Budgets, Permanent Grants.

---

## Phase 5: Persistence & State Management (COMPLETED)
- **Achievements**: SQLite storage for grants/agents/tasks, SHA-256 token hashing, optional AES scope encryption.

---

## Phase 6: Tauri Desktop Interface (COMPLETED)
- **Achievements**: Sidecar pattern (Rust/Python), Bidirectional IPC Bridge, Reactive Vanilla TS + Vite Dashboard.

---

## Phase 7: Extensibility & Advanced Capabilities (COMPLETED)
- **Achievements**: Attenuated (Derived) Grants, Advanced scoping (time-of-day, max-calls), Auto-Approval Policy Engine, Dynamic Plugin System.

---

## Phase 8: Production Hardening (COMPLETED)
- **Achievements**: Pure JSONL rotating logs, Prometheus metrics exporter (port 8000), `rudi-server` CLI entry point.

---

## Phase 9: LLM Integration & Real Agent Testing (COMPLETED)
- **Achievements**: Pluggable `MLXProvider` (Apple Silicon) and `OpenAIProvider`, Model preloading/RAM management, `examples/research_agent.py` reasoning loop.

---

## Phase 10: Advanced Network Mediation & Air-Gapped Proxying (COMPLETED)

**Objective**  
Implement a secure network proxy layer to enable "air-gapped" control over external API communication.

**Achievements**
- **IPC-Based HTTP Mediation**: Implemented `network:http` capability where agents delegate HTTP requests to the Control Plane.
- **Granular Policy Enforcement**: Implemented method filtering (Read-Only GET vs POST) and URL pattern matching.
- **Air-Gapped Ready**: Enables agents with zero network possession to communicate via the mediated Control Plane.
- **Integrated Client**: Added `http_request` helper to `ControlPlaneClient`.

---

## Phase 11: Personas, Projects & Semantic Memory (ACTIVE)

**Objective**  
Isolate user contexts and provide agents with long-term, searchable "memory" of past interactions.

**Requirements**
- **Personas & Projects**: Implement logical grouping of grants and history.
    - **Personas** (e.g., Work, Personal): Default permission sets and identities.
    - **Projects**: Scoped contexts within a persona (e.g., "Research Topic A").
- **Activity Streams**: Real-time "Thought" feed in UI showing LLM reasoning alongside capability requests.
- **Semantic History Indexing**: 
    - Automatically summarize agent actions and findings into a searchable index.
    - Allow agents to query this index (via `history:query`) to quickly recall past work without re-executing high-cost tasks.
- **Storage**: Extend SQLite schema to support persona/project ownership and history summaries.

---

## Phase 12: Deep Interposition & Core Toolset (BACKLOG)

**Objective**  
Demonstrate the "Virtual Service" pattern and provide essential agent tools.

**Requirements**
- **Interposition APIs**: Build a proxy for a complex service (e.g., Google Calendar).
    - R.U.D.I. holds the actual OAuth credentials.
    - R.U.D.I. exposes a local IPC endpoint that mimics a safe subset of the real API.
    - Agents use the local endpoint; R.U.D.I. maps and validates every call before proxying to the real service.
- **Core Workforce**: Implement high-utility plugins for Web Search (Tavily/DDG), Web Scraping, and System Health.
- **Interactive Feedback**: Support a "Chat" window in the dashboard for real-time agent steering.

---

## Phase 13: Remote / Distributed Control Plane (BACKLOG)

**Objective**  
Support cross-machine capability mediation.

---

## Change Log

- **2026-05-07 v1.14**: Roadmap Expansion. Detailed Phase 11 (Personas/Memory) and Phase 12 (Interposition/Toolset). Set Phase 11 as ACTIVE.
- **2026-05-07 v1.13**: Completed Phase 10. Implemented IPC-based HTTP mediation.
- **2026-05-07 v1.12**: Roadmap Pivot. Added Phase 10 (Advanced Network Mediation) and Phase 11 (UX Refinement).
- **2026-05-07 v1.11**: Completed Phase 9. Implemented pluggable LLM backend.

---

**End of spec.md**
