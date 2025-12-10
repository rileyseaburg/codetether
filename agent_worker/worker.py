#!/usr/bin/env python3
"""
A2A Agent Worker - Runs on machines with codebases, connects to A2A server

This worker:
1. Registers itself with the A2A server
2. Registers local codebases it can work on
3. Polls for tasks assigned to its codebases
4. Executes tasks using OpenCode
5. Reports results back to the server
6. Reports OpenCode session history to the server

Usage:
    python worker.py --server https://a2a.quantum-forge.net --name "dev-vm-worker"
"""

import argparse
import asyncio
import glob
import json
import logging
import os
import signal
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger('a2a-worker')


@dataclass
class WorkerConfig:
    """Configuration for the agent worker."""
    server_url: str
    worker_name: str
    worker_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    codebases: List[Dict[str, str]] = field(default_factory=list)
    poll_interval: int = 5
    opencode_bin: Optional[str] = None
    capabilities: List[str] = field(default_factory=lambda: ["opencode", "build", "deploy"])


@dataclass
class LocalCodebase:
    """A codebase registered with this worker."""
    id: str  # Server-assigned ID
    name: str
    path: str
    description: str = ""


class AgentWorker:
    """
    Agent worker that connects to A2A server and executes tasks locally.
    """

    def __init__(self, config: WorkerConfig):
        self.config = config
        self.codebases: Dict[str, LocalCodebase] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        self.running = False
        self.opencode_bin = config.opencode_bin or self._find_opencode_binary()
        self.active_processes: Dict[str, subprocess.Popen] = {}

    def _find_opencode_binary(self) -> str:
        """Find the opencode binary."""
        locations = [
            str(Path.home() / ".local" / "bin" / "opencode"),
            str(Path.home() / "bin" / "opencode"),
            "/usr/local/bin/opencode",
            "/usr/bin/opencode",
            # Check in the A2A project
            str(Path(__file__).parent.parent / "opencode" / "packages" / "opencode" / "bin" / "opencode"),
        ]

        for loc in locations:
            if Path(loc).exists() and os.access(loc, os.X_OK):
                logger.info(f"Found opencode at: {loc}")
                return loc

        # Try PATH
        try:
            result = subprocess.run(["which", "opencode"], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

        logger.warning("OpenCode binary not found, some features may not work")
        return "opencode"

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"Content-Type": "application/json"}
            )
        return self.session

    async def start(self):
        """Start the worker."""
        logger.info(f"Starting worker '{self.config.worker_name}' (ID: {self.config.worker_id})")
        logger.info(f"Connecting to server: {self.config.server_url}")

        self.running = True

        # Register worker with server
        await self.register_worker()

        # Register configured codebases
        for cb_config in self.config.codebases:
            await self.register_codebase(
                name=cb_config.get("name", Path(cb_config["path"]).name),
                path=cb_config["path"],
                description=cb_config.get("description", ""),
            )

        # Immediately sync sessions on startup
        logger.info("Syncing sessions with server...")
        await self.report_sessions_to_server()

        # Start polling loop
        await self.poll_loop()

    async def stop(self):
        """Stop the worker gracefully."""
        logger.info("Stopping worker...")
        self.running = False

        # Kill any active processes
        for task_id, process in self.active_processes.items():
            logger.info(f"Terminating process for task {task_id}")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

        # Unregister from server
        await self.unregister_worker()

        # Close session
        if self.session and not self.session.closed:
            await self.session.close()

        logger.info("Worker stopped")

    async def register_worker(self):
        """Register this worker with the A2A server."""
        try:
            session = await self._get_session()
            url = f"{self.config.server_url}/v1/opencode/workers/register"

            payload = {
                "worker_id": self.config.worker_id,
                "name": self.config.worker_name,
                "capabilities": self.config.capabilities,
                "hostname": os.uname().nodename,
            }

            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"Worker registered successfully: {data}")
                else:
                    text = await resp.text()
                    logger.warning(f"Worker registration returned {resp.status}: {text}")
                    # Continue anyway - server might not have this endpoint yet

        except Exception as e:
            logger.warning(f"Failed to register worker (continuing anyway): {e}")

    async def unregister_worker(self):
        """Unregister this worker from the A2A server."""
        try:
            session = await self._get_session()
            url = f"{self.config.server_url}/v1/opencode/workers/{self.config.worker_id}/unregister"

            async with session.post(url) as resp:
                if resp.status == 200:
                    logger.info("Worker unregistered successfully")

        except Exception as e:
            logger.debug(f"Failed to unregister worker: {e}")

    async def register_codebase(self, name: str, path: str, description: str = "") -> Optional[str]:
        """Register a local codebase with the A2A server."""
        # Validate path exists locally
        if not os.path.isdir(path):
            logger.error(f"Codebase path does not exist: {path}")
            return None

        try:
            session = await self._get_session()
            url = f"{self.config.server_url}/v1/opencode/codebases"

            payload = {
                "name": name,
                "path": path,
                "description": description,
                "worker_id": self.config.worker_id,  # Associate with this worker
            }

            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    codebase_data = data.get("codebase", data)
                    codebase_id = codebase_data.get("id")

                    self.codebases[codebase_id] = LocalCodebase(
                        id=codebase_id,
                        name=name,
                        path=path,
                        description=description,
                    )

                    logger.info(f"Registered codebase '{name}' (ID: {codebase_id}) at {path}")
                    return codebase_id
                else:
                    text = await resp.text()
                    logger.error(f"Failed to register codebase: {resp.status} - {text}")
                    return None

        except Exception as e:
            logger.error(f"Failed to register codebase: {e}")
            return None

    async def poll_loop(self):
        """Main loop - poll for tasks and execute them."""
        logger.info(f"Starting poll loop (interval: {self.config.poll_interval}s)")

        session_sync_counter = 0
        session_sync_interval = 12  # Sync sessions every 12 poll cycles (60s at 5s interval)

        while self.running:
            try:
                # Get pending tasks for our codebases
                tasks = await self.get_pending_tasks()

                for task in tasks:
                    if not self.running:
                        break

                    # Check if this task is for one of our codebases
                    codebase_id = task.get("codebase_id")
                    if codebase_id in self.codebases:
                        await self.execute_task(task)

                # Periodically sync sessions
                session_sync_counter += 1
                if session_sync_counter >= session_sync_interval:
                    session_sync_counter = 0
                    await self.report_sessions_to_server()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in poll loop: {e}")

            await asyncio.sleep(self.config.poll_interval)

    async def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """Get pending tasks from the server."""
        try:
            session = await self._get_session()

            # Get tasks for our worker's codebases
            codebase_ids = list(self.codebases.keys())
            if not codebase_ids:
                return []

            url = f"{self.config.server_url}/v1/opencode/tasks"
            params = {
                "status": "pending",
                "worker_id": self.config.worker_id,
            }

            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    tasks = await resp.json()
                    # Filter to tasks for our codebases
                    return [t for t in tasks if t.get("codebase_id") in self.codebases]
                else:
                    return []

        except Exception as e:
            logger.debug(f"Failed to get pending tasks: {e}")
            return []

    async def execute_task(self, task: Dict[str, Any]):
        """Execute a task using OpenCode."""
        task_id = task.get("id")
        codebase_id = task.get("codebase_id")
        codebase = self.codebases.get(codebase_id)

        if not codebase:
            logger.error(f"Codebase {codebase_id} not found for task {task_id}")
            return

        logger.info(f"Executing task {task_id}: {task.get('title')}")

        # Claim the task
        await self.update_task_status(task_id, "running")

        try:
            # Build the prompt
            prompt = task.get("prompt", task.get("description", ""))
            agent_type = task.get("agent_type", "build")
            metadata = task.get("metadata", {})
            model = metadata.get("model")  # e.g., "anthropic/claude-sonnet-4-20250514"
            resume_session_id = metadata.get("resume_session_id")  # Session to resume

            # Run OpenCode
            result = await self.run_opencode(
                codebase_path=codebase.path,
                prompt=prompt,
                agent_type=agent_type,
                task_id=task_id,
                model=model,
                session_id=resume_session_id,
            )

            if result["success"]:
                await self.update_task_status(
                    task_id,
                    "completed",
                    result=result.get("output", "Task completed successfully")
                )
                logger.info(f"Task {task_id} completed successfully")
            else:
                await self.update_task_status(
                    task_id,
                    "failed",
                    error=result.get("error", "Unknown error")
                )
                logger.error(f"Task {task_id} failed: {result.get('error')}")

        except Exception as e:
            logger.error(f"Task {task_id} execution error: {e}")
            await self.update_task_status(task_id, "failed", error=str(e))

    async def run_opencode(
        self,
        codebase_path: str,
        prompt: str,
        agent_type: str = "build",
        task_id: Optional[str] = None,
        model: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run OpenCode agent on a codebase."""

        # Check if opencode exists
        if not Path(self.opencode_bin).exists():
            return {"success": False, "error": f"OpenCode not found at {self.opencode_bin}"}

        # Build command using 'opencode run' with proper flags
        cmd = [
            self.opencode_bin,
            "run",
            "--agent", agent_type,
            "--format", "json",
        ]

        # Add model if specified (format: provider/model)
        if model:
            cmd.extend(["--model", model])

        # Add session resumption if specified
        if session_id:
            cmd.extend(["--session", session_id])
            logger.info(f"Resuming session: {session_id}")

        # Add the prompt as the last argument
        cmd.append(prompt)

        log_model = f" --model {model}" if model else ""
        log_session = f" --session {session_id}" if session_id else ""
        logger.info(f"Running: {self.opencode_bin} run --agent {agent_type}{log_model}{log_session} ...")

        try:
            # Run the process with line-buffered output for streaming
            process = subprocess.Popen(
                cmd,
                cwd=codebase_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                env={**os.environ, "NO_COLOR": "1"},
            )

            if task_id:
                self.active_processes[task_id] = process

            # Stream output in real-time
            output_lines = []
            try:
                # Use select to read from both stdout and stderr
                import select
                import asyncio

                while True:
                    # Check if process is done
                    ret = process.poll()

                    # Read available output
                    if process.stdout:
                        line = process.stdout.readline()
                        if line:
                            output_lines.append(line)
                            # Stream output to server
                            if task_id:
                                await self.stream_task_output(task_id, line.strip())

                    if ret is not None:
                        # Process finished, read remaining output
                        if process.stdout:
                            remaining = process.stdout.read()
                            if remaining:
                                output_lines.append(remaining)
                                if task_id:
                                    await self.stream_task_output(task_id, remaining.strip())
                        break

                    # Small sleep to prevent busy loop
                    await asyncio.sleep(0.05)

                stdout = "".join(output_lines)
                stderr = process.stderr.read() if process.stderr else ""

            except subprocess.TimeoutExpired:
                process.kill()
                stdout = "".join(output_lines)
                stderr = process.stderr.read() if process.stderr else ""
                return {"success": False, "error": "Task timed out after 10 minutes"}
            finally:
                if task_id and task_id in self.active_processes:
                    del self.active_processes[task_id]

            if process.returncode == 0:
                return {"success": True, "output": stdout}
            else:
                return {"success": False, "error": stderr or f"Exit code: {process.returncode}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def stream_task_output(self, task_id: str, output: str):
        """Stream output chunk to the server."""
        if not output:
            return
        try:
            session = await self._get_session()
            url = f"{self.config.server_url}/v1/opencode/tasks/{task_id}/output"

            payload = {
                "worker_id": self.config.worker_id,
                "output": output,
                "timestamp": datetime.now().isoformat(),
            }

            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    logger.debug(f"Failed to stream output: {resp.status}")
        except Exception as e:
            logger.debug(f"Failed to stream output: {e}")

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        result: Optional[str] = None,
        error: Optional[str] = None,
    ):
        """Update task status on the server."""
        try:
            session = await self._get_session()
            url = f"{self.config.server_url}/v1/opencode/tasks/{task_id}/status"

            payload = {
                "status": status,
                "worker_id": self.config.worker_id,
            }
            if result:
                payload["result"] = result
            if error:
                payload["error"] = error

            async with session.put(url, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.warning(f"Failed to update task status: {resp.status} - {text}")

        except Exception as e:
            logger.error(f"Failed to update task status: {e}")

    def _get_opencode_storage_path(self) -> Path:
        """Get the OpenCode global storage path."""
        # Check XDG_DATA_HOME first
        xdg_data = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
        return Path(xdg_data) / "opencode" / "storage"

    def _get_project_id_for_path(self, codebase_path: str) -> Optional[str]:
        """Get the OpenCode project ID (hash) for a given codebase path."""
        storage_path = self._get_opencode_storage_path()
        project_dir = storage_path / "project"

        if not project_dir.exists():
            return None

        # Read all project files to find the matching worktree
        for project_file in project_dir.glob("*.json"):
            if project_file.stem == "global":
                continue
            try:
                with open(project_file) as f:
                    project = json.load(f)
                    if project.get("worktree") == codebase_path:
                        return project.get("id")
            except Exception:
                continue

        return None

    def get_sessions_for_codebase(self, codebase_path: str) -> List[Dict[str, Any]]:
        """Get all OpenCode sessions for a codebase."""
        project_id = self._get_project_id_for_path(codebase_path)
        if not project_id:
            logger.debug(f"No OpenCode project ID found for {codebase_path}")
            return []

        storage_path = self._get_opencode_storage_path()
        session_dir = storage_path / "session" / project_id

        if not session_dir.exists():
            return []

        sessions = []
        for session_file in session_dir.glob("ses_*.json"):
            try:
                with open(session_file) as f:
                    session_data = json.load(f)
                    # Convert timestamps from milliseconds to ISO format
                    time_data = session_data.get("time", {})
                    created_ms = time_data.get("created", 0)
                    updated_ms = time_data.get("updated", 0)

                    sessions.append({
                        "id": session_data.get("id"),
                        "title": session_data.get("title", "Untitled"),
                        "directory": session_data.get("directory"),
                        "project_id": project_id,
                        "created_at": datetime.fromtimestamp(created_ms / 1000).isoformat() if created_ms else None,
                        "updated_at": datetime.fromtimestamp(updated_ms / 1000).isoformat() if updated_ms else None,
                        "summary": session_data.get("summary", {}),
                        "version": session_data.get("version"),
                    })
            except Exception as e:
                logger.debug(f"Error reading session file {session_file}: {e}")
                continue

        # Sort by updated time descending
        sessions.sort(key=lambda s: s.get("updated_at") or "", reverse=True)
        return sessions

    def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get messages for a specific session."""
        storage_path = self._get_opencode_storage_path()
        message_dir = storage_path / "message" / session_id

        if not message_dir.exists():
            return []

        messages = []
        for msg_file in message_dir.glob("msg_*.json"):
            try:
                with open(msg_file) as f:
                    msg_data = json.load(f)
                    time_data = msg_data.get("time", {})
                    created_ms = time_data.get("created", 0)

                    messages.append({
                        "id": msg_data.get("id"),
                        "session_id": msg_data.get("sessionID"),
                        "role": msg_data.get("role"),
                        "created_at": datetime.fromtimestamp(created_ms / 1000).isoformat() if created_ms else None,
                        "summary": msg_data.get("summary", {}),
                        "agent": msg_data.get("agent"),
                        "model": msg_data.get("model", {}),
                    })
            except Exception as e:
                logger.debug(f"Error reading message file {msg_file}: {e}")
                continue

        # Sort by created time ascending
        messages.sort(key=lambda m: m.get("created_at") or "")
        return messages

    async def report_sessions_to_server(self):
        """Report all sessions for registered codebases to the server."""
        for codebase_id, codebase in self.codebases.items():
            try:
                sessions = self.get_sessions_for_codebase(codebase.path)
                if not sessions:
                    continue

                session = await self._get_session()
                url = f"{self.config.server_url}/v1/opencode/codebases/{codebase_id}/sessions/sync"

                payload = {
                    "worker_id": self.config.worker_id,
                    "sessions": sessions,
                }

                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        logger.debug(f"Synced {len(sessions)} sessions for {codebase.name}")
                    else:
                        text = await resp.text()
                        logger.debug(f"Session sync returned {resp.status}: {text}")

            except Exception as e:
                logger.debug(f"Failed to sync sessions for {codebase.name}: {e}")


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from file."""
    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            return json.load(f)

    # Check default locations
    default_paths = [
        Path.home() / ".config" / "a2a-worker" / "config.json",
        Path("/etc/a2a-worker/config.json"),
        Path("worker-config.json"),
    ]

    for path in default_paths:
        if path.exists():
            with open(path) as f:
                return json.load(f)

    return {}


async def main():
    parser = argparse.ArgumentParser(description="A2A Agent Worker")
    parser.add_argument(
        "--server", "-s",
        default=os.environ.get("A2A_SERVER_URL", "https://a2a.quantum-forge.net"),
        help="A2A server URL"
    )
    parser.add_argument(
        "--name", "-n",
        default=os.environ.get("A2A_WORKER_NAME", os.uname().nodename),
        help="Worker name"
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to config file"
    )
    parser.add_argument(
        "--codebase", "-b",
        action="append",
        help="Codebase to register (format: name:path or just path)"
    )
    parser.add_argument(
        "--poll-interval", "-i",
        type=int,
        default=int(os.environ.get("A2A_POLL_INTERVAL", "5")),
        help="Poll interval in seconds"
    )
    parser.add_argument(
        "--opencode",
        help="Path to opencode binary"
    )

    args = parser.parse_args()

    # Load config from file
    file_config = load_config(args.config)

    # Build codebase list
    codebases = file_config.get("codebases", [])
    if args.codebase:
        for cb in args.codebase:
            if ":" in cb:
                name, path = cb.split(":", 1)
            else:
                name = Path(cb).name
                path = cb
            codebases.append({"name": name, "path": os.path.abspath(path)})

    # Create config
    config = WorkerConfig(
        server_url=args.server,
        worker_name=args.name,
        codebases=codebases,
        poll_interval=args.poll_interval,
        opencode_bin=args.opencode or file_config.get("opencode_bin"),
    )

    # Create and start worker
    worker = AgentWorker(config)

    # Handle signals
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(worker.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await worker.start()
    except KeyboardInterrupt:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
