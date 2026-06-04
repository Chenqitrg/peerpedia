#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "🧹 清缓存..."
lsof -ti:8080 | xargs kill -9 2>/dev/null || true
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
rm -rf .pytest_cache .mypy_cache .ruff_cache 2>/dev/null || true
rm -f .coverage 2>/dev/null || true

echo "🌱 重建 demo 数据..."
.venv/bin/peerpedia seed --force 2>&1 | tail -1

echo "🚀 启动服务器..."
# Use uvicorn directly (no --reload) because uvicorn's reloader crashes
# when Jinja2 .html templates are edited — it only watches .py files.
.venv/bin/python -m uvicorn peerpedia.web.app:app --host 127.0.0.1 --port 8080
