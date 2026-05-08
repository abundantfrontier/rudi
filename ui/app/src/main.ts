import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

// State
let activeApprovalId: string | null = null;
let editingTaskId: string | null = null;
let currentPersonaId: string | null = null;
let currentProjectId: string | null = "default"; // Default fail-safe
let lastPullRequestId: string | null = null;

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
  modelSearchQuery: document.querySelector("#model-search-query") as HTMLInputElement,
  btnSearchModels: document.querySelector("#btn-search-models") as HTMLButtonElement,
  modelSearchResults: document.querySelector("#model-search-results") as HTMLElement,
  localModelsList: document.querySelector("#local-models") as HTMLElement,
  activeDownloads: document.querySelector("#active-downloads") as HTMLElement,

  // Context Elements
  selectPersona: document.querySelector("#select-persona") as HTMLSelectElement,
  selectProject: document.querySelector("#select-project") as HTMLSelectElement,
  btnNewProject: document.querySelector("#btn-new-project") as HTMLButtonElement,
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

  // Phase 12 Chat Elements
  chatLog: document.querySelector("#chat-log") as HTMLElement,
  chatInput: document.querySelector("#chat-input") as HTMLTextAreaElement,
  btnChatSend: document.querySelector("#btn-chat-send") as HTMLButtonElement,
  agentIndicator: document.querySelector("#agent-indicator") as HTMLElement,
};

async function callRpc(method: string, params: any): Promise<string> {
    const res = await invoke("send_rpc", { method, params }) as any;
    return res.id;
}

function formatBytes(bytes: number, decimals = 2) {
    if (!bytes || bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

async function refreshData(isInitial: boolean = false) {
  try {
    await callRpc("metrics.get", {});
    await callRpc("grants.list", {});
    await callRpc("task.list", { project_id: currentProjectId });
    await callRpc("llm.list_local_models", {});
    await callRpc("llm.status", { isInitial });
    if (currentProjectId) {
      await callRpc("history.query", { project_id: currentProjectId, query: els.historyQuery.value });
      await callRpc("chat.history", { project_id: currentProjectId });
    }
  } catch (e) {
    console.error("Refresh error:", e);
  }
}

async function refreshContext() {
    await callRpc("persona.list", {});
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
    if (personas.length === 0) {
        const opt = document.createElement("option");
        opt.textContent = "No Personas";
        els.selectPersona.appendChild(opt);
        return;
    }
    personas.forEach(p => {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = p.name;
        els.selectPersona.appendChild(opt);
    });
    // Selection logic
    if (!currentPersonaId) {
        currentPersonaId = personas[0].id;
        els.selectPersona.value = currentPersonaId;
    }
    updateProjectButtonLabel(els.selectPersona.options[els.selectPersona.selectedIndex].text);
    callRpc("project.list", { persona_id: currentPersonaId });
}

function updateProjectButtonLabel(personaName: string) {
    els.btnNewProject.textContent = `+ Project to ${personaName}`;
}

function updateProjects(projects: any[]) {
    els.selectProject.innerHTML = "";
    if (projects.length === 0) {
        const opt = document.createElement("option");
        opt.textContent = "No Projects";
        els.selectProject.appendChild(opt);
        currentProjectId = null;
        return;
    }
    projects.forEach(p => {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = p.name;
        els.selectProject.appendChild(opt);
    });
    // Selection logic
    if (!currentProjectId || !projects.find(p => p.id === currentProjectId)) {
        currentProjectId = projects[0].id;
        els.selectProject.value = currentProjectId as string;
    }
    refreshData();
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

function updateLocalModels(models: string[]) {
    els.localModelsList.innerHTML = models.length ? "" : '<div class="empty-state">No local models found.</div>';
    models.forEach(id => {
        const item = document.createElement("div");
        item.className = "local-model-item";
        item.innerHTML = `
            <div class="model-id" title="${id}">${id}</div>
            <button class="btn-small btn-success" onclick="window.loadLocalModel('${id}')">Load</button>
        `;
        els.localModelsList.appendChild(item);
    });
}

function updateDownloadProgress(modelId: string, percent: number, error?: string, current?: number, total?: number) {
    const safeId = modelId.replace(/[^a-z0-9]/gi, '-');
    let item = document.querySelector(`#dl-${safeId}`) as HTMLElement;
    
    if (!item) {
        const empty = els.activeDownloads.querySelector(".empty-state");
        if (empty) empty.remove();
        
        item = document.createElement("div");
        item.id = `dl-${safeId}`;
        item.className = "download-item";
        item.innerHTML = `
            <div class="model-id">${modelId}</div>
            <div class="progress-container">
                <div class="progress-bar" style="width: 0%"></div>
            </div>
            <div class="dl-stats" style="font-size: 10px; color: #64748b; margin-top: 2px;"></div>
            <div class="error-msg danger hidden" style="font-size: 10px; margin-top: 4px;"></div>
        `;
        els.activeDownloads.appendChild(item);
    }
    
    const bar = item.querySelector(".progress-bar") as HTMLElement;
    const stats = item.querySelector(".dl-stats") as HTMLElement;
    const errorEl = item.querySelector(".error-msg") as HTMLElement;

    if (percent >= 0) {
        bar.parentElement!.classList.remove("hidden");
        bar.style.width = `${percent}%`;
        if (current && total) {
            stats.textContent = `${formatBytes(current)} / ${formatBytes(total)} (${percent}%)`;
        } else {
            stats.textContent = `${percent}%`;
        }
        if (percent >= 100) {
            setTimeout(() => {
                if (item.parentNode) item.remove();
                if (els.activeDownloads.children.length === 0) {
                    els.activeDownloads.innerHTML = '<div class="empty-state">No active downloads.</div>';
                }
            }, 2000);
            refreshData(); 
        }
    } else {
        bar.parentElement!.classList.add("hidden");
        errorEl.textContent = `Download Failed: ${error || 'Unknown Error'}`;
        errorEl.classList.remove("hidden");
    }
}

function updateChatHistory(history: any[]) {
    els.chatLog.innerHTML = "";
    if (history.length === 0) {
        els.chatLog.innerHTML = '<div class="empty-state">Start a conversation with R.U.D.I...</div>';
    } else {
        history.forEach(addChatMessage);
    }
    els.chatLog.scrollTop = els.chatLog.scrollHeight;
}

function addChatMessage(msg: any) {
    console.log("[UI] Rendering Message:", msg.role, msg.content);
    const empty = els.chatLog.querySelector(".empty-state");
    if (empty) empty.remove();

    const div = document.createElement("div");
    div.className = `chat-message ${msg.role}`;
    div.textContent = msg.content;
    els.chatLog.appendChild(div);
    els.chatLog.scrollTop = els.chatLog.scrollHeight;
}

function addThought(agentId: string, thought: string) {
    const div = document.createElement("div");
    div.className = "chat-message thought";
    div.innerHTML = `<small>[${agentId}]</small><br>${thought}`;
    els.chatLog.appendChild(div);
    els.chatLog.scrollTop = els.chatLog.scrollHeight;
}

// Window Globals
(window as any).revokeGrant = async (id: string) => {
  await callRpc("grant.revoke", { grant_id: id });
};

(window as any).runTask = async (id: string) => {
  console.log("[UI] Running task:", id);
  await callRpc("task.run", { task_id: id, project_id: currentProjectId });
};

(window as any).editTask = async (id: string) => {
  editingTaskId = id;
  els.taskModalTitle.textContent = "Edit Task";
  els.taskModal.classList.remove("hidden");
};

(window as any).selectModel = (id: string) => {
    els.pullModelId.value = id;
    els.modelSearchResults.classList.add("hidden");
};

(window as any).loadLocalModel = async (id: string) => {
    els.ramStatus.textContent = "LOADING...";
    els.ramStatus.className = "status-badge loading";
    await callRpc("llm.preload", { model: id });
};

async function handleRpcMessage(msg: any) {
  console.log("[RPC EVENT]", msg);
  
  els.status.textContent = "Online";
  els.status.classList.add("online");

  if (msg.error) {
      console.error("[RPC ERROR]", msg.error);
      return;
  }
  
  // 1. Notifications (Async events from server)
  if (msg.method === "chat.message") {
      addChatMessage(msg.params);
      if (msg.params.role === 'assistant') els.agentIndicator.classList.add("hidden");
  } else if (msg.method === "llm.load_progress") {
      const { step, percent, current, total } = msg.params;
      els.ramStatus.textContent = `LOADING: ${step} [${formatBytes(current)} / ${formatBytes(total)}] (${percent}%)`;
      els.ramStatus.className = "status-badge loading";
  } else if (msg.method === "llm.download_progress") {
      updateDownloadProgress(msg.params.model_id, msg.params.percent, msg.params.error, msg.params.current, msg.params.total);
  } else if (msg.method === "approval.required") {
    activeApprovalId = msg.params.approval_id;
    const req = msg.params.request;
    els.requestDetails.innerHTML = `<p><b>Agent:</b> ${req.agent_id}</p><p><b>Capability:</b> <code>${req.capability}</code></p><p><b>Purpose:</b> ${req.purpose}</p><p><b>Scope:</b> <pre>${JSON.stringify(req.scope, null, 2)}</pre></p>`;
    els.approvalModal.classList.remove("hidden");
  } else if (msg.method === "llm.thought") {
    addThought(msg.params.agent_id, msg.params.thought);
  } else if (msg.method === "grant.updated") {
    await refreshData();
  } 
  
  // 2. Results (Responses to our calls)
  if (msg.result) {
    const res = msg.result;
    if (typeof res === "object" && res !== null && "total_requests" in res) {
      updateMetrics(res);
    } else if (typeof res === "object" && res !== null && "models" in res) {
        updateModelSearchResults(res.models);
    } else if (typeof res === "object" && res !== null && "status" in res && "percent" in res) {
        // Response to llm.status
        if (res.status === "loading") {
            els.ramStatus.textContent = `LOADING: ${res.step} (${res.percent}%)`;
            els.ramStatus.className = "status-badge loading";
            els.btnLoadModel.disabled = true;
        } else if (res.status === "loaded") {
            els.ramStatus.textContent = "LOADED";
            els.ramStatus.className = "status-badge loaded";
            els.btnLoadModel.classList.add("hidden");
            els.btnUnloadModel.classList.remove("hidden");
        } else {
            els.ramStatus.textContent = "NOT LOADED";
            els.ramStatus.className = "status-badge";
            els.btnLoadModel.classList.remove("hidden");
            els.btnUnloadModel.classList.add("hidden");
        }
    } else if (Array.isArray(res)) {
        // Robust list dispatcher
        if (res.length === 0) {
            // Check request metadata if we had it, but for now we'll rely on refresh context
            return;
        }
        const first = res[0];
        if (typeof first === 'string') updateLocalModels(res);
        else if ("instruction" in first) updateTasks(res);
        else if ("persona_id" in first) updateProjects(res);
        else if ("summary" in first) updateHistory(res);
        else if ("capability" in first) updateGrants(res);
        else if ("name" in first) updatePersonas(res);
        else if ("role" in first) updateChatHistory(res);
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
      updateProjectButtonLabel(els.selectPersona.options[els.selectPersona.selectedIndex].text);
      callRpc("project.list", { persona_id: currentPersonaId });
  };
  els.selectProject.onchange = () => {
      currentProjectId = els.selectProject.value;
      refreshData();
  };
  els.btnNewProject.onclick = () => els.projectModal.classList.remove("hidden");
  els.btnProjectCancel.onclick = () => els.projectModal.classList.add("hidden");
  els.btnProjectSave.onclick = async () => {
      if (!currentPersonaId) return;
      await callRpc("project.create", { persona_id: currentPersonaId, name: els.projectName.value, description: els.projectDesc.value });
      els.projectModal.classList.add("hidden");
      await callRpc("project.list", { persona_id: currentPersonaId });
  };

  els.btnNewPersona.onclick = () => els.personaModal.classList.remove("hidden");
  els.btnPersonaCancel.onclick = () => els.personaModal.classList.add("hidden");
  els.btnPersonaSave.onclick = async () => {
    await callRpc("persona.create", { name: els.personaName.value, description: els.personaDesc.value });
    els.personaModal.classList.add("hidden");
    await refreshContext();
  };

  // Chat Interaction
  els.btnChatSend.onclick = async () => {
      const content = els.chatInput.value;
      console.log("[UI] Sending Message. Context:", currentProjectId, "Content:", content);
      if (!content) return;
      
      // Force default if null
      const projId = currentProjectId || "default";
      
      els.chatInput.value = "";
      els.agentIndicator.classList.remove("hidden");
      
      try {
        await callRpc("chat.send", { project_id: projId, content });
      } catch (e) {
        console.error("[UI] Chat Send Error:", e);
        els.agentIndicator.classList.add("hidden");
      }
  };
  els.chatInput.onkeydown = (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          els.btnChatSend.click();
      }
  };

  // Task Management
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
    await callRpc("task.save", task);
    els.taskModal.classList.add("hidden");
    await refreshData();
  };

  // Model Management
  els.btnPullModel.onclick = async () => {
    const model = els.pullModelId.value;
    if (!model) return;
    els.btnPullModel.disabled = true;
    els.btnPullModel.textContent = "Starting...";
    lastPullRequestId = await callRpc("system.pull_model", { model });
  };

  els.btnSearchModels.onclick = async () => {
      const query = els.modelSearchQuery.value;
      if (!query) return;
      els.btnSearchModels.disabled = true;
      els.btnSearchModels.textContent = "Searching...";
      els.modelSearchResults.classList.add("loading-active");
      await callRpc("llm.search_models", { query });
  };
  els.btnLoadModel.onclick = async () => {
    const model = els.pullModelId.value;
    els.btnLoadModel.disabled = true;
    els.ramStatus.textContent = "LOADING...";
    els.ramStatus.className = "status-badge loading";
    await callRpc("llm.preload", { model: model || undefined });
  };
  els.btnUnloadModel.onclick = async () => {
    await callRpc("llm.unload", {});
  };

  // Approval flow
  els.btnApprove.onclick = async () => {
    if (activeApprovalId) {
      await callRpc("grant.approve", { approval_id: activeApprovalId, grant_type: els.grantType.value, duration: els.grantType.value === "session" ? 3600 : 0 });
      els.approvalModal.classList.add("hidden");
      activeApprovalId = null;
    }
  };
  els.btnDeny.onclick = async () => {
    if (activeApprovalId) {
      await callRpc("grant.deny", { approval_id: activeApprovalId });
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

  // Bootstrap
  await refreshContext();
  await refreshData(true);
  setInterval(() => refreshData(false), 5000);
});
