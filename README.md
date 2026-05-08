# R.U.D.I. (Responsible User-Delegated Interface)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform: macOS / Linux](https://img.shields.io/badge/Platform-macOS%20%2F%20Linux-lightgrey.svg)](#)

R.U.D.I. is a capability-based mediation layer (Control Plane) designed to give AI agents bounded, revocable, and human-approved authority. Instead of agents holding direct access to system resources, they must request specific "capabilities" from R.U.D.I., which are then evaluated, approved by a human, and strictly enforced at runtime.

R.U.D.I. now features a **Conversational Command Center**, transforming the dashboard from a monitoring tool into a proactive, local-first AI workspace.

---

## 🌟 Core Principles

- **Least Privilege by Default**: Agents start with zero permissions.
- **Mediation over Possession**: Agents never hold credentials or capabilities; the Control Plane enforces all access.
- **Human-in-the-Loop**: High-impact actions require explicit approval via an interactive Desktop interface.
- **Strict Context Isolation**: Authority is siloed by **Persona** and **Project**, preventing cross-context data leaks.
- **Full Auditability**: 100% durable audit trail (with `fsync`) of every request, decision, and use.
- **Local-First**: Optimized for Apple Silicon (MLX) and offline-capable capability mediation.

---

## 🏗️ Architecture

R.U.D.I. uses a "Sidecar" architecture, combining a high-performance Python Control Plane with a modern Tauri/Rust Desktop interface.

```text
rudi/
├── core/                  # Control Plane Logic
│   ├── control_plane/     # IPC Server, Request Management & Evaluation
│   ├── policy/            # Grant Matching & Auto-Approval Logic
│   ├── audit/             # Durable JSONL logging and SQLite event storage
│   ├── llm/               # Pluggable Providers (MLX, OpenAI)
│   ├── storage/           # SQLite Persistence (Grants, Chat, Memory)
│   └── models/            # Pydantic data models
├── platforms/             # Platform-specific Enforcement Adapters
│   ├── darwin/            # macOS implementation (Process, FS, Network)
│   └── linux/             # Linux implementation
├── ui/
│   └── app/               # Tauri/Vite/TypeScript Frontend
│       ├── src/           # Reactive Dashboard & Chat UI
│       └── src-tauri/     # Rust-based IPC Bridge & Sidecar Bootloader
├── examples/              # Agents (ChatAgent, ResearchAgent, UITester)
├── tests/
│   └── integration/       # Headless System Verification Suite
└── rudi-spec.md           # The primary specification and roadmap
```

---

## 🚀 Key Features (v1.16)

### 💬 Conversational Command Center
- **Persistent, Isolated Chat**: Every project has its own private, searchable chat history.
- **Agent Steering**: Interactively guide background agents, providing hints or corrections in real-time.
- **Closed-Loop Reasoning**: Agents can "talk" and "act" in the same turn. Capability requests appear as interactive popups within the chat flow.

### 🧠 Semantic Memory & Context
- **Persona/Project Silos**: Strict separation of history, grants, and tasks between different user contexts.
- **Automated Summarization**: Agent actions are automatically summarized and indexed in a searchable SQLite database.

### 💻 Local LLM Management
- **Model Library**: Automatically scans for local MLX models on your Mac.
- **Smart RAM Management**: One-click preloading with real-time byte counters and background progress bars.
- **Autoloading**: Remembers your last-used model and restores it instantly on startup.

---

## 🛡️ Capabilities Supported

| Capability | Description | Scope Support |
| :--- | :--- | :--- |
| `filesystem:read` | Read access to files/directories | Realpath normalization, hierarchical scoping |
| `filesystem:write` | Write access to files/directories | Realpath normalization, hierarchical scoping |
| `network:http` | Granular HTTP mediation | Method matching (GET/POST), URL pattern matching |
| `network:connect` | Outbound raw TCP connections | Hostnames, IPs, Wildcards (`*.example.com`) |
| `process:execute` | Execution of system commands | Command prefixes, strict parent-process monitoring |
| `history:query` | Access to past agent work | Project-isolated semantic search |

---

## 🛡️ Reliability & Security
- **Parent Watchdog**: The Control Plane automatically self-terminates if the UI is closed (Dead Man's Switch).
- **Headless Verification**: A comprehensive integration suite (`verify_system.py`) that simulates the UI to verify security boundaries in seconds.
- **Atomic Validation**: Enforcement is performed exclusively by platform-specific adapters to prevent state consumption errors.

---

## 🤖 Getting Started

### Prerequisites
- Python 3.10+
- Node.js & npm
- macOS (Apple Silicon recommended for MLX) or Linux

### Installation
```bash
git clone https://github.com/your-repo/rudi.git
cd rudi
pip install -r requirements.txt
cd ui/app && npm install
```

### Running the App
```bash
# Launch the full Conversational Command Center
npm run tauri dev
```

### Automated Verification
```bash
# Verify the entire system (IPC, DB, Isolation, LLM) headlessly
export PYTHONPATH=$PYTHONPATH:.
python3 tests/integration/verify_system.py
```

---

## 🗺️ Roadmap
- **Phase 12**: Persistent Chat & Agent Steering (**DONE**)
- **Phase 13**: Deep Interposition (Google Calendar Proxy, Web Workforce) (**ACTIVE**)
- **Phase 14**: Remote / Distributed Control Plane (**BACKLOG**)

---

## 📜 Audit Logging
R.U.D.I. maintains an `audit.log` and a searchable SQLite event store. Every interaction is recorded as a JSON entry and flushed to disk using `fsync` to ensure a permanent, tamper-evident security record.

---

## 📄 License
This project is licensed under the MIT License.
