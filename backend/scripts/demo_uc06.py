"""Friday UC-06 smoke: validate → run(high) → approve → DONE; run(low) → DONE."""

from __future__ import annotations

import tempfile
from pathlib import Path

from mawp.config.loader import load_config
from mawp.core.engine import WorkflowEngine
from mawp.core.loader import load_workflow
from mawp.core.validate import validate_workflow

ROOT = Path(__file__).resolve().parents[1]
BRANCH = ROOT / "examples" / "branch-human" / "workflow.yaml"
HELLO = ROOT / "examples" / "hello-workflow" / "workflow.yaml"


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        cfg = load_config().model_copy(update={"workspace": tmp})
        engine = WorkflowEngine(cfg)

        # AC-01 hello
        hello = load_workflow(HELLO)
        assert validate_workflow(hello) == []
        r0 = engine.run(hello)
        assert r0.status == "DONE", r0
        print("[OK] AC-01 hello → DONE", r0.run_id)

        # UC-06 high
        wf = load_workflow(BRANCH)
        assert validate_workflow(wf) == []
        r1 = engine.run(wf)
        assert r1.status == "WAITING_USER", r1.status
        assert r1.checkpoint and r1.checkpoint.get("reason")
        print("[OK] UC-06 pause", r1.run_id, r1.checkpoint.get("reason"))
        r1 = engine.resume(r1.run_id, "approve")
        assert r1.status == "DONE", r1.status
        print("[OK] UC-06 approve → DONE")

        # low risk
        r2 = engine.run(wf, params_override={"risk": "low"})
        assert r2.status == "DONE", r2.status
        print("[OK] low risk auto → DONE", r2.run_id)

    print("ALL DEMO CHECKS PASSED")


if __name__ == "__main__":
    main()
