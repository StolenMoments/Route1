import asyncio
import unittest
from typing import cast
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


class AcceptingWsHandler(FakeWsHandler):
    async def handle_connection(self, websocket):
        self.handled_websockets.append(websocket)
        await websocket.accept()
        await websocket.send_text("connected")
        await websocket.close()


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

    def test_websocket_route_is_available(self):
        fake_handler = AcceptingWsHandler()

        with patch.object(main, "ws_handler", fake_handler):
            with TestClient(main.app) as client:
                with client.websocket_connect("/ws") as websocket:
                    self.assertEqual(websocket.receive_text(), "connected")

        self.assertEqual(len(fake_handler.handled_websockets), 1)


if __name__ == "__main__":
    unittest.main()
