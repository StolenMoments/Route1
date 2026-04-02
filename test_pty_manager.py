import asyncio
import sys
import types
import unittest
from unittest.mock import patch

if "pexpect" not in sys.modules:
    sys.modules["pexpect"] = types.SimpleNamespace(
        EOF=object(),
        TIMEOUT=object(),
        spawn=type("Spawn", (), {}),
    )

from pty_manager import PtyManager, Status


class FakeProcess:
    def __init__(self, manager, idx, data):
        self.manager = manager
        self.idx = idx
        self.data = data
        self.after = ""
        self.sent = []

    def expect(self, patterns, timeout=0.1):
        self.after = self.data
        self.manager._stop_event.set()
        return self.idx

    def isalive(self):
        return True

    def send(self, text):
        self.sent.append(text)


def run_immediately(coro, loop):
    try:
        loop.run_until_complete(coro)
    except RuntimeError:
        asyncio.run(coro)

    class _Done:
        def result(self):
            return None

    return _Done()


def make_manager(auto_approve=False):
    outputs = []
    approvals = []

    async def on_output(data):
        await asyncio.sleep(0)
        outputs.append(data)

    async def on_approval_request(name, data):
        await asyncio.sleep(0)
        approvals.append((name, data))

    manager = PtyManager(
        name="codex",
        config={
            "approval_patterns": [r"Approve\\?"],
            "auto_approve": auto_approve,
        },
        on_output=on_output,
        on_approval_request=on_approval_request,
    )
    manager.status = Status.RUNNING

    return manager, outputs, approvals


class TestPtyManagerReadLoop(unittest.TestCase):
    def test_approval_pattern_routes_only_to_approval_request(self):
        manager, outputs, approvals = make_manager(auto_approve=False)
        manager.process = FakeProcess(manager, idx=0, data="Approve? (y/n)")

        with patch("pty_manager.asyncio.run_coroutine_threadsafe", side_effect=run_immediately):
            manager._read_loop()

        self.assertEqual(outputs, [])
        self.assertEqual(approvals, [("codex", "Approve? (y/n)")])

    def test_normal_output_routes_only_to_output_callback(self):
        manager, outputs, approvals = make_manager(auto_approve=False)
        # idx 1 matches the catch-all '.+' pattern (non-approval output)
        manager.process = FakeProcess(manager, idx=1, data="Refactoring...\n")

        with patch("pty_manager.asyncio.run_coroutine_threadsafe", side_effect=run_immediately):
            manager._read_loop()

        self.assertEqual(outputs, ["Refactoring...\n"])
        self.assertEqual(approvals, [])

    def test_auto_approve_sends_yes_without_approval_callback(self):
        manager, outputs, approvals = make_manager(auto_approve=True)
        manager.process = FakeProcess(manager, idx=0, data="Delete 3 files? (y/n)")

        with patch("pty_manager.asyncio.run_coroutine_threadsafe", side_effect=run_immediately):
            manager._read_loop()

        self.assertEqual(outputs, [])
        self.assertEqual(approvals, [])
        self.assertEqual(manager.process.sent, ["y\n"])

    def test_timeout_with_none_data_does_not_call_output(self):
        manager, outputs, approvals = make_manager(auto_approve=False)
        # idx 3 is TIMEOUT when one approval pattern is configured.
        manager.process = FakeProcess(manager, idx=3, data=None)

        with patch("pty_manager.asyncio.run_coroutine_threadsafe", side_effect=run_immediately):
            manager._read_loop()

        self.assertEqual(outputs, [])
        self.assertEqual(approvals, [])

    def test_eof_transitions_to_error(self):
        manager, outputs, approvals = make_manager(auto_approve=False)
        # idx 2 is EOF when one approval pattern is configured.
        manager.process = FakeProcess(manager, idx=2, data="")

        with patch("pty_manager.asyncio.run_coroutine_threadsafe", side_effect=run_immediately):
            manager._read_loop()

        self.assertEqual(manager.status, Status.ERROR)
        self.assertEqual(outputs, [])
        self.assertEqual(approvals, [])


if __name__ == "__main__":
    unittest.main()
