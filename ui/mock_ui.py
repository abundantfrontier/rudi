import asyncio
import json
import os

async def run_mock_ui():
    socket_path = "/tmp/rudi.sock"
    reader, writer = await asyncio.open_unix_connection(socket_path)
    
    # 1. Register UI
    register_msg = {
        "jsonrpc": "2.0",
        "method": "system.register_ui",
        "params": {},
        "id": "reg-1"
    }
    writer.write((json.dumps(register_msg) + "\n").encode())
    await writer.drain()
    
    print("Mock UI: Registered with server.")
    
    while True:
        line = await reader.readline()
        if not line:
            break
        
        msg = json.loads(line.decode())
        if msg.get("method") == "approval.required":
            params = msg["params"]
            approval_id = params["approval_id"]
            request = params["request"]
            
            print(f"Mock UI: Received approval request for {request['capability']} by {request['agent_id']}")
            print(f"Mock UI: Auto-approving...")
            
            approve_msg = {
                "jsonrpc": "2.0",
                "method": "grant.approve",
                "params": {
                    "approval_id": approval_id,
                    "grant_type": "allow_once",
                    "duration": 0
                },
                "id": f"app-{approval_id[:4]}"
            }
            writer.write((json.dumps(approve_msg) + "\n").encode())
            await writer.drain()

if __name__ == "__main__":
    asyncio.run(run_mock_ui())
