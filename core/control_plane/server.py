import asyncio
import json
import os
import stat
import logging
import uuid
from typing import Dict, Any, Optional
from core.control_plane.manager import ControlPlaneManager
from core.models.models import CapabilityRequest, CapabilityType, GrantType
from adapters.platform_adapter import get_platform_adapter
from core.interfaces.plugin import CapabilityPlugin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rudi.server")

class JSONRPCError(Exception):
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data

class IPCUIHandler:
    def __init__(self, server: 'ControlPlaneServer'):
        self.server = server
        self.pending_approvals: Dict[str, asyncio.Future] = {}

    async def ask_approval(self, request: CapabilityRequest, timeout: int = 60) -> Any:
        if not self.server.ui_connection:
            logger.error("No UI registered for approval request.")
            return False

        approval_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self.pending_approvals[approval_id] = future

        # Send notification to UI
        notification = {
            "jsonrpc": "2.0",
            "method": "approval.required",
            "params": {
                "approval_id": approval_id,
                "request": request.model_dump(mode='json')
            }
        }
        self.server.ui_connection.write((json.dumps(notification) + "\n").encode())
        await self.server.ui_connection.drain()

        try:
            # Wait for user response
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Approval {approval_id} timed out.")
            return False
        finally:
            self.pending_approvals.pop(approval_id, None)

class ControlPlaneServer:
    def __init__(self, config: dict, socket_path: str = "/tmp/rudi.sock"):
        self.config = config
        self.manager = ControlPlaneManager(config)
        self.socket_path = socket_path
        self.ui_connection: Optional[asyncio.StreamWriter] = None
        self.adapters = get_platform_adapter(self.manager)
        self.ui_handler = IPCUIHandler(self)
        self.manager.ui_handler = self.ui_handler
        self.plugins: Dict[str, CapabilityPlugin] = {}

    def register_plugin(self, plugin: CapabilityPlugin):
        """Register a dynamic capability plugin."""
        self.plugins[plugin.capability_type] = plugin
        logger.info(f"Registered plugin: {plugin.capability_type}")

    async def start(self):
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)

        # Start Prometheus Metrics Server
        from core.control_plane.manager import PROMETHEUS_AVAILABLE
        if PROMETHEUS_AVAILABLE:
            metrics_port = self.config.get("metrics_port", 8000)
            try:
                from prometheus_client import start_http_server
                start_http_server(metrics_port)
                logger.info(f"Prometheus metrics available on port {metrics_port}")
            except Exception as e:
                logger.error(f"Failed to start Prometheus server: {e}")

        server = await asyncio.start_unix_server(self.handle_client, self.socket_path)
        os.chmod(self.socket_path, stat.S_IRUSR | stat.S_IWUSR)
        
        logger.info(f"R.U.D.I. Server started on {self.socket_path}")
        async with server:
            await server.serve_forever()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        try:
            while True:
                data = await reader.readline()
                if not data:
                    break

                try:
                    msg = json.loads(data.decode())
                    if "method" in msg:
                        response = await self.process_request(msg, writer)
                        if response:
                            writer.write((json.dumps(response) + "\n").encode())
                            await writer.drain()
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received from {addr}")
                except Exception as e:
                    logger.error(f"Error processing request from {addr}: {e}")
        except (ConnectionResetError, BrokenPipeError):
            logger.info(f"Connection lost from {addr}")
        finally:
            if self.ui_connection == writer:
                self.ui_connection = None
            writer.close()
            try:
                await writer.wait_closed()
            except:
                pass

    async def process_request(self, request: Dict[str, Any], writer: asyncio.StreamWriter) -> Optional[Dict[str, Any]]:
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        try:
            result = None
            if method == "system.ping":
                result = "pong"
            elif method == "system.register_ui":
                self.ui_connection = writer
                result = "UI Registered"
            elif method == "capability.request":
                result = await self.handle_capability_request(params)
            elif method == "capability.execute":
                result = await self.handle_capability_execute(params)
            elif method == "grant.approve":
                result = self.handle_grant_approve(params)
            elif method == "grant.deny":
                result = self.handle_grant_deny(params)
            elif method == "grants.list":
                result = [g.model_dump(mode='json') for g in self.manager.get_active_grants(params.get("agent_id"))]
            elif method == "metrics.get":
                result = self.manager.get_metrics()
            else:
                raise JSONRPCError(-32601, f"Method not found: {method}")

            return {"jsonrpc": "2.0", "result": result, "id": request_id}
        except JSONRPCError as e:
            return {"jsonrpc": "2.0", "error": {"code": e.code, "message": e.message, "data": e.data}, "id": request_id}

    async def broadcast_update(self):
        if self.ui_connection:
            notification = {
                "jsonrpc": "2.0",
                "method": "grant.updated",
                "params": {}
            }
            try:
                self.ui_connection.write((json.dumps(notification) + "\n").encode())
                await self.ui_connection.drain()
            except Exception as e:
                logger.error(f"Failed to broadcast update: {e}")
                self.ui_connection = None

    async def handle_capability_request(self, params: Dict[str, Any]) -> Any:
        req = CapabilityRequest(**params)
        grant = await self.manager.request_capability(req)
        return grant.model_dump(mode='json') if grant else None

    async def handle_capability_execute(self, params: Dict[str, Any]) -> Any:
        agent_id = params.get("agent_id")
        action = params.get("action")
        args = params.get("args", {})

        # 1. Check for Plugins
        if action in self.plugins:
            plugin = self.plugins[action]
            if not self.manager.validate_grant(agent_id, action, args):
                raise JSONRPCError(-32000, f"R.U.D.I. blocked {action}: No valid grant.")
            try:
                result = plugin.execute(agent_id, args)
                await self.broadcast_update()
                return result
            except Exception as e:
                raise JSONRPCError(-32603, f"Plugin execution error: {e}")

        # 2. Core capability logic
        try:
            cap_type = CapabilityType(action)
        except ValueError:
            raise JSONRPCError(-32602, f"Invalid action: {action}")

        # Execution logic - The adapters internally call manager.validate_grant()
        try:
            if cap_type in [CapabilityType.FILESYSTEM_READ, CapabilityType.FILESYSTEM_WRITE]:
                res = self._execute_fs(agent_id, action, args)
            elif cap_type == CapabilityType.NETWORK_CONNECT:
                res = self._execute_net(agent_id, action, args)
            elif cap_type == CapabilityType.PROCESS_EXECUTE:
                res = self._execute_proc(agent_id, action, args)
            else:
                raise JSONRPCError(-32601, f"Execution not implemented for: {action}")
            
            await self.broadcast_update()
            return res
        except PermissionError as e:
            raise JSONRPCError(-32000, str(e))
        except Exception as e:
            logger.error(f"Execution error: {e}")
            raise JSONRPCError(-32603, f"Internal execution error: {e}")

    def _execute_fs(self, agent_id: str, action: str, args: Dict[str, Any]) -> Any:
        fs = self.adapters["fs"]
        path = args.get("path")
        if action == CapabilityType.FILESYSTEM_READ:
            return {"content": fs.read_file(agent_id, path)}
        elif action == CapabilityType.FILESYSTEM_WRITE:
            fs.write_file(agent_id, path, args.get("content", ""))
            return {"status": "success"}

    def _execute_net(self, agent_id: str, action: str, args: Dict[str, Any]) -> Any:
        net = self.adapters["net"]
        success = net.connect(agent_id, args.get("host"), args.get("port"))
        if not success:
            raise JSONRPCError(-32000, f"R.U.D.I. blocked network connection to {args.get('host')}:{args.get('port')}")
        return {"success": success}

    def _execute_proc(self, agent_id: str, action: str, args: Dict[str, Any]) -> Any:
        proc = self.adapters["proc"]
        return proc.execute(agent_id, args.get("command"))

    def handle_grant_approve(self, params: Dict[str, Any]) -> bool:
        approval_id = params.get("approval_id")
        grant_type = GrantType(params.get("grant_type", "allow_once"))
        duration = params.get("duration", 0)
        
        if approval_id in self.ui_handler.pending_approvals:
            self.ui_handler.pending_approvals[approval_id].set_result((True, grant_type, duration))
            return True
        return False

    def handle_grant_deny(self, params: Dict[str, Any]) -> bool:
        approval_id = params.get("approval_id")
        if approval_id in self.ui_handler.pending_approvals:
            self.ui_handler.pending_approvals[approval_id].set_result(False)
            return True
        return False

def main():
    """Main entry point for the rudi-server console script."""
    from core.common.config import ConfigLoader
    config = ConfigLoader.load()
    server = ControlPlaneServer(config)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")

if __name__ == "__main__":
    main()
