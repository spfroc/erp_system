#!/usr/bin/env bash
# 下载默认本地 GGUF（Qwen2.5-1.5B-Instruct Q4_K_M，约 1GB，适合 CPU）
# 优先 ModelScope（国内），再 hf-mirror / HuggingFace 直链。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODELS_DIR="${ROOT}/models"
mkdir -p "${MODELS_DIR}"
cd "${MODELS_DIR}"

FILE="qwen2.5-1.5b-instruct-q4_k_m.gguf"
DEST="${MODELS_DIR}/${FILE}"

if [[ -f "${DEST}" ]]; then
  echo "已存在: ${DEST}"
  ls -lh "${DEST}"
  exit 0
fi

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "${PY}" ]]; then
  PY="$(command -v python3 || command -v python)"
fi

echo "=== 方式 1: ModelScope（推荐，国内）==="
if "${PY}" -m pip install -q -U modelscope \
  && "${PY}" -m modelscope.cli.download \
      --model qwen/Qwen2.5-1.5B-Instruct-GGUF \
      --local_dir "${MODELS_DIR}" \
      "${FILE}"; then
  if [[ -f "${DEST}" ]]; then
    ls -lh "${DEST}"
    echo "完成: ${DEST}"
    exit 0
  fi
fi

echo "ModelScope CLI 不可用，尝试 snapshot_download…"
if "${PY}" - <<PY
from pathlib import Path
from modelscope.hub.snapshot_download import snapshot_download
import shutil

models_dir = Path(r"${MODELS_DIR}")
file_name = "${FILE}"
dest = models_dir / file_name
cache = snapshot_download(
    "qwen/Qwen2.5-1.5B-Instruct-GGUF",
    allow_patterns=[file_name],
)
src = Path(cache) / file_name
if not src.exists():
    raise SystemExit(f"未找到 {src}")
if dest.exists():
    dest.unlink()
shutil.copy2(src, dest)
print(dest)
PY
then
  ls -lh "${DEST}"
  echo "完成: ${DEST}"
  exit 0
fi

echo "=== 方式 2: 直链镜像 ==="
URLS=(
  "https://hf-mirror.com/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/${FILE}"
  "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/${FILE}"
)

for url in "${URLS[@]}"; do
  echo "尝试: ${url}"
  if curl -L --fail --connect-timeout 20 --retry 2 --retry-delay 2 \
      -o "${DEST}.partial" "${url}"; then
    mv "${DEST}.partial" "${DEST}"
    ls -lh "${DEST}"
    echo "完成: ${DEST}"
    exit 0
  fi
  rm -f "${DEST}.partial"
done

echo "全部失败。请手动执行下方命令。" >&2
exit 1
