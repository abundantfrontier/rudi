import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

// State
let activeApprovalId: string | null = null;

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
  modal: document.querySelector("#approval-modal") as HTMLElement,
  requestDetails: document.querySelector("#request-details") as HTMLElement,
  grantType: document.querySelector("#grant-type") as HTMLSelectElement,
  btnApprove: document.querySelector("#btn-approve") as HTMLButtonElement,
  btnDeny: document.querySelector("#btn-deny") as HTMLButtonElement,
};

async function refreshData() {
  try {
    // 1. Refresh Metrics
    const metricsResp: any = await invoke("send_rpc", { method: "metrics.get", params: {} });
    // Note: Result comes via event usually if we use a router, 
    // but here we just wait for the immediate success of 'sent'
    // Actually, I need to implement a response router in TS or just poll for now.
    // For v1, I'll just send the requests and let the event listener update the UI.
    await invoke("send_rpc", { method: "metrics.get", params: {} });
    await invoke("send_rpc", { method: "grants.list", params: {} });
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

(window as any).revokeGrant = async (id: string) => {
  await invoke("send_rpc", { method: "grant.revoke", params: { grant_id: id } });
};

async function handleRpcMessage(msg: any) {
  console.log("RPC Message:", msg);
  
  if (msg.method === "approval.required") {
    activeApprovalId = msg.params.approval_id;
    const req = msg.params.request;
    els.requestDetails.innerHTML = `
      <p><b>Agent:</b> ${req.agent_id}</p>
      <p><b>Capability:</b> <code>${req.capability}</code></p>
      <p><b>Purpose:</b> ${req.purpose}</p>
      <p><b>Scope:</b> <pre>${JSON.stringify(req.scope, null, 2)}</pre></p>
    `;
    els.modal.classList.remove("hidden");
  } else if (msg.method === "grant.updated") {
    await refreshData();
  } else if (msg.result) {
    // If it's a result of one of our queries
    if (typeof msg.result === "object" && "total_requests" in msg.result) {
      updateMetrics(msg.result);
      els.status.textContent = "Online";
      els.status.classList.add("online");
    } else if (Array.isArray(msg.result)) {
      updateGrants(msg.result);
    }
  }
}

window.addEventListener("DOMContentLoaded", async () => {
  // Listen for UDS messages via Rust bridge
  await listen("rpc-msg", (event) => {
    handleRpcMessage(event.payload);
  });

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
      els.modal.classList.add("hidden");
      activeApprovalId = null;
    }
  };

  els.btnDeny.onclick = async () => {
    if (activeApprovalId) {
      await invoke("send_rpc", {
        method: "grant.deny",
        params: { approval_id: activeApprovalId }
      });
      els.modal.classList.add("hidden");
      activeApprovalId = null;
    }
  };

  // Initial load
  await refreshData();
  // Keep metrics fresh
  setInterval(refreshData, 5000);
});
