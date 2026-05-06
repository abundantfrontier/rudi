# AI Agent Workflow Guide

This document provides clear, actionable guidance for AI coding agents contributing to the R.U.D.I. project.

## 🚀 The R.U.D.I. Lifecycle

### 1. Research & Research (Source of Truth)
- **Always read `rudi-spec.md` first.** This is the definitive source of truth for the project's vision, architecture, and current development state.
- Check `docs/progress.md` to see exactly what has been implemented and what is currently in progress.

### 2. Strategy & Implementation
- **Focus only on the "Current Active Phase"** as defined in `rudi-spec.md`. Do not implement features from future phases unless explicitly instructed.
- Respect the **Core Principles** (Least Privilege, Mediation, Durable Auditing).
- Prioritize **Fail-Secure** behavior for all enforcement and UI logic.

### 3. Verification
- All code changes must be accompanied by relevant tests in `tests/common/`.
- Run the full suite before submitting: `export PYTHONPATH=$PYTHONPATH:. && python3 tests/common/test_comprehensive.py`.

### 4. Documentation Update (Crucial)
- Upon completing a phase or significant sub-task:
    - Update `rudi-spec.md` Change Log and mark objectives as COMPLETED.
    - Update `docs/progress.md` with checkmarks.
    - If a new phase has been started, update the "Current Active Phase" marker in `rudi-spec.md`.

## 🛡️ Security Mandate
- Never introduce bypasses to the Control Plane.
- Ensure all path handling uses `os.path.realpath`.
- All audit events must be flushed to disk (`fsync`) before returning control to an agent.
