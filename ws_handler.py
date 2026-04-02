import asyncio
import inspect
import json
import os
from typing import TYPE_CHECKING, Any, Coroutine, Dict, Optional, Set, Type

from approval_queue import ApprovalQueue
from config import CLI_CONFIGS, DEFAULT_CWD
from mention_parser import parse as parse_mention

if TYPE_CHECKING:
    from pty_manager import PtyManager


class WsHandler:
    def __init__(
        self,
        *,
        cli_configs: Optional[Dict[str, Dict[str, Any]]] = None,
        default_cwd: Optional[str] = None,
        pty_manager_cls: Optional[Type[Any]] = None,
    ):
        self.cli_configs = {
            name: dict(config)
            for name, config in (cli_configs or CLI_CONFIGS).items()
        }
        self.cwd = os.path.expanduser(default_cwd or DEFAULT_CWD)
        self.focused_cli: str = "claude"
        if self.focused_cli not in self.cli_configs:
            self.focused_cli = next(iter(self.cli_configs))

        self.clients: Set[Any] = set()
        self._send_lock = asyncio.Lock()

        self.approval_queue = ApprovalQueue(on_request=self._on_approval_enqueue)
        self.pty_managers: Dict[str, Any] = {}
        manager_cls = pty_manager_cls
        if manager_cls is None:
            from pty_manager import PtyManager  # Local import for testability.

            manager_cls = PtyManager
        for name, config in self.cli_configs.items():
            self.pty_managers[name] = manager_cls(
                name=name,
                config=config,
                on_output=self._build_output_callback(name),
                on_approval_request=self._on_approval_request,
                on_status_change=self._on_status_change,
            )

    def _build_output_callback(self, target: str):
        async def _callback(data: str):
            await self._broadcast(
                {
                    "type": "output",
                    "target": target,
                    "data": data,
                }
            )

        return _callback

    def _on_approval_enqueue(self, target: str, message: str) -> None:
        self._schedule(
            self._broadcast(
                {
                    "type": "approval_request",
                    "target": target,
                    "message": message,
                }
            )
        )

    def _schedule(self, coro: Coroutine[Any, Any, Any]):
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            # If no running loop is available (for example, from sync callback
            # in tests), execute immediately.
            asyncio.run(coro)

    async def _on_approval_request(self, target: str, message: str):
        pty = self.pty_managers.get(target)
        if pty is None:
            await self._broadcast(
                {
                    "type": "error",
                    "target": target,
                    "message": f"Unknown target: {target}",
                }
            )
            return
        self.approval_queue.enqueue(target, message, pty)

    async def _on_status_change(self, target: str, status: str):
        await self._broadcast(
            {
                "type": "status",
                "target": target,
                "status": status,
            }
        )

    async def _send_to_client(self, client: Any, message: Dict[str, Any]):
        if hasattr(client, "send_json"):
            await client.send_json(message)
            return
        await client.send(json.dumps(message))

    async def _broadcast(self, message: Dict[str, Any]):
        if not self.clients:
            return

        async with self._send_lock:
            disconnected = []
            for client in self.clients:
                try:
                    await self._send_to_client(client, message)
                except Exception:
                    disconnected.append(client)
            for client in disconnected:
                self.clients.discard(client)

    async def _send_current_statuses(self, client: Any):
        for name, manager in self.pty_managers.items():
            await self._send_to_client(
                client,
                {
                    "type": "status",
                    "target": name,
                    "status": manager.status,
                },
            )

    async def _send_unknown_target_error(self, target: Any):
        await self._broadcast(
            {
                "type": "error",
                "target": str(target),
                "message": f"Unknown target: {target}",
            }
        )

    async def _get_manager_or_error(self, target: Any):
        manager = self.pty_managers.get(target)
        if manager is None:
            await self._send_unknown_target_error(target)
            return None
        return manager

    async def _handle_focus_message(self, msg: Dict[str, Any]):
        target = msg.get("target")
        manager = await self._get_manager_or_error(target)
        if manager is None:
            return
        self.focused_cli = manager.name

    async def _handle_input_message(self, msg: Dict[str, Any]):
        raw_data = msg.get("data", "")
        parsed = parse_mention(raw_data)
        target = parsed.get("target") or msg.get("target") or self.focused_cli
        manager = await self._get_manager_or_error(target)
        if manager is None:
            return
        manager.send(parsed.get("text", ""))

    def _handle_approval_message(self, msg: Dict[str, Any]):
        target = msg.get("target")
        answer = str(msg.get("data", ""))
        self.approval_queue.resolve(target, answer)

    async def _handle_cwd_message(self, msg: Dict[str, Any]):
        path = msg.get("path")
        if not path:
            await self._broadcast(
                {
                    "type": "error",
                    "target": "all",
                    "message": "Missing cwd path",
                }
            )
            return
        self.cwd = os.path.expanduser(path)
        for manager in self.pty_managers.values():
            manager.stop()
            manager.start(self.cwd)

    async def _handle_restart_message(self, msg: Dict[str, Any]):
        target = msg.get("target")
        manager = await self._get_manager_or_error(target)
        if manager is None:
            return
        manager.stop()
        manager.start(self.cwd)

    async def _handle_config_update_message(self, msg: Dict[str, Any]):
        target = msg.get("target")
        manager = await self._get_manager_or_error(target)
        if manager is None:
            return

        config_patch = msg.get("config", {})
        if not isinstance(config_patch, dict):
            await self._broadcast(
                {
                    "type": "error",
                    "target": str(target),
                    "message": "config must be an object",
                }
            )
            return

        manager.config.update(config_patch)

    async def handle_message(self, msg: Dict[str, Any]):
        message_type = msg.get("type")
        handlers = {
            "focus": self._handle_focus_message,
            "input": self._handle_input_message,
            "approval": self._handle_approval_message,
            "cwd": self._handle_cwd_message,
            "restart": self._handle_restart_message,
            "config_update": self._handle_config_update_message,
        }
        handler = handlers.get(message_type)
        if handler is not None:
            result = handler(msg)
            if inspect.isawaitable(result):
                await result
            return

        await self._broadcast(
            {
                "type": "error",
                "target": str(msg.get("target", "all")),
                "message": f"Unsupported message type: {message_type}",
            }
        )

    async def handle_connection(self, websocket: Any):
        if hasattr(websocket, "accept"):
            await websocket.accept()

        self.clients.add(websocket)
        try:
            await self._send_current_statuses(websocket)

            message_stream = (
                websocket.iter_text()
                if hasattr(websocket, "iter_text")
                else websocket
            )
            async for raw_message in message_stream:
                try:
                    message = (
                        raw_message
                        if isinstance(raw_message, dict)
                        else json.loads(raw_message)
                    )
                except json.JSONDecodeError:
                    await self._broadcast(
                        {
                            "type": "error",
                            "target": "all",
                            "message": "Invalid JSON payload",
                        }
                    )
                    continue
                await self.handle_message(message)
        finally:
            self.clients.discard(websocket)


_default_handler: Optional[WsHandler] = None


def get_default_handler() -> WsHandler:
    global _default_handler
    if _default_handler is None:
        _default_handler = WsHandler()
    return _default_handler


async def ws_handler(websocket, path=None):
    del path
    await get_default_handler().handle_connection(websocket)
