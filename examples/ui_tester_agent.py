import asyncio
import json
import uuid
import os
import sys
import argparse
from datetime import datetime
from typing import Dict, Any, List
from core.control_plane.client import ControlPlaneClient
from core.models.models import CapabilityRequest, CapabilityType

class UITesterAgent:
    def __init__(self, socket_path: str = "/tmp/rudi.sock"):
        self.agent_id = f"tester-{uuid.uuid4().hex[:4]}"
        self.client = ControlPlaneClient(socket_path=socket_path)
        self.results = []
        self.test_persona_id = None
        self.test_project_id = None

    async def log(self, msg: str, success: bool = True):
        status = "✅" if success else "❌"
        line = f"{status} {msg}"
        print(line)
        self.results.append(line)
        # Broadcast to UI
        try:
            await self.client._call("system.broadcast_thought", {
                "agent_id": self.agent_id,
                "thought": line
            })
        except:
            pass # UI might not be listening yet

    async def run_tests(self):
        print(f"--- Starting R.U.D.I. System Verification ({self.agent_id}) ---")
        try:
            await self.client.connect()
        except Exception as e:
            print(f"CRITICAL: Could not connect to server: {e}")
            return

        # 1. Connection Test
        await self.log("Testing RPC Connection (Ping)...")
        ping = await self.client._call("system.ping", {})
        if ping == "pong":
            await self.log("Connection successful.")
        else:
            await self.log("Connection failed.", False)
            return

        # 2. Context Isolation: Persona Creation
        await self.log("Testing Persona Creation...")
        try:
            persona = await self.client._call("persona.create", {"name": f"Test-Persona-{self.agent_id}", "description": "Auto-test context"})
            self.test_persona_id = persona['id']
            await self.log(f"Persona created: {persona['name']} ({self.test_persona_id})")
        except Exception as e:
            await self.log(f"Persona creation failed: {e}", False)

        # 3. Context Isolation: Project Creation
        await self.log("Testing Project Creation...")
        try:
            project = await self.client._call("project.create", {"persona_id": self.test_persona_id, "name": "System Health Check"})
            self.test_project_id = project['id']
            await self.log(f"Project created: {project['name']} ({self.test_project_id})")
        except Exception as e:
            await self.log(f"Project creation failed: {e}", False)

        # 4. Model Search Test
        await self.log("Testing Model Search (HuggingFace)...")
        try:
            results = await self.client._call("llm.search_models", {"query": "Llama-3"})
            if "models" in results and len(results["models"]) > 0:
                await self.log(f"Search successful. Found {len(results['models'])} models.")
            else:
                await self.log("Search returned 0 results. Check network or huggingface-hub.", False)
        except Exception as e:
            await self.log(f"Model search failed: {e}", False)

        # 5. Local Model Listing
        await self.log("Testing Local Model Library listing...")
        try:
            locals = await self.client._call("llm.list_local_models", {})
            await self.log(f"Found {len(locals)} models on disk.")
        except Exception as e:
            await self.log(f"Local listing failed: {e}", False)

        # 6. Capability Workflow: FS Read
        await self.log("Testing Capability Workflow (FS Read)...")
        try:
            # We'll try to read /etc/hosts
            path = "/etc/hosts"
            req = CapabilityRequest(
                agent_id=self.agent_id,
                capability=CapabilityType.FILESYSTEM_READ,
                scope={"path": path},
                purpose="Self-Verification Test",
                project_id=self.test_project_id
            )
            # This will trigger a UI modal if not auto-approved
            await self.log(f"Requesting permission to read {path}. PLEASE CLICK APPROVE IN UI.")
            grant = await self.client.request_capability(req)
            
            if grant:
                await self.log(f"Permission GRANTED for {path}. Executing...")
                result = await self.client.execute(self.agent_id, "filesystem:read", {"path": path}, project_id=self.test_project_id)
                if "content" in result:
                    await self.log(f"Execution successful. Read {len(result['content'])} bytes.")
                else:
                    await self.log(f"Execution failed: {result}", False)
            else:
                await self.log("Permission DENIED by user. Skipping execution check.", False)
        except Exception as e:
            await self.log(f"Capability workflow failed: {e}", False)

        # 7. Chat Integration
        await self.log("Testing Chat Integration...")
        try:
            await self.client._call("chat.send", {"project_id": self.test_project_id, "content": "R.U.D.I., please confirm you can see this test message."})
            await self.log("Message sent to chat history. Check 'Interaction' tab.")
        except Exception as e:
            await self.log(f"Chat test failed: {e}", False)

        # 8. Cleanup
        await self.log("Cleaning up test context...")
        
        await self.log("--- Verification Suite Complete ---")
        
        # Send final report to chat
        summary = "\n".join(self.results)
        await self.client._call("chat.receive", {
            "project_id": self.test_project_id or "default",
            "role": "assistant",
            "content": f"### System Health Report\n{summary}"
        })

        await self.client.close()

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=str, nargs="?", default="default")
    parser.add_argument("--socket", type=str, default="/tmp/rudi.sock")
    args = parser.parse_args()
    
    tester = UITesterAgent(socket_path=args.socket)
    await tester.run_tests()

if __name__ == "__main__":
    asyncio.run(main())
