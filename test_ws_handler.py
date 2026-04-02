import json
import unittest
from typing import Any, Dict, List, Optional

from ws_handler import WsHandler


STATUS_STOPPED = "stopped"
STATUS_RUNNING = "running"


class FakeWebSocket:
    def __init__(self):
        self.messages: List[Dict[str, Any]] = []

    async def send_json(self, payload: Dict[str, Any]):
        self.messages.append(payload)

    async def send(self, payload: str):
        self.messages.append(json.loads(payload))


class FakePtyManager:
    def __init__(
        self,
        name: str,
        config: Dict[str, Any],
        on_output,
        on_approval_request,
        on_status_change=None,
    ):
        self.name = name
        self.config = dict(config)
        self.on_output = on_output
        self.on_approval_request = on_approval_request
        self.on_status_change = on_status_change
        self.status = STATUS_STOPPED
        self.cwd: Optional[str] = None
        self.sent: List[str] = []
        self.start_calls: List[str] = []
        self.stop_calls = 0

    def send(self, text: str):
        self.sent.append(text)

    def start(self, cwd: str):
        self.cwd = cwd
        self.start_calls.append(cwd)
        self.status = STATUS_RUNNING

    def stop(self):
        self.stop_calls += 1
        self.status = STATUS_STOPPED

    async def emit_status(self, status: str):
        self.status = status
        if self.on_status_change:
            await self.on_status_change(self.name, status)


class TestWsHandler(unittest.IsolatedAsyncioTestCase):
    def make_handler(self) -> WsHandler:
        return WsHandler(pty_manager_cls=FakePtyManager)

    async def test_input_uses_mention_parser_target(self):
        handler = self.make_handler()

        await handler.handle_message(
            {
                "type": "input",
                "target": "codex",
                "data": "@gemini run tests",
            }
        )

        self.assertEqual(handler.pty_managers["gemini"].sent, ["run tests"])
        self.assertEqual(handler.pty_managers["codex"].sent, [])

    async def test_input_without_target_uses_focused_cli(self):
        handler = self.make_handler()

        await handler.handle_message({"type": "focus", "target": "codex"})
        await handler.handle_message(
            {
                "type": "input",
                "target": None,
                "data": "continue",
            }
        )

        self.assertEqual(handler.pty_managers["codex"].sent, ["continue"])
        self.assertEqual(handler.pty_managers["claude"].sent, [])

    async def test_status_change_is_forwarded_to_client(self):
        handler = self.make_handler()
        websocket = FakeWebSocket()
        handler.clients.add(websocket)

        await handler.pty_managers["claude"].emit_status(STATUS_RUNNING)

        self.assertEqual(
            websocket.messages,
            [
                {
                    "type": "status",
                    "target": "claude",
                    "status": STATUS_RUNNING,
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
