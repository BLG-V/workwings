# -*- coding: utf-8 -*-
"""部署脚手架：为项目自动生成 Dockerfile / docker-compose.yml / 启动脚本。

用法：
    from mawp.runtime.deploy_scaffolder import scaffold_deploy_files
    scaffold_deploy_files(project_path, goal="我的项目")
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _write(path: Path, content: str, encoding: str = "utf-8") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding=encoding)
    return path


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


# --- 后端 Dockerfile 模板 ---
BACKEND_DOCKERFILE = '''# 后端 API Dockerfile
# 由 MAWP 自动生成
FROM python:3.11-slim as builder

WORKDIR /app

# 先复制依赖文件，利用 Docker 缓存
COPY apps/api/requirements.txt .
RUN pip install --user -r requirements.txt \
    && pip cache purge

FROM python:3.11-slim
WORKDIR /app

# 复制安装好的依赖
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# 复制源代码
COPY apps/api/ ./apps/api/

# 创建非 root 用户
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# 健康检查 + 启动
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5).raise_for_status()" || exit 1

EXPOSE 8000
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
'''

# --- 前端 Dockerfile 模板（静态站点）---
FRONTEND_DOCKERFILE = '''# 前端静态站点 Dockerfile
# 由 MAWP 自动生成
FROM node:20-alpine as builder

WORKDIR /app

# 复制前端文件
COPY apps/web/package.json apps/web/yarn.lock* apps/web/pnpm-lock.yaml apps/web/package-lock.json ./
RUN if [ -f yarn.lock ]; then yarn install --frozen-lockfile; \
       elif [ -f pnpm-lock.yaml ]; then pnpm install --frozen-lockfile; \
       elif [ -f package-lock.json ]; then npm ci; \
       else npm install; fi

COPY apps/web/ ./

# 构建（如果有 build 脚本）
RUN if [ -f package.json ] && grep -q '"build"' package.json; then \
        if [ -f pnpm-lock.yaml ] && command -v pnpm; then pnpm run build; \
        elif [ -f yarn.lock ] && command -v yarn; then yarn build; \
        elif command -v npm; then npm run build; fi; \
    fi

FROM nginx:alpine

# 复制构建产物到 nginx
COPY --from=builder /app/dist /usr/share/nginx/html
COPY --from=builder /app/index.html /usr/share/nginx/html/
COPY --from=builder /app/*.html /usr/share/nginx/html/
COPY --from=builder /app/*.js /usr/share/nginx/html/
COPY --from=builder /app/*.css /usr/share/nginx/html/
COPY --from=builder /app/assets /usr/share/nginx/html/assets

# nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
'''

# --- nginx 配置 ---
NGINX_CONF = '''server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
'''

# --- docker-compose.yml 模板 ---
DOCKER_COMPOSE = '''version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: deploy/Dockerfile.backend
    container_name: {project_id}-backend
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - PYTHONUNBUFFERED=1
      - PYTHONDONTWRITEBYTECODE=1
    volumes:
      - ./apps/api:/app/apps/api:ro
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8000/health', timeout=5).raise_for_status()"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

  frontend:
    build:
      context: .
      dockerfile: deploy/Dockerfile.frontend
    container_name: {project_id}-frontend
    restart: unless-stopped
    ports:
      - "3000:80"
    depends_on:
      - backend

  # 可选：Nginx 反向代理（生产环境）
  nginx:
    image: nginx:alpine
    container_name: {project_id}-nginx
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./deploy/nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - backend
      - frontend
    profiles:
      - production
'''

# --- 启动脚本 ---
START_SCRIPT = '''#!/usr/bin/env bash
# MAWP 项目一键启动脚本
# 用法: ./scripts/start.sh [dev|prod|down]

set -e

PROJECT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")/.." && pwd)"
ACTION="${{1:-dev}}"

echo "[MAWP] 项目目录: $PROJECT_DIR"
echo "[MAWP] 操作: $ACTION"

case "$ACTION" in
  dev)
    echo "[MAWP] 启动开发环境..."
    
    # 后端
    echo "[MAWP] 启动后端 (apps/api)..."
    cd "$PROJECT_DIR/apps/api"
    if [ -f requirements.txt ]; then
      pip install -r requirements.txt -q
    fi
    uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
    BACKEND_PID=$!
    
    # 前端
    echo "[MAWP] 启动前端 (apps/web)..."
    cd "$PROJECT_DIR/apps/web"
    if [ -f package.json ]; then
      if [ -f pnpm-lock.yaml ] && command -v pnpm; then
        pnpm install
        pnpm run dev --host 0.0.0.0 --port 5173 &
      elif [ -f yarn.lock ] && command -v yarn; then
        yarn install
        yarn dev --host 0.0.0.0 --port 5173 &
      elif command -v npm; then
        npm install
        npm run dev --host 0.0.0.0 --port 5173 &
      fi
    else
      python -m http.server 5173 --directory . &
    fi
    FRONTEND_PID=$!
    
    echo "[MAWP] 开发环境已启动:"
    echo "  后端: http://localhost:8000"
    echo "  前端: http://localhost:5173"
    echo "  按 Ctrl+C 停止"
    
    # 等待
    wait $BACKEND_PID $FRONTEND_PID
    ;;
  
  prod)
    echo "[MAWP] 启动生产环境 (Docker)..."
    cd "$PROJECT_DIR"
    docker-compose -p mawp-$(basename "$PROJECT_DIR") up -d --build
    echo "[MAWP] 生产环境已启动:"
    echo "  后端: http://localhost:8000"
    echo "  前端: http://localhost:3000"
    echo "  Nginx: http://localhost:80"
    ;;
  
  down)
    echo "[MAWP] 停止并清理容器..."
    cd "$PROJECT_DIR"
    docker-compose -p mawp-$(basename "$PROJECT_DIR") down
    ;;
  
  *)
    echo "[MAWP] 无效操作: $ACTION"
    echo "用法: ./scripts/start.sh [dev|prod|down]"
    exit 1
    ;;
esac
'''

# --- .dockerignore ---
DOCKERIGNORE = '''# 依赖缓存
__pycache__
*.py[cod]
*$py.class

# 虚拟环境
.venv
venv
ENV

# IDE
.idea
.vscode
*.swp
*.swo

# Git
.git
.gitignore

# node_modules
node_modules

# 部署产物
deploy/

# 日志
*.log
*.sqlite

# OS
.DS_Store
Thumbs.db
'''

# --- .gitignore ---
GITIGNORE = '''# 依赖
__pycache__/
*.py[cod]
*$py.class

# 虚拟环境
.venv/
venv/
ENV/

# IDE
.idea/
.vscode/
*.swp
*.swo

# node_modules
node_modules/

# 日志
*.log
*.sqlite

# 部署
.deployment/
deploy/

# OS
.DS_Store
Thumbs.db

# 环境变量
.env
.env.local
.env.*.local
'''


def scaffold_deploy_files(
    project_path: Path | str,
    *,
    project_id: str | None = None,
    goal: str = "MAWP Project",
    has_frontend: bool = True,
    has_backend: bool = True,
) -> dict[str, Any]:
    """为项目生成完整的部署文件。
    
    Args:
        project_path: 项目根路径
        project_id: 项目 ID（用于容器命名），默认从目录名提取
        goal: 项目名称/目标
        has_frontend: 是否包含前端
        has_backend: 是否包含后端
    
    Returns:
        生成的文件列表与路径
    """
    project_path = Path(project_path).resolve()
    deploy_dir = _ensure_dir(project_path / "deploy")
    scripts_dir = _ensure_dir(project_path / "scripts")

    if project_id is None:
        project_id = project_path.name.lower().replace(" ", "-")

    result: dict[str, Any] = {
        "ok": True,
        "project_path": str(project_path),
        "project_id": project_id,
        "files": [],
    }

    # 1. 后端 Dockerfile
    if has_backend:
        backend_df = deploy_dir / "Dockerfile.backend"
        _write(backend_df, BACKEND_DOCKERFILE)
        result["files"].append({"path": "deploy/Dockerfile.backend", "type": "dockerfile"})

    # 2. 前端 Dockerfile
    if has_frontend:
        frontend_df = deploy_dir / "Dockerfile.frontend"
        _write(frontend_df, FRONTEND_DOCKERFILE)
        result["files"].append({"path": "deploy/Dockerfile.frontend", "type": "dockerfile"})

    # 3. nginx 配置
    if has_frontend and has_backend:
        nginx_conf = deploy_dir / "nginx.conf"
        _write(nginx_conf, NGINX_CONF)
        result["files"].append({"path": "deploy/nginx.conf", "type": "nginx_config"})

    # 4. docker-compose.yml
    compose_content = DOCKER_COMPOSE.format(project_id=project_id)
    compose_path = deploy_dir / "docker-compose.yml"
    _write(compose_path, compose_content)
    result["files"].append({"path": "deploy/docker-compose.yml", "type": "compose"})

    # 5. 启动脚本
    start_path = scripts_dir / "start.sh"
    _write(start_path, START_SCRIPT)
    start_path.chmod(0o755)  # 可执行
    result["files"].append({"path": "scripts/start.sh", "type": "start_script"})

    # 6. .dockerignore
    dockerignore_path = project_path / ".dockerignore"
    _write(dockerignore_path, DOCKERIGNORE)
    result["files"].append({"path": ".dockerignore", "type": "dockerignore"})

    # 7. .gitignore
    gitignore_path = project_path / ".gitignore"
    if not gitignore_path.is_file():
        _write(gitignore_path, GITIGNORE)
        result["files"].append({"path": ".gitignore", "type": "gitignore"})

    # 8. README 部署说明
    readme_path = deploy_dir / "README.md"
    readme_content = f"""# 部署说明

## 快速开始

### 开发环境

```bash
# 启动后端 + 前端
./scripts/start.sh dev

# 访问
- 后端: http://localhost:8000
- 前端: http://localhost:5173
```

### 生产环境 (Docker)

```bash
# 构建并启动
./scripts/start.sh prod

# 查看日志
docker-compose -p mawp-{project_id} logs -f

# 停止
docker-compose -p mawp-{project_id} down

# 访问
- 后端: http://localhost:8000
- 前端: http://localhost:3000
- Nginx: http://localhost:80
```

## 文件结构

```
deploy/
├── Dockerfile.backend    # 后端镜像
├── Dockerfile.frontend   # 前端镜像
├── docker-compose.yml    # 多容器编排
└── nginx.conf            # Nginx 反向代理配置

scripts/
└── start.sh              # 一键启动脚本
```

## 手动部署

### 后端

```bash
cd apps/api
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd apps/web
npm install
npm run dev
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `PYTHONUNBUFFERED` | Python 输出不缓冲 | 1 |
| `PYTHONDONTWRITEBYTECODE` | 不生成 .pyc | 1 |
"""
    _write(readme_path, readme_content)
    result["files"].append({"path": "deploy/README.md", "type": "deploy_readme"})

    result["count"] = len(result["files"])
    return result


def scaffold_docker_only(
    project_path: Path | str,
    *,
    project_id: str | None = None,
    goal: str = "MAWP Project",
) -> dict[str, Any]:
    """只生成 Docker 相关文件（不含 docker-compose）。"""
    return scaffold_deploy_files(
        project_path,
        project_id=project_id,
        goal=goal,
        has_frontend=True,
        has_backend=True,
    )


def scaffold_compose_only(
    project_path: Path | str,
    *,
    project_id: str | None = None,
    goal: str = "MAWP Project",
) -> dict[str, Any]:
    """只生成 docker-compose.yml。"""
    project_path = Path(project_path).resolve()
    deploy_dir = _ensure_dir(project_path / "deploy")

    if project_id is None:
        project_id = project_path.name.lower().replace(" ", "-")

    compose_content = DOCKER_COMPOSE.format(project_id=project_id)
    compose_path = deploy_dir / "docker-compose.yml"
    _write(compose_path, compose_content)

    return {
        "ok": True,
        "project_path": str(project_path),
        "files": [{"path": "deploy/docker-compose.yml", "type": "compose"}],
        "count": 1,
    }


def ensure_project_deploy(
    project_path: Path | str,
    *,
    project_id: str | None = None,
    goal: str = "MAWP Project",
    has_frontend: bool = True,
    has_backend: bool = True,
) -> dict[str, Any]:
    """确保项目有完整的部署文件。
    
    如果已有文件，则跳过；否则生成。
    """
    project_path = Path(project_path).resolve()
    deploy_dir = project_path / "deploy"

    # 检查是否已有部署文件
    if deploy_dir.is_dir():
        existing = list(deploy_dir.glob("*"))
        if existing:
            return {
                "ok": True,
                "project_path": str(project_path),
                "files": [{"path": str(p.relative_to(project_path)), "type": "existing"} for p in existing],
                "count": len(existing),
                "skipped": True,
            }

    return scaffold_deploy_files(
        project_path,
        project_id=project_id,
        goal=goal,
        has_frontend=has_frontend,
        has_backend=has_backend,
    )
