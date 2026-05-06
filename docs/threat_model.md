# R.U.D.I. Threat Model v1.0

## Overview
R.U.D.I. acts as a Control Plane between an Agent (requesting party) and a Resource (filesystem, network, etc.). This document identifies threats to the system and our mitigation strategies.

## 1. Threat Actors
- **Compromised Agent:** An agent that has been taken over or is acting maliciously to exceed its granted scope.
- **Malicious Agent:** An agent designed specifically to bypass R.U.D.I. or abuse grants.
- **Local User (Non-Root):** An attacker on the same system trying to intercept grants or audit logs.

## 2. Attack Surface
- **Communication Channel:** The mechanism by which Agents talk to the Control Plane.
- **Enforcement Layer:** The platform-specific code that restricts access.
- **Grant Storage:** Where active and past grants are stored.
- **Policy Engine:** Logic that decides whether to prompt a human.

## 3. High-Level Threats & Mitigations

| Threat | Description | Mitigation |
| :--- | :--- | :--- |
| **Enforcement Bypass** | Agent accesses a resource without a grant by going around the enforcement layer. | Runtime enforcement must be mandatory and platform-native (e.g., Mac sandbox, Linux namespaces). |
| **Identity Spoofing** | Agent A pretends to be Agent B to use B's grants. | Every request must include a verifiable `agent_id` (Phase 1: UUID; Phase 2+: Signatures/Attestation). |
| **Grant Tampering** | An attacker modifies an active grant to extend duration or scope. | Grants are managed solely by the Control Plane; agents never hold the grant object directly. |
| **Approval Fatigue** | Human clicks "Allow" without reading due to high volume. | Intelligent defaults, scope minimization, and "Session" grants to reduce prompt frequency. |
| **Audit Log Erasure** | Attacker deletes evidence of unauthorized access. | Audit logs should be append-only and ideally sent to a protected local or remote sink. |

## 4. Platform-Specific Considerations

### macOS (Darwin)
- **Threat:** Bypassing TCC or Sandbox via XPC or AppleScript.
- **Mitigation:** Use established macOS security APIs and validate paths strictly against the sandbox profile.

### Linux
- **Threat:** Escaping namespaces or exploiting `sudo` misconfigurations.
- **Mitigation:** Use `seccomp`, namespaces, or cgroups for enforcement where appropriate.

## 5. Failure Modes
- **Control Plane Crash:** Default to "Deny All" if the mediator is unavailable.
- **Timeout:** If the human doesn't respond, the request is denied.
