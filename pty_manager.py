import asyncio
import pexpect
import re
from typing import Callable, Dict, Any, Optional


class Status:
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


class PtyManager:
    def __init__(
        self,
        name: str,
        config: Dict[str, Any],
        on_output: Callable[[str, str], None],
        on_approval_request: Callable[[str, str], None],
        on_status_change: Optional[Callable[[str, str], None]] = None
    ):
        self.name = name
        self.config = config
        self.on_output = on_output
        self.on_approval_request = on_approval_request
        self.on_status_change = on_status_change

        self.status = Status.STOPPED
        self.process = None
        self.cwd = None
        self._loop_task: Optional[asyncio.Task] = None

    def _set_status(self, new_status: str):
        if self.status != new_status:
            self.status = new_status
            if self.on_status_change:
                self.on_status_change(self.name, new_status)

    async def start(self, cwd: str):
        self.cwd = cwd
        self._set_status(Status.STARTING)

        try:
            command = self.config["command"]
            # pexpect.spawn is for Unix-like systems (including WSL)
            self.process = pexpect.spawn(
                command,
                cwd=cwd,
                encoding='utf-8',
                echo=False,
                timeout=None
            )

            self._set_status(Status.RUNNING)

            if self._loop_task:
                self._loop_task.cancel()
            self._loop_task = asyncio.create_task(self._streaming_loop())

        except Exception:
            self._set_status(Status.ERROR)
            asyncio.create_task(self._handle_error())

    async def _streaming_loop(self):
        try:
            while self.status == Status.RUNNING:
                try:
                    # Non-blocking read with timeout to allow checking loop condition
                    data = await asyncio.to_thread(
                        self.process.read_nonblocking,
                        size=4096,
                        timeout=0.1
                    )
                    if data:
                        await self._process_output(data)
                except pexpect.TIMEOUT:
                    continue
                except pexpect.EOF:
                    break
        except Exception:
            pass
        finally:
            if self.status != Status.STOPPED:
                self._set_status(Status.ERROR)
                asyncio.create_task(self._handle_error())

    async def _process_output(self, data: str):
        self.on_output(self.name, data)

        # Check approval patterns
        patterns = self.config.get("approval_patterns", [])
        for pattern in patterns:
            if re.search(pattern, data):
                if self.config.get("auto_approve", False):
                    self.send("y\n")
                else:
                    self.on_approval_request(self.name, data)
                break

    def send(self, text: str):
        if self.process and self.process.isalive():
            self.process.send(text)

    async def _handle_error(self):
        # Auto-restart logic
        await asyncio.sleep(2)
        if self.status == Status.ERROR and self.cwd:
            await self.start(self.cwd)

    def stop(self):
        self._set_status(Status.STOPPED)
        if self._loop_task:
            self._loop_task.cancel()
            self._loop_task = None
        if self.process and self.process.isalive():
            self.process.terminate(force=True)
