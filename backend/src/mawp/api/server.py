"""启动 Platform API：python -m mawp.api.server"""

from __future__ import annotations

import os
from pathlib import Path


def main() -> None:
    import uvicorn

    # 确保从 backend 目录能找到配置与 examples
    backend_root = Path(__file__).resolve().parents[3]
    os.chdir(backend_root)

    host = os.environ.get("MAWP_HOST", "127.0.0.1")
    port = int(os.environ.get("MAWP_PORT", "8787"))
    uvicorn.run(
        "mawp.api.platform:create_app",
        factory=True,
        host=host,
        port=port,
        reload=os.environ.get("MAWP_RELOAD", "0") == "1",
    )


if __name__ == "__main__":
    main()
