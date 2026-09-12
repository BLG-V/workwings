from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_run_id() -> str:
    return uuid4().hex[:12]


@dataclass
class RunRecord:
    run_id: str
    workflow_id: str
    status: str
    current_node_id: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    node_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    failed_node_id: str | None = None
    error: str | None = None
    workflow_path: str | None = None
    # W3 human_checkpoint payload (also mirrored under .mawp/checkpoints/)
    checkpoint: dict[str, Any] | None = None
    # 当次 run 的自愈预算与最近一次跳转（跨 run 不保留）
    heal: dict[str, Any] | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunRecord:
        return cls(
            run_id=str(data["run_id"]),
            workflow_id=str(data.get("workflow_id", "")),
            status=str(data.get("status", "")),
            current_node_id=data.get("current_node_id"),
            params=dict(data.get("params") or {}),
            node_outputs=dict(data.get("node_outputs") or {}),
            failed_node_id=data.get("failed_node_id"),
            error=data.get("error"),
            workflow_path=data.get("workflow_path"),
            checkpoint=data.get("checkpoint"),
            heal=data.get("heal") if isinstance(data.get("heal"), dict) else None,
            created_at=str(data.get("created_at") or utc_now_iso()),
            updated_at=str(data.get("updated_at") or utc_now_iso()),
        )


class RunStore:
    def __init__(self, workspace: Path):
        self.workspace = Path(workspace).resolve()
        self.root = self.workspace / ".mawp"
        self.runs_dir = self.root / "runs"
        self.events_dir = self.root / "events"
        self.checkpoints_dir = self.root / "checkpoints"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def save_run(self, run: RunRecord) -> Path:
        run.updated_at = utc_now_iso()
        path = self.runs_dir / f"{run.run_id}.json"
        path.write_text(
            json.dumps(run.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def load_run(self, run_id: str) -> RunRecord | None:
        path = self.runs_dir / f"{run_id}.json"
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return RunRecord.from_dict(data)

    def list_runs(self, *, limit: int = 50) -> list[RunRecord]:
        paths = sorted(
            self.runs_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        runs: list[RunRecord] = []
        for path in paths[: max(1, limit)]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                runs.append(RunRecord.from_dict(data))
            except (OSError, json.JSONDecodeError, KeyError, TypeError):
                continue
        return runs

    def save_checkpoint(self, run_id: str, checkpoint: dict[str, Any]) -> Path:
        path = self.checkpoints_dir / f"{run_id}.json"
        path.write_text(
            json.dumps(checkpoint, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def load_checkpoint(self, run_id: str) -> dict[str, Any] | None:
        path = self.checkpoints_dir / f"{run_id}.json"
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None

    def delete_checkpoint(self, run_id: str) -> None:
        path = self.checkpoints_dir / f"{run_id}.json"
        if path.is_file():
            path.unlink()

    def append_event(self, run_id: str, event: dict[str, Any]) -> None:
        payload = {"run_id": run_id, "ts": utc_now_iso(), **event}
        path = self.events_dir / f"{run_id}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def read_events(self, run_id: str) -> list[dict[str, Any]]:
        path = self.events_dir / f"{run_id}.jsonl"
        if not path.is_file():
            return []
        events: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                events.append(json.loads(line))
        return events
