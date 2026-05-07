use tauri::{AppHandle, Emitter, Manager, Runtime};
use tauri_plugin_shell::ShellExt;
use tokio::net::UnixStream;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::Mutex;

#[derive(Serialize, Deserialize, Debug, Clone)]
struct JsonRpcRequest {
    jsonrpc: String,
    method: String,
    params: serde_json::Value,
    id: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
struct JsonRpcResponse {
    jsonrpc: String,
    result: Option<serde_json::Value>,
    error: Option<serde_json::Value>,
    id: Option<serde_json::Value>,
}

struct AppState {
    uds_writer: Arc<Mutex<Option<tokio::io::WriteHalf<UnixStream>>>>,
}

#[tauri::command]
async fn send_rpc(
    state: tauri::State<'_, AppState>,
    method: String,
    params: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let mut writer_guard = state.uds_writer.lock().await;
    if let Some(writer) = writer_guard.as_mut() {
        let id = uuid::Uuid::new_v4().to_string();
        let request = JsonRpcRequest {
            jsonrpc: "2.0".to_string(),
            method,
            params,
            id: Some(serde_json::Value::String(id.clone())),
        };
        
        let payload = format!("{}\n", serde_json::to_string(&request).unwrap());
        writer.write_all(payload.as_bytes()).await.map_err(|e| e.to_string())?;
        writer.flush().await.map_err(|e| e.to_string())?;
        
        // Note: For simplicity in this bridge, we aren't waiting for the SPECIFIC response ID here.
        // In a real app, we'd use a response router. For now, we'll return a placeholder
        // or refactor to support async responses properly.
        // Actually, let's keep it simple: the frontend will receive results via events 
        // if they are async, or we can implement a basic wait loop.
        
        Ok(serde_json::json!({ "status": "sent", "id": id }))
    } else {
        Err("UDS connection not established".to_string())
    }
}

async fn start_uds_listener<R: Runtime>(app: AppHandle<R>, uds_writer: Arc<Mutex<Option<tokio::io::WriteHalf<UnixStream>>>>) {
    let socket_path = "/tmp/rudi.sock";
    
    // Wait for sidecar to start and create socket
    let mut retry_count = 0;
    let stream = loop {
        match UnixStream::connect(socket_path).await {
            Ok(s) => break s,
            Err(_) if retry_count < 10 => {
                tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;
                retry_count += 1;
            }
            Err(e) => {
                eprintln!("Failed to connect to UDS: {}", e);
                return;
            }
        }
    };

    let (reader, writer) = tokio::io::split(stream);
    *uds_writer.lock().await = Some(writer);
    
    // Register UI with server immediately
    let register_msg = serde_json::json!({
        "jsonrpc": "2.0",
        "method": "system.register_ui",
        "params": {},
        "id": "init-reg"
    });
    let mut writer_lock = uds_writer.lock().await;
    if let Some(w) = writer_lock.as_mut() {
        let _ = w.write_all(format!("{}\n", register_msg).as_bytes()).await;
        let _ = w.flush().await;
    }
    drop(writer_lock);

    let mut lines = BufReader::new(reader).lines();
    while let Ok(Some(line)) = lines.next_line().await {
        if let Ok(msg) = serde_json::from_str::<serde_json::Value>(&line) {
            // Forward everything to frontend
            let _ = app.emit("rpc-msg", msg);
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let uds_writer = Arc::new(Mutex::new(None));
    let uds_writer_clone = uds_writer.clone();

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .manage(AppState { uds_writer })
        .setup(|app| {
            // 1. Spawn Sidecar
            let sidecar = app.shell().sidecar("rudi-server").unwrap();
            let (_rx, _child) = sidecar.spawn().expect("Failed to spawn sidecar");
            
            // 2. Start UDS Bridge
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                start_uds_listener(handle, uds_writer_clone).await;
            });
            
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![send_rpc])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
