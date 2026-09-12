"""示例仓库：供 RAG 索引与 E2E 演示。"""

from fastapi import FastAPI

from src.auth.login import router as auth_router

app = FastAPI()
app.include_router(auth_router)


@app.get("/health")
def health():
    return {"status": "ok"}
