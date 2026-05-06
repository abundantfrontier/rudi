# R.U.D.I. Foundational Design Notes

## 1. Agent Identity & Authentication
- **Phase 0/1:** Agents are identified by a unique `agent_id` (UUID) provided in the request.
- **Verification:** For the MVP, we assume a local trust model where the `agent_id` is stable. 
- **Future:** Cryptographic signing of requests and process-level attestation.

## 2. Error Handling & Failure Mode Strategy
- **Enforcement Failure:** If the platform enforcement layer fails to initialize or check a permission, the operation must be blocked (Fail-Closed).
- **Human Timeout:** Default timeout (e.g., 60s). If exceeded, the request is automatically denied.
- **Grant Expiration:** Enforcement layers must check expiration *at the time of use*. Long-running operations should be periodically re-validated.
- **Control Plane Downtime:** Agents must not be able to access resources if the Control Plane is not reachable to verify grants.

## 3. Configuration & Defaults
- **Location:** `~/.rudi/config.yaml` or project-root `rudi-config.yaml`.
- **Defaults:**
  - `default_deny: true`
  - `approval_timeout: 60`
  - `log_level: INFO`
  - `enforcement_strict: true`

## 4. Observability
- **Audit:** Every request/grant/use is logged to `core/audit/`.
- **Metrics:** 
  - `total_requests`
  - `total_grants`
  - `denials_by_user`
  - `denials_by_enforcement`
- **Health:** A simple status check to ensure the Control Plane process is active.

## 5. Path Normalization (Critical for FS Enforcement)
- All paths must be converted to absolute, real paths (resolving symlinks) before policy evaluation or enforcement to prevent directory traversal attacks.
