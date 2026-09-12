from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from mawp.config.loader import AgentConfig
from mawp.goal.models import IssueDocument
from mawp.goal.store import GoalStore


class ApproveError(PermissionError):
    """approve 门禁拒绝。"""


class ApproveService:
    """Issue 级交付授权（GW-052）。"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.goal_store = GoalStore(config)
        self.base = config.workspace_path() / ".mawp" / "approvals"

    def approve_path(self, issue_id: str) -> Path:
        return self.base / f"{issue_id}.json"

    @staticmethod
    def issue_hash(issue: IssueDocument) -> str:
        payload = issue.to_markdown().encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def approve(self, issue_id: str, *, actor_id: str = "local") -> Path:
        issue = self.goal_store.load_issue(issue_id)
        self.base.mkdir(parents=True, exist_ok=True)
        record = {
            "issue_id": issue_id,
            "approved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "issue_hash": self.issue_hash(issue),
            "actor_id": actor_id,
            "title": issue.title,
        }
        path = self.approve_path(issue_id)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load(self, issue_id: str) -> dict | None:
        path = self.approve_path(issue_id)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def is_valid(self, issue_id: str) -> tuple[bool, str]:
        issue = self.goal_store.load_issue(issue_id)
        record = self.load(issue_id)
        if record is None:
            return False, f"Issue {issue_id} 尚未授权，请运行 agent approve {issue_id}"
        current_hash = self.issue_hash(issue)
        if record.get("issue_hash") != current_hash:
            return False, (
                f"Issue {issue_id} 在 approve 后已变更，请重新运行 agent approve {issue_id}"
            )
        return True, "ok"

    def assert_valid(self, issue_id: str) -> None:
        ok, reason = self.is_valid(issue_id)
        if not ok:
            raise ApproveError(reason)
