"""启动数据引擎 API 服务。"""

import os

import uvicorn

from core.main import app


def main():
    """启动 API 服务。"""
    host = os.environ.get("ASTOCK_HOST", "0.0.0.0")
    port = int(os.environ.get("ASTOCK_PORT", "8080"))
    reload_enabled = os.environ.get("ASTOCK_RELOAD", "0") == "1"

    print("=" * 50)
    print("A 股数据引擎 API 服务")
    print("=" * 50)
    print()
    print("启动中...")
    print()
    print("服务地址:")
    print(f"  - 管理页面：http://localhost:{port}/")
    print(f"  - API 文档：http://localhost:{port}/docs")
    print(f"  - ReDoc:   http://localhost:{port}/redoc")
    print(f"  - Health:  http://localhost:{port}/api/health")
    print()
    print("推荐环境变量:")
    print("  - ASTOCK_PORT=8080")
    print("  - DISABLE_STARTUP_JOBS=1   # CI / E2E 推荐")
    print("  - ASTOCK_ALLOWED_ORIGINS=http://127.0.0.1:8080,http://localhost:8080")
    print()
    print("按 Ctrl+C 停止服务")
    print("=" * 50)

    if reload_enabled:
        uvicorn.run("core.main:app", host=host, port=port, reload=True)
    else:
        uvicorn.run(app, host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
