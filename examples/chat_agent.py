import asyncio
import json
import os
import uuid
import sys
import argparse
import re
from typing import List, Dict, Any, Optional
from core.control_plane.client import ControlPlaneClient
from core.models.models import CapabilityRequest, CapabilityType, ChatMessage

SYSTEM_PROMPT = """You are R.U.D.I., a context-aware AI assistant.
You are helping the user manage their system and projects.

CAPABILITIES:
- filesystem:read (path)
- filesystem:write (path, content)
- network:http (url, method, body, headers)
- process:execute (command)

CONVENTIONS:
1. To use a capability, output a JSON command: {"command": "request_capability", "capability": "filesystem:read", "scope": {"path": "/etc/hosts"}, "purpose": "I need to check the host mappings.", "thought": "The user asked for host info."}
2. You can mix human text and JSON.
3. If you have enough information, just respond to the user in plain text.
4. You are isolated within a specific PROJECT.
"""

class ChatAgent:
    def __init__(self, project_id: str, socket_path: str = "/tmp/rudi.sock"):
        self.agent_id = f"chat-agent-{uuid.uuid4().hex[:4]}"
        self.project_id = project_id
        self.client = ControlPlaneClient(socket_path=socket_path)

    def extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract the first valid JSON block from text."""
        try:
            # Look for {...}
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except:
            pass
        return None

    async def run(self):
        try:
            await self.client.connect()
        except Exception as e:
            print(f"ERROR: Could not connect to server: {e}")
            return

        try:
            # 1. Fetch History
            print(f"[ChatAgent] Fetching history for project {self.project_id}...")
            history: List[Dict[str, Any]] = await self.client._call("chat.history", {"project_id": self.project_id})
            
            if not history:
                print("[ChatAgent] No history found. Exiting.")
                return

            messages = [{"role": m['role'], "content": m['content']} for m in history]
            
            # 2. Generate Initial Response
            print(f"[ChatAgent] Generating response for project {self.project_id}...")
            response_text = await self.client.generate(
                prompt=messages,
                system_prompt=SYSTEM_PROMPT,
                temperature=0.7
            )
            print(f"[ChatAgent] LLM Output: {response_text}")

            # 3. Command Extraction & Execution
            cmd_data = self.extract_json(response_text)
            
            if cmd_data and cmd_data.get("command") == "request_capability":
                # Handle generic mappings
                cap = cmd_data['capability']
                if cap == "filesystem": cap = "filesystem:read" # Default to read
                if cap == "network": cap = "network:http"
                
                print(f"[ChatAgent] TRIGGERING POPUP: {cap}...")
                
                req = CapabilityRequest(
                    agent_id=self.agent_id,
                    capability=CapabilityType(cap),
                    scope=cmd_data['scope'],
                    purpose=cmd_data['purpose'],
                    project_id=self.project_id
                )
                
                # This will wait for the UI 'Approve' click
                grant = await self.client.request_capability(req)
                
                if grant:
                    print(f"[ChatAgent] Access GRANTED. Executing {cap}...")
                    try:
                        result = await self.client.execute(self.agent_id, cap, cmd_data['scope'], project_id=self.project_id)
                        
                        # 4. Feed back to LLM for final summary
                        messages.append({"role": "assistant", "content": response_text})
                        messages.append({"role": "user", "content": f"RESULT OF {cap}: {result}\nNow provide the final response to the user."})
                        
                        print("[ChatAgent] Generating final summary...")
                        response_text = await self.client.generate(prompt=messages, system_prompt=SYSTEM_PROMPT)
                    except Exception as e:
                        response_text = f"I was granted permission, but the action failed: {e}"
                else:
                    print("[ChatAgent] Access DENIED by user.")
                    response_text = "I'm sorry, I cannot complete that task because the permission request was denied."

            # 5. Send Final bubble back to UI
            await self.client._call("chat.receive", {
                "project_id": self.project_id,
                "role": "assistant",
                "content": response_text,
                "metadata": {"agent_id": self.agent_id}
            })

        except Exception as e:
            print(f"ERROR in ChatAgent loop: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.client.close()

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=str, required=True)
    parser.add_argument("--socket", type=str, default="/tmp/rudi.sock")
    args = parser.parse_args()
    
    agent = ChatAgent(args.project, socket_path=args.socket)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
