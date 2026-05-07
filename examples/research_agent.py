import asyncio
import os
import uuid
import json
import sys
from typing import Dict, Any, Optional

# Ensure project root is in path
sys.path.append(os.getcwd())

from core.models.models import CapabilityRequest, CapabilityType
from core.control_plane.client import ControlPlaneClient
from core.llm.factory import LLMFactory

SYSTEM_PROMPT = """
You are a Research Agent operating inside the R.U.D.I. secure environment.
Your goal is to fulfill user requests by gathering information.

When you need to perform an action (like reading a file), you must output a JSON command.
If you have gathered enough information, output your final answer directly.

COMMAND FORMAT:
{
  "thought": "Reasoning about why you need this action",
  "command": "request_capability",
  "capability": "filesystem:read",
  "scope": {"path": "/absolute/path/to/file"},
  "purpose": "Clear explanation for the human approver"
}

CAPABILITIES AVAILABLE:
- filesystem:read: Read text from a file.
- filesystem:write: Write text to a file.

Example Flow:
User: "Read /etc/hosts"
Agent: {"thought": "I need to read the hosts file.", "command": "request_capability", "capability": "filesystem:read", "scope": {"path": "/etc/hosts"}, "purpose": "User asked to see host configurations."}
R.U.D.I.: [Content of file]
Agent: "The hosts file contains..."
"""

class ResearchAgent:
    def __init__(self, agent_id: str, project_id: str = "default"):
        self.agent_id = agent_id
        self.project_id = project_id
        self.client = ControlPlaneClient()
        self.history = []

    async def run(self, task: str):
        print(f"--- Research Agent ({self.agent_id}) Starting Task: {task} ---")
        
        try:
            await self.client.connect()
        except Exception as e:
            print(f"ERROR: Could not connect to R.U.D.I. Server: {e}")
            return

        prompt = f"Task: {task}"
        
        while True:
            print("\n[Agent] Thinking...")
            response_text = await self.client.generate(
                prompt=prompt, 
                system_prompt=SYSTEM_PROMPT,
                temperature=0.2 # Lower for more consistent command output
            )
            
            try:
                # Attempt to parse as a command
                data = json.loads(response_text)
                
                # Broadcast thought to UI
                if "thought" in data:
                    await self.client._call("system.broadcast_thought", {
                        "agent_id": self.agent_id,
                        "thought": data["thought"]
                    })

                if data.get("command") == "request_capability":
                    print(f"[Agent] Decision: {data['thought']}")
                    print(f"[Agent] Requesting {data['capability']} for {data['scope']}")
                    
                    # 1. Request Capability
                    req = CapabilityRequest(
                        agent_id=self.agent_id,
                        capability=CapabilityType(data['capability']),
                        scope=data['scope'],
                        purpose=data['purpose'],
                        project_id=self.project_id
                    )
                    grant = await self.client.request_capability(req)
                    
                    if not grant:
                        print("[Agent] FAILED: Human denied request.")
                        prompt = "The human denied your request. Try another way or explain why you can't finish."
                        continue

                    # 2. Execute Action
                    print(f"[Agent] Grant received ({grant['id']}). Executing...")
                    result = await self.client.execute(self.agent_id, data['capability'], data['scope'])
                    
                    # 3. Feed result back to LLM
                    print("[Agent] Action successful. Feeding result back...")
                    prompt = f"Result of {data['capability']} on {data['scope']}:\n{result.get('content') or result.get('status')}\n\nContinue with the task."
                else:
                    # Final answer received
                    print(f"\n--- FINAL ANSWER ---\n{response_text}\n")
                    # Save to Semantic History
                    await self.client._call("history.add", {
                        "project_id": self.project_id,
                        "agent_id": self.agent_id,
                        "summary": response_text[:500] # Truncated summary
                    })
                    break
            except (json.JSONDecodeError, KeyError):
                # Final answer
                print(f"\n--- FINAL ANSWER ---\n{response_text}\n")
                await self.client._call("history.add", {
                    "project_id": self.project_id,
                    "agent_id": self.agent_id,
                    "summary": response_text[:500]
                })
                break
            except Exception as e:
                print(f"ERROR in agent loop: {e}")
                break

        await self.client.close()

async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("task", type=str, nargs="?", default="Tell me what localhost is mapped to in /etc/hosts")
    parser.add_argument("--project", type=str, default="default")
    args = parser.parse_args()
        
    agent = ResearchAgent(f"researcher-{uuid.uuid4().hex[:4]}", project_id=args.project)
    await agent.run(args.task)

if __name__ == "__main__":
    asyncio.run(main())
