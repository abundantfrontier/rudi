# R.U.D.I. Capabilities & Approvals System
**Phased Requirements Specification v1.6**  
**Optimized for AI Coding Agents**  
**Date:** May 5, 2026

---

## AI Coding Agent Instructions (READ THESE FIRST — EVERY SESSION)

**CRITICAL RULES — FOLLOW THESE WITHOUT EXCEPTION:**

1. **Always read the full current version of this file** (`rudi-spec.md`) before planning, coding, or suggesting any changes.
2. **Current Active Phase**: Phase 5 — Post-v1 Extensibility (update this line only when a phase is officially completed).
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

**How to work with this file:**
- Start every new session with: "Read the full rudi-spec.md and implement the Current Active Phase."
- Use `@rudi-spec.md` when referencing it in chat.
- When a phase passes its Exit Criteria, update the marker and add an entry to the Change Log.

---

## Overall Vision & Non-Negotiable Core Principles

**Vision**  
R.U.D.I. provides a capability-based mediation layer (Control Plane) that lets agents request bounded authority. The Control Plane evaluates requests, surfaces them for human approval when needed, issues grants with explicit purpose/scope/duration, and **enforces** those grants at runtime. Agents never hold capabilities directly.  

This model enables safe, usable background/autonomous behavior while keeping humans in control of high-impact actions — directly addressing the risks observed in systems like OpenClaw.

**Core Principles (must be respected in every phase and every line of code)**

- Least privilege by default.
- Capabilities are **always issued and enforced by the Control Plane** — never held directly by the agent.
- Every grant must carry explicit metadata: purpose, scope, duration, requesting agent, human approver (when applicable), and timestamp.
- Human visibility and easy one-click revocation at all times.
- Design against approval fatigue (safe defaults prominent, risky options de-emphasized).
- Full audit trail of every request, evaluation, decision, grant, use, modification, expiration, and revocation.
- Time-bounded or review-gated authority is strongly preferred for autonomous/background work.

---

## Cross-Platform Strategy & Recommended Repository Structure

R.U.D.I. must support **both Linux and macOS** (Apple Silicon and Intel) as first-class targets from day one.

### Guiding Principles
- Maximize shared / common code (core logic should be ~80-90% platform-independent).
- Use platform-specific adapters **only** where truly necessary (mainly enforcement layers).
- The common layer must **never** import platform-specific code directly.
- Use clear interfaces / abstract base classes / protocols so the core can remain clean.
- Path handling, permission models, and sandboxing differ significantly between platforms — plan for this early.

---

## Foundational Requirements (Must Be Addressed by End of Phase 1)

...

---

## Phase 2: Expand Grant Types + Second Capability + Improved Dialog (COMPLETED)
...

---

## Phase 3: Background / Autonomous Support + Full Auditing & Revocation (COMPLETED)
...

---

## Phase 4: Remaining v1 Capability Types + Permanent Grants (Stretch) (COMPLETED)

**Objective**  
Add Code Execution, Model Escalation, API call capabilities, and Permanent grants.

**Status: COMPLETED**
- Implemented **`PROCESS_EXECUTE`** with platform-specific sandboxing (`platforms/darwin/process_enforcement.py`).
- Added **`MODEL_ESCALATE`** with stateful **Token Budget** consumption.
- Implemented **`API_CALL`** capability with generic scope matching.
- Developed **Permanent Grants** with mandatory **"CONFIRM"** extra confirmation in UI.
- Enhanced **`_scope_matches`** to support host wildcards (`*.example.com`) and command prefixes.
- Improved path normalization using `os.path.realpath` for consistent cross-platform symlink handling.
- Verified with comprehensive tests in `tests/common/test_phase4.py`.

**Exit Criteria / Success Metrics**
- [x] Code execution is enforced and sandboxed (at an interface level).
- [x] Model escalation correctly decrements token budgets.
- [x] Permanent grants require extra user confirmation and don't expire.
- [x] Host wildcards and command prefixes work as expected.
- [x] Phase ready for Phase 5.

---

## Phase 5: Post-v1 Extensibility
...

---

## Change Log

- **2026-05-05 v1.6**: Completed Phase 4. Implemented Process Execution, Model Escalation (Token Budgets), API Call capabilities, and Permanent Grants with extra confirmation. Improved scope matching (wildcards, command prefixes).
- **2026-05-05 v1.5**: Updated Phase 2 and Phase 3 with critical durability and safety enhancements: Hierarchical path scoping, 100% durable audit logs (fsync), and thread-safe grant management. Updated Current Active Phase marker.
- **2026-05-05 v1.4**: Added new **Foundational Requirements** section based on panel review. Covered Agent Identity, Error Handling & Failure Modes, Configuration, basic Observability, and Testing Strategy. Updated Phase 0 and Phase 1 prompt packages and requirements accordingly. Bumped version to v1.4.

---

**End of spec.md**
