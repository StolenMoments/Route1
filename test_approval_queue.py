import unittest

from approval_queue import ApprovalQueue


class FakePty:
    def __init__(self):
        self.sent = []

    def send(self, text: str):
        self.sent.append(text)


class TestApprovalQueue(unittest.TestCase):
    def test_enqueue_calls_on_request_with_target_and_message(self):
        calls = []
        queue = ApprovalQueue(on_request=lambda target, message: calls.append((target, message)))
        pty = FakePty()

        queue.enqueue("codex", "Proceed? (y/n)", pty)

        self.assertEqual(calls, [("codex", "Proceed? (y/n)")])
        pending_item = queue.get_pending("codex")
        self.assertIsNotNone(pending_item)
        self.assertEqual(pending_item.status, "pending")

    def test_resolve_yes_injects_into_pty_and_marks_item_resolved(self):
        queue = ApprovalQueue(on_request=lambda target, message: None)
        pty = FakePty()
        queue.enqueue("codex", "Delete files? (y/n)", pty)

        queue.resolve("codex", "y")

        self.assertEqual(pty.sent, ["y\n"])
        self.assertIsNone(queue.get_pending("codex"))
        resolved_item = queue.get_resolved("codex")
        self.assertIsNotNone(resolved_item)
        self.assertEqual(resolved_item.status, "resolved")

    def test_resolve_is_noop_when_no_pending_item(self):
        queue = ApprovalQueue(on_request=lambda target, message: None)

        # Should not raise.
        queue.resolve("missing-target", "y")

        self.assertIsNone(queue.get_pending("missing-target"))
        self.assertIsNone(queue.get_resolved("missing-target"))


if __name__ == "__main__":
    unittest.main()
