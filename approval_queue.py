from dataclasses import dataclass
from typing import Callable, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from pty_manager import PtyManager


@dataclass
class ApprovalItem:
    target: str
    message: str
    pty: "PtyManager"
    status: str = "pending"


class ApprovalQueue:
    def __init__(self, on_request: Callable[[str, str], None]):
        self.on_request = on_request
        self._pending: Dict[str, ApprovalItem] = {}
        self._resolved: Dict[str, ApprovalItem] = {}

    def enqueue(self, target: str, message: str, pty: "PtyManager") -> None:
        item = ApprovalItem(target=target, message=message, pty=pty, status="pending")
        self._pending[target] = item
        self.on_request(target, message)

    def resolve(self, target: str, answer: str) -> None:
        item = self._pending.get(target)
        if item is None:
            return

        normalized = answer.lower()
        if normalized in ("y", "n"):
            item.pty.send(f"{normalized}\n")

        item.status = "resolved"
        self._resolved[target] = item
        self._pending.pop(target, None)

    def get_pending(self, target: str) -> Optional[ApprovalItem]:
        return self._pending.get(target)

    def get_resolved(self, target: str) -> Optional[ApprovalItem]:
        return self._resolved.get(target)
