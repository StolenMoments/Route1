import asyncio
import unittest
from typing import Any, Dict, List, Optional, cast
from unittest.mock import patch

from fastapi import WebSocket
from fastapi.testclient import TestClient

import main


class FakeManager:
    def __init__(self):
        self.start_calls = []
        self.stop_calls = 0

    def start(self, cwd: str):
        self.start_calls.append(cwd)

    def stop(self):
        self.stop_calls += 1


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
        self.status = "stopped"
        self.cwd: Optional[str] = None
        self.sent: List[str] = []

    def start(self, cwd: str):
        self.cwd = cwd
        self.status = "running"

    def stop(self):
        self.status = "stopped"

    def send(self, text: str):
        self.sent.append(text)


class FakeWsHandler:
    def __init__(self):
        self.cwd = "D:/workspace"
        self.pty_managers = {
            "claude": FakeManager(),
            "gemini": FakeManager(),
            "codex": FakeManager(),
        }
        self.handled_websockets = []

    async def handle_connection(self, websocket):
        await asyncio.sleep(0)
        self.handled_websockets.append(websocket)


class TestMain(unittest.IsolatedAsyncioTestCase):
    async def test_lifespan_starts_and_stops_all_pty_managers(self):
        fake_handler = FakeWsHandler()

        with patch.object(main, "ws_handler", fake_handler):
            async with main.lifespan(main.app):
                for manager in fake_handler.pty_managers.values():
                    self.assertEqual(manager.start_calls, [fake_handler.cwd])
                    self.assertEqual(manager.stop_calls, 0)

        for manager in fake_handler.pty_managers.values():
            self.assertEqual(manager.start_calls, [fake_handler.cwd])
            self.assertEqual(manager.stop_calls, 1)

    async def test_websocket_entrypoint_delegates_to_ws_handler(self):
        fake_handler = FakeWsHandler()
        fake_websocket = cast(WebSocket, object())

        with patch.object(main, "ws_handler", fake_handler):
            await main.websocket_entrypoint(fake_websocket)

        self.assertEqual(fake_handler.handled_websockets, [fake_websocket])


class TestMainHttp(unittest.TestCase):
    def test_root_serves_frontend_index(self):
        fake_handler = FakeWsHandler()

        with patch.object(main, "ws_handler", fake_handler):
            with TestClient(main.app) as client:
                response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("<!DOCTYPE html>", response.text)
        self.assertIn("<title>Route 1</title>", response.text)

    def test_websocket_route_works_with_real_ws_handler(self):
        real_handler = main.WsHandler(pty_manager_cls=FakePtyManager)

        with patch.object(main, "ws_handler", real_handler):
            with TestClient(main.app) as client:
                with client.websocket_connect("/ws") as websocket:
                    first_message = websocket.receive_json()
                    self.assertEqual(first_message["type"], "status")
                    self.assertIn(first_message["target"], {"claude", "gemini", "codex"})
                    self.assertEqual(first_message["status"], "running")
                    websocket.send_json({"type": "focus", "target": "codex"})
                    websocket.send_json({"type": "input", "target": None, "data": "connected"})

        self.assertEqual(real_handler.pty_managers["codex"].sent, ["connected"])


if __name__ == "__main__":
    unittest.main()
