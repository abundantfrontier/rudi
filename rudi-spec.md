# R.U.D.I. Capabilities & Approvals System
**Phased Requirements Specification v1.16**  
**Optimized for AI Coding Agents**  
**Date:** May 7, 2026

---

## AI Coding Agent Instructions (READ THESE FIRST — EVERY SESSION)

**CRITICAL RULES — FOLLOW THESE WITHOUT EXCEPTION:**

1. **Always read the full current version of this file** (`rudi-spec.md`) before planning, coding, or suggesting any changes.
2. **Current Active Phase**: Phase 12 — Persistent Chat Interface & Agent Steering.
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
- **Achievements**: IPC-Based HTTP Mediation, Granular Policy Enforcement (Read-Only GET), URL Pattern Matching, Air-Gapped Ready architecture.

---

## Phase 11: Personas, Projects & Semantic Memory (COMPLETED)

**Objective**  
Isolate user contexts and provide agents with long-term, searchable "memory" of past interactions.

**Status: COMPLETED**
- **Personas & Projects**: Implemented logical grouping and isolation. Every task, grant, and history item is now context-aware.
- **Activity Streams**: Developed a real-time "Thought Feed" in the Tauri UI, allowing users to see agent reasoning alongside capability requests.
- **Semantic History Indexing**: Built a system that automatically summarizes agent work into a searchable SQLite index, accessible via \`history:query\`.
- **Atomic Validation**: Refactored the enforcement layer so that platform-specific adapters (Darwin/Linux) are the sole, project-aware authoritative points for validation. This definitively resolved double-consumption bugs for stateful constraints.
- **UI Refactor**: Reorganized the dashboard into a two-tabbed interface (**Interaction** and **Monitoring**) for better focus and usability, including a breadcrumb context switcher.
- **Window Management**: Optimized default window size (1100x900) to fit the comprehensive command center layout.

---

## Phase 12: Persistent Chat Interface & Agent Steering (ACTIVE)

**Objective**  
Transform the R.U.D.I. dashboard into a conversational Command Center with persistent context and real-time steering.

**Requirements**
- **Persistent Chat History**: Implement a SQLite-backed chat log isolated by Project.
- **Interactive Chat UI**: Replace the read-only Activity Stream with a two-way Chat Interface.
- **The Chat Agent**: Implement a long-lived conversational agent (`chat_agent.py`) that can recall history and execute commands.
- **Agent Control**: Allow the user to provide corrections, hints, or new instructions to active agents via the chat window.

---

## Phase 13: Deep Interposition & Core Toolset (BACKLOG)

**Objective**  
Demonstrate the "Virtual Service" pattern and provide essential agent tools.

**Requirements**
- **Interposition APIs**: Build a proxy for a complex service (e.g., Google Calendar).
    - R.U.D.I. holds the actual OAuth credentials.
    - R.U.D.I. exposes a local IPC endpoint that mimics a safe subset of the real API.
- **Core Workforce**: Implement high-utility plugins for Web Search (Tavily/DDG), Web Scraping, and System Health.

---

## Phase 14: Remote / Distributed Control Plane (BACKLOG)

**Objective**  
Support cross-machine capability mediation.

---

## Change Log

- **2026-05-07 v1.16**: Inserted Phase 12: Persistent Chat Interface. Moved Interposition to Phase 13. Set Phase 12 as ACTIVE.
- **2026-05-07 v1.15**: Completed Phase 11. Implemented Personas, Projects, Activity Streams, and Semantic Memory. Refactored UI into Interaction/Monitoring tabs. Set Phase 12 as ACTIVE.
- **2026-05-07 v1.14**: Roadmap Expansion. Detailed Phase 11 (Personas/Memory) and Phase 12 (Interposition/Toolset). Set Phase 11 as ACTIVE.
- **2026-05-07 v1.13**: Completed Phase 10. Implemented IPC-based HTTP mediation.

---

**End of spec.md**
