import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

// State
let activeApprovalId: string | null = null;
let editingTaskId: string | null = null;

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
};

async function refreshData() {
  try {
    await invoke("send_rpc", { method: "metrics.get", params: {} });
    await invoke("send_rpc", { method: "grants.list", params: {} });
    await invoke("send_rpc", { method: "task.list", params: {} });
  } catch (e) {
    console.error("Refresh error:", e);
  }
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
        <button class="btn-small btn-danger" onclick="window.deleteTask('${t.id}')">Delete</button>
      </div>
    `;
    els.taskGrid.appendChild(card);
  });
}

// Window Globals for dynamic HTML
(window as any).revokeGrant = async (id: string) => {
  await invoke("send_rpc", { method: "grant.revoke", params: { grant_id: id } });
};

(window as any).runTask = async (id: string) => {
  await invoke("send_rpc", { method: "task.run", params: { task_id: id } });
};

(window as any).deleteTask = async (id: string) => {
  if (confirm("Delete this task?")) {
    await invoke("send_rpc", { method: "task.delete", params: { task_id: id } });
  }
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
  } else if (msg.method === "grant.updated") {
    await refreshData();
  } else if (msg.result) {
    if (typeof msg.result === "object" && "status" in msg.result) {
      // Model results
      if (msg.result.status === "success") {
        if (msg.result.message?.includes("RAM")) {
            els.ramStatus.textContent = "LOADED";
            els.ramStatus.classList.add("loaded");
            els.btnLoadModel.classList.add("hidden");
            els.btnUnloadModel.classList.remove("hidden");
            els.modelStatus.textContent = "Model weights are warm and ready for instant responses.";
        } else if (msg.result.message?.includes("unloaded")) {
            els.ramStatus.textContent = "NOT LOADED";
            els.ramStatus.classList.remove("loaded");
            els.btnLoadModel.classList.remove("hidden");
            els.btnUnloadModel.classList.add("hidden");
            els.modelStatus.textContent = "RAM cleared. Next task will lazy-load.";
        } else {
            els.modelStatus.textContent = "Model downloaded successfully!";
            els.modelStatus.className = "status-text success";
        }
      } else {
        els.modelStatus.textContent = "Action failed.";
        els.modelStatus.className = "status-text error";
      }
      els.btnPullModel.disabled = false;
      els.btnLoadModel.disabled = false;
    } else if (typeof msg.result === "object" && "total_requests" in msg.result) {
      updateMetrics(msg.result);
      els.status.textContent = "Online";
      els.status.classList.add("online");
    } else if (Array.isArray(msg.result)) {
      if (msg.result.length > 0 && "instruction" in msg.result[0]) {
        updateTasks(msg.result);
      } else {
        updateGrants(msg.result);
      }
    }
  }
}

window.addEventListener("DOMContentLoaded", async () => {
  await listen("rpc-msg", (event) => {
    handleRpcMessage(event.payload);
  });

  // Task Modal Toggles
  els.btnAddTask.onclick = () => {
    editingTaskId = null;
    els.taskModalTitle.textContent = "Create New Task";
    els.taskLabel.value = "";
    els.taskInstruction.value = "";
    els.taskModal.classList.remove("hidden");
  };

  els.btnTaskCancel.onclick = () => els.taskModal.classList.add("hidden");

  els.btnPullModel.onclick = async () => {
    const model = els.pullModelId.value;
    if (!model) return;
    els.btnPullModel.disabled = true;
    els.modelStatus.textContent = `Pulling ${model}... (this may take several minutes)`;
    els.modelStatus.className = "status-text";
    try {
      await invoke("send_rpc", { method: "system.pull_model", params: { model } });
    } catch (e) {
      els.modelStatus.textContent = `Error: ${e}`;
      els.modelStatus.className = "status-text error";
      els.btnPullModel.disabled = false;
    }
  };

  els.btnLoadModel.onclick = async () => {
    const model = els.pullModelId.value;
    els.btnLoadModel.disabled = true;
    els.modelStatus.textContent = "Loading model into RAM...";
    try {
      await invoke("send_rpc", { method: "llm.preload", params: { model: model || undefined } });
    } catch (e) {
      els.modelStatus.textContent = `Error loading: ${e}`;
      els.btnLoadModel.disabled = false;
    }
  };

  els.btnUnloadModel.onclick = async () => {
    try {
      await invoke("send_rpc", { method: "llm.unload", params: {} });
    } catch (e) {
      console.error("Unload error:", e);
    }
  };

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
      schedule_type: els.taskScheduleType.value,
      target_time: els.taskTargetTime.value || null,
      interval_seconds: parseInt(els.taskInterval.value) || null,
    };
    await invoke("send_rpc", { method: "task.save", params: task });
    els.taskModal.classList.add("hidden");
  };

  // Approval Modal Actions
  els.btnApprove.onclick = async () => {
    if (activeApprovalId) {
      await invoke("send_rpc", {
        method: "grant.approve",
        params: {
          approval_id: activeApprovalId,
          grant_type: els.grantType.value,
          duration: els.grantType.value === "session" ? 3600 : 0
        }
      });
      els.approvalModal.classList.add("hidden");
      activeApprovalId = null;
    }
  };

  els.btnDeny.onclick = async () => {
    if (activeApprovalId) {
      await invoke("send_rpc", {
        method: "grant.deny",
        params: { approval_id: activeApprovalId }
      });
      els.approvalModal.classList.add("hidden");
      activeApprovalId = null;
    }
  };

  await refreshData();
  setInterval(refreshData, 5000);
});
