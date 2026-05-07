import asyncio
import json
import os
import stat
import logging
import uuid
from datetime import datetime, timedelta
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
        # Load tasks from storage
        from core.models.models import DelegatedTask
        self.tasks: Dict[str, DelegatedTask] = {t.id: t for t in self.manager.storage.load_all_tasks()}

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
        # Start background scheduler
        asyncio.create_task(self.scheduler_loop())
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
            elif method == "system.pull_model":
                result = await self.handle_pull_model(params)
            elif method == "system.broadcast_thought":
                await self.broadcast_thought(params)
                result = {"status": "broadcasted"}
            elif method == "llm.preload":
                result = await self.handle_llm_preload(params)
            elif method == "llm.unload":
                result = self.handle_llm_unload()
            elif method == "llm.generate":
                result = await self.handle_llm_generate(params)
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
            elif method == "persona.create":
                p = self.manager.create_persona(params.get("name"), params.get("description"))
                result = p.model_dump(mode='json')
            elif method == "persona.list":
                result = [p.model_dump(mode='json') for p in self.manager.list_personas()]
            elif method == "project.create":
                p = self.manager.create_project(params.get("persona_id"), params.get("name"), params.get("description"))
                result = p.model_dump(mode='json')
            elif method == "project.list":
                result = [p.model_dump(mode='json') for p in self.manager.list_projects(params.get("persona_id"))]
            elif method == "history.add":
                self.manager.add_history_summary(
                    params.get("project_id"), params.get("agent_id"), 
                    params.get("summary"), params.get("metadata", {})
                )
                result = {"status": "success"}
            elif method == "history.query":
                result = [s.model_dump(mode='json') for s in self.manager.query_history(params.get("project_id"), params.get("query"))]
            elif method == "task.list":
                project_id = params.get("project_id")
                result = [t.model_dump(mode='json') for t in self.tasks.values() if not project_id or t.project_id == project_id]
            elif method == "task.save":
                result = await self.handle_task_save(params)
            elif method == "task.delete":
                result = self.handle_task_delete(params)
            elif method == "task.run":
                result = await self.handle_task_run(params)
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

    async def broadcast_thought(self, params: Dict[str, Any]):
        if self.ui_connection:
            notification = {
                "jsonrpc": "2.0",
                "method": "llm.thought",
                "params": params
            }
            try:
                self.ui_connection.write((json.dumps(notification) + "\n").encode())
                await self.ui_connection.drain()
            except Exception as e:
                logger.error(f"Failed to broadcast thought: {e}")

    async def handle_capability_request(self, params: Dict[str, Any]) -> Any:
        req = CapabilityRequest(**params)
        grant = await self.manager.request_capability(req)
        return grant.model_dump(mode='json') if grant else None

    async def handle_pull_model(self, params: Dict[str, Any]) -> Any:
        model_path = params.get("model")
        if hasattr(self.llm_provider, "download_model"):
            success = await self.llm_provider.download_model(model_path)
            return {"status": "success" if success else "failed"}
        else:
            raise JSONRPCError(-32601, "Model downloading not supported by current LLM provider.")

    async def handle_llm_preload(self, params: Dict[str, Any]) -> Any:
        model_path = params.get("model")
        if model_path:
            self.llm_provider = LLMFactory.get_provider({**self.config, "llm": {"model": model_path}})

        try:
            await asyncio.to_thread(self.llm_provider._ensure_loaded)
            return {"status": "success", "message": "Model loaded into RAM."}
        except Exception as e:
            raise JSONRPCError(-32603, f"Failed to preload model: {e}")

    def handle_llm_unload(self) -> Any:
        if hasattr(self.llm_provider, "model"):
            self.llm_provider.model = None
            self.llm_provider.tokenizer = None
            import gc
            gc.collect()
            logger.info("Model unloaded from RAM.")
            return {"status": "success", "message": "Model unloaded."}
        return {"status": "skipped", "message": "Provider does not support unloading."}

    async def handle_llm_generate(self, params: Dict[str, Any]) -> str:
        try:
            return await self.llm_provider.generate(
                prompt=params.get("prompt"),
                system_prompt=params.get("system_prompt"),
                temperature=params.get("temperature", 0.7),
                max_tokens=params.get("max_tokens", 1000),
                json_mode=params.get("json_mode", False)
            )
        except Exception as e:
            raise JSONRPCError(-32603, f"Generation failed: {e}")

    async def handle_capability_request(self, params: Dict[str, Any]) -> Any:
        try:
            req = CapabilityRequest(**params)
            grant = await self.manager.request_capability(req)
            await self.broadcast_update()
            return grant.model_dump(mode='json') if grant else None
        except Exception as e:
            raise JSONRPCError(-32602, f"Invalid request params: {e}")

    async def handle_task_save(self, params: Dict[str, Any]) -> Any:
        try:
            from core.models.models import DelegatedTask
            task = DelegatedTask(**params)
            # Update next_run_at if needed
            if task.schedule_type == "once" and task.target_time:
                task.next_run_at = task.target_time
            elif task.schedule_type == "repeat" and task.interval_seconds:
                if not task.next_run_at:
                    task.next_run_at = datetime.now() + timedelta(seconds=task.interval_seconds)
            
            self.tasks[task.id] = task
            self.manager.storage.save_task(task)
            await self.broadcast_update()
            return task.model_dump(mode='json')
        except Exception as e:
            raise JSONRPCError(-32602, f"Invalid task params: {e}")

    def handle_task_delete(self, params: Dict[str, Any]) -> bool:
        task_id = params.get("task_id")
        if task_id in self.tasks:
            del self.tasks[task_id]
            self.manager.storage.delete_task(task_id)
            asyncio.create_task(self.broadcast_update())
            return True
        return False

    async def handle_task_run(self, params: Dict[str, Any]) -> bool:
        task_id = params.get("task_id")
        task = self.tasks.get(task_id)
        if task:
            await self.trigger_task(task)
            return True
        return False

    async def trigger_task(self, task: 'DelegatedTask'):
        logger.info(f"Triggering task: {task.label} ({task.instruction})")
        # Spawn agent subprocess
        import subprocess
        import sys
        try:
            # We use sys.executable to ensure we use the same python interpreter
            cmd = [sys.executable, "examples/research_agent.py", task.instruction, "--project", task.project_id]
            # Run in background
            subprocess.Popen(cmd, env={**os.environ, "PYTHONPATH": os.getcwd()})
            
            # Update last run
            task.last_run_at = datetime.now()
            if task.schedule_type == "repeat" and task.interval_seconds:
                task.next_run_at = datetime.now() + timedelta(seconds=task.interval_seconds)
            elif task.schedule_type == "once":
                task.next_run_at = None # Don't run again
                
            self.manager.storage.save_task(task)
            await self.broadcast_update()
        except Exception as e:
            logger.error(f"Failed to trigger task {task.label}: {e}")

    async def scheduler_loop(self):
        logger.info("Background scheduler started.")
        while True:
            await asyncio.sleep(5)
            now = datetime.now()
            for task in list(self.tasks.values()):
                if task.next_run_at and now >= task.next_run_at:
                    await self.trigger_task(task)

    async def handle_capability_execute(self, params: Dict[str, Any]) -> Any:
        agent_id = params.get("agent_id")
        action = params.get("action")
        project_id = params.get("project_id")
        args = params.get("args", {})

        # 1. Check for Plugins
        if action in self.plugins:
            plugin = self.plugins[action]
            if not self.manager.validate_grant(agent_id, action, args, project_id=project_id):
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

        # Execution logic - The handlers/adapters internally call manager.validate_grant()
        try:
            if cap_type in [CapabilityType.FILESYSTEM_READ, CapabilityType.FILESYSTEM_WRITE]:
                res = self._execute_fs(agent_id, action, args, project_id=project_id)
            elif cap_type == CapabilityType.NETWORK_CONNECT:
                res = self._execute_net(agent_id, action, args, project_id=project_id)
            elif cap_type == CapabilityType.NETWORK_HTTP:
                res = await self._execute_http(agent_id, action, args, project_id=project_id)
            elif cap_type == CapabilityType.PROCESS_EXECUTE:
                res = self._execute_proc(agent_id, action, args, project_id=project_id)
            else:
                raise JSONRPCError(-32601, f"Execution not implemented for: {action}")
            
            await self.broadcast_update()
            return res
        except PermissionError as e:
            raise JSONRPCError(-32000, str(e))
        except Exception as e:
            logger.error(f"Execution error: {e}")
            raise JSONRPCError(-32603, f"Internal execution error: {e}")

    def _execute_fs(self, agent_id: str, action: str, args: Dict[str, Any], project_id: Optional[str] = None) -> Any:
        fs = self.adapters["fs"]
        path = args.get("path")
        if action == CapabilityType.FILESYSTEM_READ:
            return {"content": fs.read_file(agent_id, path, project_id=project_id)}
        elif action == CapabilityType.FILESYSTEM_WRITE:
            fs.write_file(agent_id, path, args.get("content", ""), project_id=project_id)
            return {"status": "success"}

    def _execute_net(self, agent_id: str, action: str, args: Dict[str, Any], project_id: Optional[str] = None) -> Any:
        net = self.adapters["net"]
        success = net.connect(agent_id, args.get("host"), args.get("port"), project_id=project_id)
        if not success:
            raise JSONRPCError(-32000, f"R.U.D.I. blocked network connection to {args.get('host')}:{args.get('port')}")
        return {"success": success}


    def _execute_proc(self, agent_id: str, action: str, args: Dict[str, Any], project_id: Optional[str] = None) -> Any:
        proc = self.adapters["proc"]
        return proc.execute(agent_id, args.get("command"))

    async def _execute_http(self, agent_id: str, action: str, args: Dict[str, Any], project_id: Optional[str] = None) -> Any:
        url = args.get("url")
        method = args.get("method", "GET").upper()
        headers = args.get("headers", {})
        body = args.get("body")

        if not url:
            raise JSONRPCError(-32602, "Missing 'url' argument")

        # Manager validation (using args as scope)
        if not self.manager.validate_grant(agent_id, action, args, project_id=project_id):
            raise JSONRPCError(-32000, f"R.U.D.I. blocked HTTP {method} to {url}: No valid grant.")

        import httpx
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    content=body,
                    follow_redirects=True
                )
                
                try:
                    content = resp.json()
                except:
                    content = resp.text

                return {
                    "status_code": resp.status_code,
                    "headers": dict(resp.headers),
                    "content": content
                }
        except Exception as e:
            logger.error(f"HTTP request failed: {e}")
            raise JSONRPCError(-32603, f"HTTP request failed: {e}")

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
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="R.U.D.I. Control Plane Server")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Run command (default)
    run_parser = subparsers.add_parser("run", help="Start the Control Plane server")
    
    # Pull command
    pull_parser = subparsers.add_parser("pull", help="Download/cache an LLM model")
    pull_parser.add_argument("model", type=str, help="The model ID to pull (e.g. mlx-community/Meta-Llama-3-8B-Instruct-4bit)")

    args = parser.parse_args()

    from core.common.config import ConfigLoader
    config = ConfigLoader.load()
    
    if args.command == "pull":
        from core.llm.factory import LLMFactory
        provider = LLMFactory.get_provider(config)
        if hasattr(provider, "download_model"):
            print(f"Pulling model: {args.model}...")
            success = asyncio.run(provider.download_model(args.model))
            if success:
                print("Model pulled successfully.")
            else:
                print("Failed to pull model.")
                sys.exit(1)
        else:
            print("Error: Current LLM provider does not support model pulling.")
            sys.exit(1)
        return

    # Default to 'run'
    server = ControlPlaneServer(config)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")

if __name__ == "__main__":
    main()
