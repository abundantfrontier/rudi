import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

// State
let activeApprovalId: string | null = null;
let editingTaskId: string | null = null;
let currentPersonaId: string | null = null;
let currentProjectId: string | null = null;

// UI Elements
const els = {
  status: document.querySelector("#system-status") as HTMLElement,
  mRequests: document.querySelector("#m-requests") as HTMLElement,
  mGrants: document.querySelector("#m-grants") as HTMLElement,
  mDenials: document.querySelector("#m-denials") as HTMLElement,
  mUses: document.querySelector("#m-uses") as HTMLElement,
  mBlocked: document.querySelector("#m-blocked") as HTMLElement,
  mIdFailures: document.querySelector("#m-id-failures") as HTMLElement,
  grantsTable: document.querySelector("#grants-table tbody") as HTMLElement,
  taskGrid: document.querySelector("#task-grid") as HTMLElement,
  
  approvalModal: document.querySelector("#approval-modal") as HTMLElement,
  requestDetails: document.querySelector("#request-details") as HTMLElement,
  grantType: document.querySelector("#grant-type") as HTMLSelectElement,
  btnApprove: document.querySelector("#btn-approve") as HTMLButtonElement,
  btnDeny: document.querySelector("#btn-deny") as HTMLButtonElement,

  taskModal: document.querySelector("#task-modal") as HTMLElement,
  taskModalTitle: document.querySelector("#task-modal-title") as HTMLElement,
  taskLabel: document.querySelector("#task-label") as HTMLInputElement,
  taskInstruction: document.querySelector("#task-instruction") as HTMLTextAreaElement,
  taskScheduleType: document.querySelector("#task-schedule-type") as HTMLSelectElement,
  taskTargetTime: document.querySelector("#task-target-time") as HTMLInputElement,
  taskInterval: document.querySelector("#task-interval") as HTMLInputElement,
  btnAddTask: document.querySelector("#btn-add-task") as HTMLButtonElement,
  btnTaskSave: document.querySelector("#btn-task-save") as HTMLButtonElement,
  btnTaskCancel: document.querySelector("#btn-task-cancel") as HTMLButtonElement,

  pullModelId: document.querySelector("#pull-model-id") as HTMLInputElement,
  btnPullModel: document.querySelector("#btn-pull-model") as HTMLButtonElement,
  btnLoadModel: document.querySelector("#btn-load-model") as HTMLButtonElement,
  btnUnloadModel: document.querySelector("#btn-unload-model") as HTMLButtonElement,
  modelStatus: document.querySelector("#model-status") as HTMLElement,
  ramStatus: document.querySelector("#ram-status") as HTMLElement,

  // Phase 11 Elements
  selectPersona: document.querySelector("#select-persona") as HTMLSelectElement,
  selectProject: document.querySelector("#select-project") as HTMLSelectElement,
  btnNewProject: document.querySelector("#btn-new-project") as HTMLButtonElement,
  thoughtFeed: document.querySelector("#thought-feed") as HTMLElement,
  historyList: document.querySelector("#history-list") as HTMLElement,
  historyQuery: document.querySelector("#history-query") as HTMLInputElement,
  projectModal: document.querySelector("#project-modal") as HTMLElement,
  projectName: document.querySelector("#project-name") as HTMLInputElement,
  projectDesc: document.querySelector("#project-desc") as HTMLTextAreaElement,
  btnProjectSave: document.querySelector("#btn-project-save") as HTMLButtonElement,
  btnProjectCancel: document.querySelector("#btn-project-cancel") as HTMLButtonElement,

  personaModal: document.querySelector("#persona-modal") as HTMLElement,
  personaName: document.querySelector("#persona-name") as HTMLInputElement,
  personaDesc: document.querySelector("#persona-desc") as HTMLTextAreaElement,
  btnNewPersona: document.querySelector("#btn-new-persona") as HTMLButtonElement,
  btnPersonaSave: document.querySelector("#btn-persona-save") as HTMLButtonElement,
  btnPersonaCancel: document.querySelector("#btn-persona-cancel") as HTMLButtonElement,

  // Tab Elements
  tabBtnInteraction: document.querySelector("#tab-btn-interaction") as HTMLButtonElement,
  tabBtnMonitoring: document.querySelector("#tab-btn-monitoring") as HTMLButtonElement,
  tabInteraction: document.querySelector("#tab-interaction") as HTMLElement,
  tabMonitoring: document.querySelector("#tab-monitoring") as HTMLElement,
};

async function refreshData() {
  try {
    await invoke("send_rpc", { method: "metrics.get", params: {} });
    await invoke("send_rpc", { method: "grants.list", params: {} });
    await invoke("send_rpc", { method: "task.list", params: {} });
    if (currentProjectId) {
      await invoke("send_rpc", { method: "history.query", params: { project_id: currentProjectId, query: els.historyQuery.value } });
    }
  } catch (e) {
    console.error("Refresh error:", e);
  }
}

async function refreshContext() {
    await invoke("send_rpc", { method: "persona.list", params: {} });
}

function updateMetrics(metrics: any) {
  els.mRequests.textContent = metrics.total_requests;
  els.mGrants.textContent = metrics.total_grants;
  els.mDenials.textContent = metrics.total_denials;
  els.mUses.textContent = metrics.total_uses;
  els.mBlocked.textContent = metrics.total_blocked;
  els.mIdFailures.textContent = metrics.identity_failures;
}

function updateGrants(grants: any[]) {
  els.grantsTable.innerHTML = "";
  grants.forEach((g) => {
    const row = document.createElement("tr");
    const expiry = g.expires_at ? new Date(g.expires_at).toLocaleString() : "PERMANENT";
    row.innerHTML = `
      <td>${g.agent_id}</td>
      <td><code>${g.capability}</code></td>
      <td>${expiry}</td>
      <td><button class="btn-small btn-danger" onclick="window.revokeGrant('${g.id}')">Revoke</button></td>
    `;
    els.grantsTable.appendChild(row);
  });
}

function updateTasks(tasks: any[]) {
  els.taskGrid.innerHTML = "";
  tasks.forEach((t) => {
    const card = document.createElement("div");
    card.className = "task-card";
    card.innerHTML = `
      <h3>${t.label}</h3>
      <div class="instruction">${t.instruction}</div>
      <div class="schedule">${t.schedule_type}${t.schedule_type === 'repeat' ? ` (${t.interval_seconds}s)` : ''}</div>
      <div class="task-actions">
        <button class="btn-small btn-primary" onclick="window.runTask('${t.id}')">Run Now</button>
        <button class="btn-small" onclick="window.editTask('${t.id}')">Edit</button>
      </div>
    `;
    els.taskGrid.appendChild(card);
  });
}

function updatePersonas(personas: any[]) {
    els.selectPersona.innerHTML = "";
    personas.forEach(p => {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = p.name;
        els.selectPersona.appendChild(opt);
    });
    if (personas.length > 0 && !currentPersonaId) {
        currentPersonaId = personas[0].id;
        updateProjectButtonLabel(personas[0].name);
        invoke("send_rpc", { method: "project.list", params: { persona_id: currentPersonaId } });
    }
}

function updateProjectButtonLabel(personaName: string) {
    els.btnNewProject.textContent = `+ Project to ${personaName}`;
}

function updateProjects(projects: any[]) {
    els.selectProject.innerHTML = "";
    projects.forEach(p => {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = p.name;
        els.selectProject.appendChild(opt);
    });
    if (projects.length > 0 && !currentProjectId) {
        currentProjectId = projects[0].id;
        refreshData();
    }
}

function updateHistory(history: any[]) {
    els.historyList.innerHTML = history.length ? "" : '<div class="empty-state">No history found.</div>';
    history.forEach(s => {
        const item = document.createElement("div");
        item.className = "history-item";
        item.innerHTML = `
            <div class="timestamp">${new Date(s.timestamp).toLocaleString()}</div>
            <div class="summary">${s.summary}</div>
        `;
        els.historyList.appendChild(item);
    });
}

function addThought(agentId: string, thought: string) {
    const firstThought = els.thoughtFeed.querySelector(".empty-state");
    if (firstThought) firstThought.remove();

    const card = document.createElement("div");
    card.className = "thought-card";
    card.innerHTML = `
        <div class="agent-id">${agentId}</div>
        <div class="thought">${thought}</div>
    `;
    els.thoughtFeed.prepend(card);
}

// Window Globals
(window as any).revokeGrant = async (id: string) => {
  await invoke("send_rpc", { method: "grant.revoke", params: { grant_id: id } });
};

(window as any).runTask = async (id: string) => {
  await invoke("send_rpc", { method: "task.run", params: { task_id: id, project_id: currentProjectId } });
};

(window as any).editTask = async (id: string) => {
  editingTaskId = id;
  els.taskModalTitle.textContent = "Edit Task";
  els.taskModal.classList.remove("hidden");
};

async function handleRpcMessage(msg: any) {
  if (msg.method === "approval.required") {
    activeApprovalId = msg.params.approval_id;
    const req = msg.params.request;
    els.requestDetails.innerHTML = `
      <p><b>Agent:</b> ${req.agent_id}</p>
      <p><b>Capability:</b> <code>${req.capability}</code></p>
      <p><b>Purpose:</b> ${req.purpose}</p>
      <p><b>Scope:</b> <pre>${JSON.stringify(req.scope, null, 2)}</pre></p>
    `;
    els.approvalModal.classList.remove("hidden");
  } else if (msg.method === "llm.thought") {
    addThought(msg.params.agent_id, msg.params.thought);
  } else if (msg.method === "grant.updated") {
    await refreshData();
  } else if (msg.result) {
    const res = msg.result;
    if (typeof res === "object" && "total_requests" in res) {
      updateMetrics(res);
      els.status.textContent = "Online";
      els.status.classList.add("online");
    } else if (Array.isArray(res)) {
      if (res.length > 0) {
          if ("instruction" in res[0]) updateTasks(res);
          else if ("persona_id" in res[0]) updateProjects(res);
          else if ("summary" in res[0]) updateHistory(res);
          else if ("capability" in res[0]) updateGrants(res);
          else if ("name" in res[0]) updatePersonas(res);
      }
    } else if (typeof res === "object" && "status" in res) {
        if (res.message?.includes("RAM")) {
            els.ramStatus.textContent = "LOADED";
            els.ramStatus.classList.add("loaded");
            els.btnLoadModel.classList.add("hidden");
            els.btnUnloadModel.classList.remove("hidden");
        } else if (res.message?.includes("unloaded")) {
            els.ramStatus.textContent = "NOT LOADED";
            els.ramStatus.classList.remove("loaded");
            els.btnLoadModel.classList.remove("hidden");
            els.btnUnloadModel.classList.add("hidden");
        }
    }
  }
}

window.addEventListener("DOMContentLoaded", async () => {
  await listen("rpc-msg", (event) => {
    handleRpcMessage(event.payload);
  });

  // Context Selection
  els.selectPersona.onchange = () => {
      currentPersonaId = els.selectPersona.value;
      const personaName = els.selectPersona.options[els.selectPersona.selectedIndex].text;
      updateProjectButtonLabel(personaName);
      invoke("send_rpc", { method: "project.list", params: { persona_id: currentPersonaId } });
  };
  els.selectProject.onchange = () => {
      currentProjectId = els.selectProject.value;
      refreshData();
  };
  els.btnNewProject.onclick = () => els.projectModal.classList.remove("hidden");
  els.btnProjectCancel.onclick = () => els.projectModal.classList.add("hidden");
  els.btnProjectSave.onclick = async () => {
      if (!currentPersonaId) return;
      await invoke("send_rpc", { 
          method: "project.create", 
          params: { persona_id: currentPersonaId, name: els.projectName.value, description: els.projectDesc.value } 
      });
      els.projectModal.classList.add("hidden");
      await invoke("send_rpc", { method: "project.list", params: { persona_id: currentPersonaId } });
  };

  // Task Modal
  els.btnAddTask.onclick = () => {
    editingTaskId = null;
    els.taskModalTitle.textContent = "Create New Task";
    els.taskLabel.value = "";
    els.taskInstruction.value = "";
    els.taskModal.classList.remove("hidden");
  };
  els.btnTaskCancel.onclick = () => els.taskModal.classList.add("hidden");
  els.taskScheduleType.onchange = () => {
    const type = els.taskScheduleType.value;
    document.querySelector("#schedule-once-config")?.classList.toggle("hidden", type !== "once");
    document.querySelector("#schedule-repeat-config")?.classList.toggle("hidden", type !== "repeat");
  };
  els.btnTaskSave.onclick = async () => {
    const task = {
      id: editingTaskId || undefined,
      label: els.taskLabel.value,
      instruction: els.taskInstruction.value,
      project_id: currentProjectId,
      schedule_type: els.taskScheduleType.value,
      target_time: els.taskTargetTime.value || null,
      interval_seconds: parseInt(els.taskInterval.value) || null,
    };
    await invoke("send_rpc", { method: "task.save", params: task });
    els.taskModal.classList.add("hidden");
  };

  // Model Management
  els.btnPullModel.onclick = async () => {
    const model = els.pullModelId.value;
    if (!model) return;
    els.btnPullModel.disabled = true;
    await invoke("send_rpc", { method: "system.pull_model", params: { model } });
  };
  els.btnLoadModel.onclick = async () => {
    const model = els.pullModelId.value;
    els.btnLoadModel.disabled = true;
    await invoke("send_rpc", { method: "llm.preload", params: { model: model || undefined } });
  };
  els.btnUnloadModel.onclick = async () => {
    await invoke("send_rpc", { method: "llm.unload", params: {} });
  };

  // History Search
  els.historyQuery.oninput = () => refreshData();

  // Approval
  els.btnApprove.onclick = async () => {
    if (activeApprovalId) {
      await invoke("send_rpc", {
        method: "grant.approve",
        params: { approval_id: activeApprovalId, grant_type: els.grantType.value, duration: els.grantType.value === "session" ? 3600 : 0 }
      });
      els.approvalModal.classList.add("hidden");
      activeApprovalId = null;
    }
  };
  els.btnDeny.onclick = async () => {
    if (activeApprovalId) {
      await invoke("send_rpc", { method: "grant.deny", params: { approval_id: activeApprovalId } });
      els.approvalModal.classList.add("hidden");
      activeApprovalId = null;
    }
  };

  // Tab Switching
  els.tabBtnInteraction.onclick = () => {
    els.tabBtnInteraction.classList.add("active");
    els.tabBtnMonitoring.classList.remove("active");
    els.tabInteraction.classList.add("active");
    els.tabMonitoring.classList.remove("active");
  };

  els.tabBtnMonitoring.onclick = () => {
    els.tabBtnMonitoring.classList.add("active");
    els.tabBtnInteraction.classList.remove("active");
    els.tabMonitoring.classList.add("active");
    els.tabInteraction.classList.remove("active");
    refreshData();
  };

  await refreshContext();
  setInterval(refreshData, 5000);
});
