# R.U.D.I. Error Handling & Failure Modes

This document outlines the strategy for handling various error conditions and failure modes within the R.U.D.I. ecosystem.

## 1. UI Dialog Timeouts
- **Behavior**: If the user does not respond to an approval request within the configured timeout (default: 60s), R.U.D.I. automatically **DENIES** the request.
- **Rationale**: Fail-secure. No action should be permitted without explicit or pre-existing approval.
- **Background Agents**: For background agents, timeouts are handled the same way. If a human is not present to approve a high-risk action, it is blocked.

## 2. Grant Expiration During Operation
- **Behavior**: Grants are checked for expiry *at the moment of use* in `validate_grant`. 
- **Long-running tasks**: If an operation (e.g., a large file read) is started while a grant is valid but the grant expires *during* the operation, the current enforcement layer behavior is to allow the *start* of the operation. 
- **Future Improvement**: Add periodic re-validation for long-running stream operations.

## 3. Platform Inconsistencies
- **Behavior**: R.U.D.I. uses a cross-platform adapter pattern. If an enforcement feature (e.g., sandboxing) is not available on a platform (like Linux placeholders), the system logs a warning but falls back to the most secure common denominator (blocking the action if it cannot be safely enforced).
- **Validation**: Path normalization (`os.path.realpath`) is used to ensure symlinks and path traversal attempts are handled consistently across macOS and Linux.

## 4. Agent Identity Failures
- **Behavior**: If an `agent_token` is provided but does not match the registered token for that `agent_id`, the request is immediately denied and logged as a security event.
- **Unregistered Agents**: By default, the system allows unregistered agents for backward compatibility, but this can be restricted in the configuration (`require_registration: true`).

## 5. Control Plane Health
- **Behavior**: The Control Plane is designed to be stateless regarding persistent grants (they are currently in-memory). If the Control Plane restarts, all active grants (except PERMANENT ones if they were persisted) are lost.
- **Audit Integrity**: Audit logs are flushed to disk with `fsync` before any action is allowed, ensuring that even if the system crashes, the record of the grant or denial is preserved.
