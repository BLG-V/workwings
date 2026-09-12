from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AuditResult(StrEnum):
    SUCCESS = "SUCCESS"
    DENIED = "DENIED"
    FAILED = "FAILED"


class AuditLogger:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_config(cls, config: "AgentConfig") -> "AuditLogger":
        from mawp.config.loader import AgentConfig

        path = config.workspace_path() / ".mawp" / "audit" / "audit.jsonl"
        return cls(path)

    def log(
        self,
        *,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        result: AuditResult,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": _utc_now_iso(),
            "actor_id": actor_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "result": result.value,
            "metadata": metadata or {},
        }
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry["id"]

    def read_all(self) -> list[dict[str, Any]]:
        if not self.log_path.is_file():
            return []
        entries: list[dict[str, Any]] = []
        with self.log_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries
