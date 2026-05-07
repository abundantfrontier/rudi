import asyncio
import json
import uuid
from typing import Dict, Any, Optional, List
from core.models.models import CapabilityRequest, CapabilityType

class ControlPlaneClient:
    def __init__(self, socket_path: str = "/tmp/rudi.sock"):
        self.socket_path = socket_path
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.pending_requests: Dict[str, asyncio.Future] = {}

    async def connect(self):
        self.reader, self.writer = await asyncio.open_unix_connection(self.socket_path)
        asyncio.create_task(self._listen())

    async def _listen(self):
        while True:
            try:
                line = await self.reader.readline()
                if not line:
                    break
                
                response = json.loads(line.decode())
                request_id = response.get("id")
                
                if request_id in self.pending_requests:
                    future = self.pending_requests.pop(request_id)
                    if "error" in response:
                        future.set_exception(Exception(response["error"]["message"]))
                    else:
                        future.set_result(response.get("result"))
            except Exception as e:
                print(f"Client listen error: {e}")
                break

    async def _call(self, method: str, params: Dict[str, Any]) -> Any:
        if not self.writer:
            await self.connect()

        request_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self.pending_requests[request_id] = future

        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": request_id
        }
        
        self.writer.write((json.dumps(request) + "\n").encode())
        await self.writer.drain()
        
        return await future

    async def ping(self) -> str:
        return await self._call("system.ping", {})

    async def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None, 
        temperature: float = 0.7, 
        max_tokens: int = 1000, 
        json_mode: bool = False
    ) -> str:
        return await self._call("llm.generate", {
            "prompt": prompt,
            "system_prompt": system_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "json_mode": json_mode
        })

    async def preload_model(self, model: Optional[str] = None) -> Dict[str, Any]:
        return await self._call("llm.preload", {"model": model})

    async def unload_model(self) -> Dict[str, Any]:
        return await self._call("llm.unload", {})

    async def request_capability(self, request: CapabilityRequest) -> Optional[Dict[str, Any]]:
        # Use mode='json' to ensure datetime objects are serialized to strings
        return await self._call("capability.request", request.model_dump(mode='json'))

    async def execute(self, agent_id: str, action: str, args: Dict[str, Any], project_id: Optional[str] = None) -> Any:
        return await self._call("capability.execute", {
            "agent_id": agent_id,
            "action": action,
            "args": args,
            "project_id": project_id
        })

    async def http_request(
        self, 
        agent_id: str, 
        method: str, 
        url: str, 
        headers: Optional[Dict[str, str]] = None, 
        body: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Perform a mediated HTTP request via the Control Plane.
        """
        return await self.execute(agent_id, "network:http", {
            "method": method,
            "url": url,
            "headers": headers or {},
            "body": body
        })

    async def list_grants(self, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._call("grants.list", {"agent_id": agent_id})

    async def get_metrics(self) -> Dict[str, Any]:
        return await self._call("metrics.get", {})

    async def close(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
