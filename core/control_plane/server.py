import signal
import asyncio
import json
import os
import stat
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from core.control_plane.manager import ControlPlaneManager
from core.models.models import CapabilityRequest, CapabilityType, GrantType, ChatMessage
from adapters.platform_adapter import get_platform_adapter
from core.interfaces.plugin import CapabilityPlugin

# Configure logging to both file and console
log_file = "server_debug.log"
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(file_handler)

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
        # LLM Provider
        from core.llm.factory import LLMFactory
        self.llm_provider = LLMFactory.get_provider(config)
        # Load tasks from storage
        from core.models.models import DelegatedTask
        self.tasks: Dict[str, DelegatedTask] = {t.id: t for t in self.manager.storage.load_all_tasks()}
        
        # Shutdown logic
        self.shutdown_event = asyncio.Event()
        self.parent_pid = os.getppid()

        # Loading state tracking
        self.loading_status = {"status": "none", "model": None, "step": "", "percent": 0, "current": 0, "total": 0}

    def register_plugin(self, plugin: CapabilityPlugin):
        """Register a dynamic capability plugin."""
        self.plugins[plugin.capability_type] = plugin
        logger.info(f"Registered plugin: {plugin.capability_type}")

    async def parent_watchdog(self):
        """Monitor parent process and shutdown if it dies."""
        while not self.shutdown_event.is_set():
            try:
                # If current parent is not the one we started with, or is 1 (init)
                if os.getppid() != self.parent_pid:
                    logger.warning("Parent process disappeared. Shutting down...")
                    self.shutdown_event.set()
                    break
            except: pass
            await asyncio.sleep(2)

    async def start(self):
        logger.info(f"Starting R.U.D.I. Server with config: {self.config}")
        logger.info(f"Using socket path: {os.path.abspath(self.socket_path)}")
        
        # Register signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        try:
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda: self.shutdown_event.set())
        except NotImplementedError:
            pass # Windows

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
        # Start background tasks
        asyncio.create_task(self.scheduler_loop())
        asyncio.create_task(self.parent_watchdog())
        
        # Phase 12: Autoload last model
        last_model = self.manager.get_setting("last_loaded_model")
        if last_model:
            logger.info(f"Autoloading last model: {last_model}")
            # Use a slight delay to ensure everything is initialized
            async def delayed_autoload():
                await asyncio.sleep(1)
                await self.handle_llm_preload({"model": last_model})
            asyncio.create_task(delayed_autoload())
        
        async with server:
            # Wait until shutdown is triggered
            await self.shutdown_event.wait()
            logger.info("Shutdown signal received. Closing server...")
            
        # Cleanup
        self.manager.shutdown()
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
        logger.info("Server exited gracefully.")

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

        logger.info(f"RPC Request: {method} (id={request_id})")

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
            elif method == "llm.search_models":
                query = params.get("query", "")
                logger.info(f"LLM search request received for: '{query}'")
                models = await asyncio.to_thread(self.llm_provider.search_models, query)
                logger.info(f"LLM search returned {len(models)} models.")
                result = {"models": models}
            elif method == "llm.list_local_models":
                result = await asyncio.to_thread(self.llm_provider.list_local_models)
            elif method == "llm.status":
                result = self.loading_status
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
            elif method == "chat.history":
                msgs = self.manager.get_chat_history(params.get("project_id"), params.get("limit", 100))
                result = [m.model_dump(mode='json') for m in msgs]
            elif method == "chat.send":
                result = await self.handle_chat_send(params)
            elif method == "chat.receive":
                result = await self.handle_chat_receive(params)
            elif method == "task.list":
                project_id = params.get("project_id")
                # Show tasks for this project OR global tasks (project_id is None)
                result = [t.model_dump(mode='json') for t in self.tasks.values() if not project_id or t.project_id == project_id or t.project_id is None]
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
        except Exception as e:
            logger.error(f"Unhandled error processing request {method}: {e}", exc_info=True)
            return {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}, "id": request_id}

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

    async def broadcast_download_progress(self, model_id: str, percent: int, error: Optional[str] = None, current: int = 0, total: int = 0):
        if self.ui_connection:
            notification = {
                "jsonrpc": "2.0",
                "method": "llm.download_progress",
                "params": {"model_id": model_id, "percent": percent, "error": error, "current": current, "total": total}
            }
            try:
                self.ui_connection.write((json.dumps(notification) + "\n").encode())
                await self.ui_connection.drain()
            except Exception:
                pass

    async def broadcast_load_progress(self, step: str, percent: int, current: int = 0, total: int = 0):
        if self.ui_connection:
            notification = {
                "jsonrpc": "2.0",
                "method": "llm.load_progress",
                "params": {"step": step, "percent": percent, "current": current, "total": total}
            }
            try:
                self.ui_connection.write((json.dumps(notification) + "\n").encode())
                await self.ui_connection.drain()
            except Exception:
                pass

    async def broadcast_chat_message(self, msg: ChatMessage):
        if self.ui_connection:
            notification = {
                "jsonrpc": "2.0",
                "method": "chat.message",
                "params": msg.model_dump(mode='json')
            }
            try:
                self.ui_connection.write((json.dumps(notification) + "\n").encode())
                await self.ui_connection.drain()
            except Exception:
                pass

    async def handle_capability_request(self, params: Dict[str, Any]) -> Any:
        try:
            req = CapabilityRequest(**params)
            grant = await self.manager.request_capability(req)
            await self.broadcast_update()
            return grant.model_dump(mode='json') if grant else None
        except Exception as e:
            raise JSONRPCError(-32602, f"Invalid request params: {e}")

    async def handle_pull_model(self, params: Dict[str, Any]) -> Any:
        model_path = params.get("model")
        logger.info(f"Pull model request for: {model_path}")
        if not model_path:
            raise JSONRPCError(-32602, "Missing 'model' parameter")

        if hasattr(self.llm_provider, "download_model"):
            # Offload blocking download to a thread to keep the event loop free
            loop = asyncio.get_running_loop()
            
            def sync_callback(mid, p, err=None, cur=0, tot=0):
                # Thread-safe broadcast
                asyncio.run_coroutine_threadsafe(
                    self.broadcast_download_progress(mid, p, err, cur, tot), 
                    loop
                )

            # Start in background
            async def background_pull():
                try:
                    await asyncio.to_thread(self.llm_provider.download_model, model_path, progress_callback=sync_callback)
                    await self.broadcast_update()
                except Exception as e:
                    logger.error(f"Background pull failed: {e}")

            asyncio.create_task(background_pull())
            return {"status": "started", "message": f"Downloading {model_path} in background."}
        else:
            raise JSONRPCError(-32601, "Model downloading not supported by current LLM provider.")

    async def handle_llm_preload(self, params: Dict[str, Any]) -> Any:
        model_path = params.get("model")
        if model_path:
            from core.llm.factory import LLMFactory
            self.llm_provider = LLMFactory.get_provider({**self.config, "llm": {"model": model_path}})
        
        # Tracking for llm.status
        self.loading_status["model"] = model_path or self.llm_provider.model_path
        self.loading_status["status"] = "loading"

        try:
            def sync_callback(step, p, err=None, cur=0, tot=0):
                try:
                    loop = asyncio.get_running_loop()
                    asyncio.run_coroutine_threadsafe(
                        self.broadcast_load_progress(step, p, cur, tot), 
                        loop
                    )
                except Exception:
                    pass

            await asyncio.to_thread(self.llm_provider._ensure_loaded, progress_callback=sync_callback)
            
            # Persist last loaded model for autoload
            self.manager.set_setting("last_loaded_model", self.loading_status["model"])
            self.loading_status["status"] = "loaded"
            
            return {"status": "success", "message": "Model loaded into RAM."}
        except Exception as e:
            self.loading_status["status"] = "error"
            raise JSONRPCError(-32603, f"Failed to preload model: {e}")

    def handle_llm_unload(self) -> Any:
        if hasattr(self.llm_provider, "model"):
            self.llm_provider.model = None
            self.llm_provider.tokenizer = None
            import gc
            gc.collect()
            logger.info("Model unloaded from RAM.")
            self.loading_status = {"status": "none", "model": None, "step": "", "percent": 0, "current": 0, "total": 0}
            return {"status": "success", "message": "Model unloaded."}
        return {"status": "skipped", "message": "Provider does not support unloading."}

    async def handle_chat_send(self, params: Dict[str, Any]) -> Any:
        from core.models.models import ChatMessage
        project_id = params.get("project_id")
        content = params.get("content")
        
        msg = ChatMessage(project_id=project_id, role="user", content=content)
        self.manager.save_chat_message(msg)
        
        # Broadcast user message so it appears in UI instantly
        await self.broadcast_chat_message(msg)
        
        # Trigger ChatAgent in background
        asyncio.create_task(self.trigger_chat_agent(project_id))
        
        return msg.model_dump(mode='json')

    async def handle_chat_receive(self, params: Dict[str, Any]) -> Any:
        from core.models.models import ChatMessage
        msg = ChatMessage(**params)
        self.manager.save_chat_message(msg)
        await self.broadcast_chat_message(msg)
        return {"status": "received"}

    async def trigger_chat_agent(self, project_id: str):
        import subprocess
        import sys
        try:
            # Find project root robustly
            def find_root(start_dir):
                curr = os.path.abspath(start_dir)
                while curr != "/":
                    if os.path.exists(os.path.join(curr, "rudi-spec.md")):
                        return curr
                    curr = os.path.dirname(curr)
                return os.path.abspath(".")

            project_root = find_root(os.path.dirname(__file__))
            agent_script = os.path.join(project_root, "examples", "chat_agent.py")
            
            cmd = [sys.executable, agent_script, "--project", project_id, "--socket", self.socket_path]
            logger.info(f"Spawning chat agent: {' '.join(cmd)}")
            subprocess.Popen(cmd, env={**os.environ, "PYTHONPATH": project_root})
        except Exception as e:
            logger.error(f"Failed to trigger chat agent: {e}")

    async def handle_llm_generate(self, params: Dict[str, Any]) -> str:
        try:
            # Normalize 'temp' vs 'temperature'
            temp = params.get("temperature", params.get("temp", 0.7))
            return await self.llm_provider.generate(
                prompt=params.get("prompt"),
                system_prompt=params.get("system_prompt"),
                temperature=temp,
                max_tokens=params.get("max_tokens", 1000),
                json_mode=params.get("json_mode", False)
            )
        except Exception as e:
            raise JSONRPCError(-32603, f"Generation failed: {e}")

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
            return {"status": "success", "task_id": task.id}
        except Exception as e:
            raise JSONRPCError(-32602, f"Invalid task params: {e}")

    def handle_task_delete(self, params: Dict[str, Any]) -> Any:
        task_id = params.get("task_id")
        if task_id in self.tasks:
            del self.tasks[task_id]
            self.manager.storage.delete_task(task_id)
            return {"status": "success"}
        return {"status": "not_found"}

    async def handle_task_run(self, params: Dict[str, Any]) -> Any:
        task_id = params.get("task_id")
        project_id = params.get("project_id")
        if task_id in self.tasks:
            task = self.tasks[task_id]
            # Override project if provided by UI
            if project_id:
                task.project_id = project_id
            await self.trigger_task(task)
            return {"status": "triggered"}
        return {"status": "not_found"}

    async def trigger_task(self, task: 'DelegatedTask'):
        logger.info(f"Triggering task: {task.label} ({task.instruction})")
        # Spawn agent subprocess
        import subprocess
        import sys
        try:
            # Find project root robustly
            def find_root(start_dir):
                curr = os.path.abspath(start_dir)
                while curr != "/":
                    if os.path.exists(os.path.join(curr, "rudi-spec.md")):
                        return curr
                    curr = os.path.dirname(curr)
                return os.path.abspath(".")

            project_root = find_root(os.path.dirname(__file__))
            
            # Determine which agent to spawn
            agent_script = os.path.join(project_root, "examples", "research_agent.py")
            if "Self-Test" in task.label:
                agent_script = os.path.join(project_root, "examples", "ui_tester_agent.py")

            cmd = [sys.executable, agent_script, "--project", task.project_id or "default", "--socket", self.socket_path]
            if "research_agent.py" in agent_script:
                cmd.insert(2, task.instruction) # Insert instruction for research agent
            
            logger.info(f"Spawning agent: {' '.join(cmd)}")
            subprocess.Popen(cmd, env={**os.environ, "PYTHONPATH": project_root})
            
            # Update last run
            task.last_run_at = datetime.now()
            if task.schedule_type == "repeat" and task.interval_seconds:
                task.next_run_at = datetime.now() + timedelta(seconds=task.interval_seconds)
            elif task.schedule_type == "once":
                task.next_run_at = None # Don't run again

            self.manager.storage.save_task(task)
        except Exception as e:
            logger.error(f"Failed to spawn agent: {e}")

    async def scheduler_loop(self):
        logger.info("Background scheduler started.")
        while True:
            now = datetime.now()
            for task in list(self.tasks.values()):
                if task.next_run_at and now >= task.next_run_at:
                    await self.trigger_task(task)
            
            await asyncio.sleep(10) # Check every 10 seconds

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
        return proc.execute(agent_id, args.get("command"), project_id=project_id)

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
                    "status": resp.status_code,
                    "content": content,
                    "headers": dict(resp.headers)
                }
        except Exception as e:
            raise JSONRPCError(-32603, f"HTTP request failed: {e}")

    def handle_grant_approve(self, params: Dict[str, Any]) -> bool:
        approval_id = params.get("approval_id")
        grant_type = GrantType(params.get("grant_type", "allow_once"))
        duration = params.get("duration", 0)

        if approval_id in self.ui_handler.pending_approvals:
            self.ui_handler.pending_approvals[approval_id].set_result({
                "grant_type": grant_type,
                "duration": duration
            })
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
    run_parser.add_argument("--socket", type=str, default="/tmp/rudi.sock", help="Path to the UDS socket")
    run_parser.add_argument("--config", type=str, default="rudi-config.yaml", help="Path to the config file")
    
    # Pull command
    pull_parser = subparsers.add_parser("pull", help="Download/cache an LLM model")
    pull_parser.add_argument("model", type=str, help="The model ID to pull (e.g. mlx-community/Meta-Llama-3-8B-Instruct-4bit)")

    args = parser.parse_args()

    from core.common.config import ConfigLoader
    config = ConfigLoader.load(args.config if args.command == "run" else "rudi-config.yaml")
    
    if args.command == "pull":
        from core.llm.factory import LLMFactory
        provider = LLMFactory.get_provider(config)
        if hasattr(provider, "download_model"):
            print(f"Pulling model: {args.model}...")
            success = provider.download_model(args.model)
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
    socket_path = args.socket if args.command == "run" else "/tmp/rudi.sock"
    server = ControlPlaneServer(config, socket_path=socket_path)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")

if __name__ == "__main__":
    main()
