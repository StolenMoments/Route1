import asyncio
import threading
import pexpect
from typing import Callable, Dict, Any, Optional, Coroutine

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
        on_output: Callable[[str], Coroutine[Any, Any, None]],
        on_approval_request: Callable[[str, str], Coroutine[Any, Any, None]],
        on_status_change: Optional[Callable[[str, str], Coroutine[Any, Any, None]]] = None
    ):
        self.name = name
        self.config = config
        self.on_output = on_output
        self.on_approval_request = on_approval_request
        self.on_status_change = on_status_change
        
        # Store the event loop for thread-safe callback execution
        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        self.status = Status.STOPPED
        self.process: Optional[pexpect.spawn] = None
        self.cwd: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def _set_status(self, new_status: str):
        if self.status != new_status:
            self.status = new_status
            if self.on_status_change:
                asyncio.run_coroutine_threadsafe(
                    self.on_status_change(self.name, new_status), 
                    self.loop
                )

    def _transition_to_error(self):
        self._set_status(Status.ERROR)
        asyncio.run_coroutine_threadsafe(self._handle_error(), self.loop)

    def _handle_output_data(self, idx: int, approval_patterns: list[str], data: str):
        if idx < len(approval_patterns):
            if self.config.get("auto_approve", False):
                self.send("y\n")
                return
            asyncio.run_coroutine_threadsafe(
                self.on_approval_request(self.name, data),
                self.loop
            )
            return

        asyncio.run_coroutine_threadsafe(self.on_output(data), self.loop)

    def start(self, cwd: str):
        self.cwd = cwd
        self._set_status(Status.STARTING)
        self._stop_event.clear()

        try:
            command = self.config["command"]
            self.process = pexpect.spawn(
                command,
                cwd=cwd,
                encoding='utf-8',
                echo=False,
                timeout=None
            )
            self._set_status(Status.RUNNING)
            
            # Start the read loop in a background thread as pexpect is blocking
            self._thread = threading.Thread(target=self._read_loop, daemon=True)
            self._thread.start()
        except Exception:
            self._set_status(Status.ERROR)
            asyncio.run_coroutine_threadsafe(self._handle_error(), self.loop)

    def _read_loop(self):
        # We need to capture regular output as well as approval patterns.
        # We'll use a catch-all pattern '.+' to capture streaming output.
        approval_patterns = self.config.get("approval_patterns", [])
        all_patterns = approval_patterns + [r'.+', pexpect.EOF, pexpect.TIMEOUT]
        eof_idx = len(approval_patterns) + 1
        timeout_idx = len(approval_patterns) + 2
        
        while self.status == Status.RUNNING and not self._stop_event.is_set():
            try:
                # Use a small timeout to allow checking self._stop_event periodically
                idx = self.process.expect(all_patterns, timeout=0.1)

                if idx == eof_idx:  # pexpect.EOF
                    self._transition_to_error()
                    break

                if idx == timeout_idx:  # pexpect.TIMEOUT
                    continue

                data = self.process.after
                if data:
                    self._handle_output_data(idx, approval_patterns, data)

            except pexpect.EOF:
                self._transition_to_error()
                break
            except Exception:
                # For any other unexpected errors, transition to error state
                if self.status != Status.STOPPED:
                    self._transition_to_error()
                break

    async def _handle_error(self):
        # Wait before auto-restarting
        await asyncio.sleep(2)
        if self.status == Status.ERROR and self.cwd:
            self.start(self.cwd)

    def send(self, text: str):
        if self.process and self.process.isalive():
            self.process.send(text)

    def stop(self):
        self._set_status(Status.STOPPED)
        self._stop_event.set()
        if self.process and self.process.isalive():
            try:
                self.process.terminate(force=True)
            except Exception:
                pass
