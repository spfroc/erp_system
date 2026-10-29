#!/usr/bin/env bash
# 下载本地 GGUF（默认 Qwen2.5-3B-Instruct Q4_K_M）
# 用法:
#   bash scripts/download_gguf.sh           # 3b（推荐，附件抽取）
#   bash scripts/download_gguf.sh 1.5b      # 轻量 CPU
#   bash scripts/download_gguf.sh 7b        # 效果更好，约 4.7GB，内存建议 ≥16G
# 优先 ModelScope（国内），再 hf-mirror / HuggingFace。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODELS_DIR="${ROOT}/models"
mkdir -p "${MODELS_DIR}"
cd "${MODELS_DIR}"

SIZE="${1:-3b}"
case "${SIZE}" in
  1.5b|1.5B)
    REPO="qwen/Qwen2.5-1.5B-Instruct-GGUF"
    HF_REPO="Qwen/Qwen2.5-1.5B-Instruct-GGUF"
    FILE="qwen2.5-1.5b-instruct-q4_k_m.gguf"
    ;;
  3b|3B)
    REPO="qwen/Qwen2.5-3B-Instruct-GGUF"
    HF_REPO="Qwen/Qwen2.5-3B-Instruct-GGUF"
    FILE="qwen2.5-3b-instruct-q4_k_m.gguf"
    ;;
  7b|7B)
    REPO="qwen/Qwen2.5-7B-Instruct-GGUF"
    HF_REPO="Qwen/Qwen2.5-7B-Instruct-GGUF"
    FILE="qwen2.5-7b-instruct-q4_k_m.gguf"
    ;;
  *)
    echo "未知规格: ${SIZE}（支持 1.5b / 3b / 7b）" >&2
    exit 1
    ;;
esac

DEST="${MODELS_DIR}/${FILE}"

if [[ -f "${DEST}" ]]; then
  echo "已存在: ${DEST}"
  ls -lh "${DEST}"
  echo "在 .env 中设置:"
  echo "  LOCAL_MODEL_PATH=./models/${FILE}"
  echo "  LOCAL_N_CTX=8192"
  exit 0
fi

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "${PY}" ]]; then
  PY="$(command -v python3 || command -v python)"
fi

echo "=== 下载 ${FILE}（${REPO}）==="
echo "=== 方式 1: ModelScope（推荐，国内）==="
if "${PY}" -m pip install -q -U modelscope \
  && "${PY}" -m modelscope.cli.download \
      --model "${REPO}" \
      --local_dir "${MODELS_DIR}" \
      "${FILE}"; then
  if [[ -f "${DEST}" ]]; then
    ls -lh "${DEST}"
    echo "完成: ${DEST}"
    echo "请在 .env 写入:"
    echo "  LOCAL_MODEL_PATH=./models/${FILE}"
    echo "  LOCAL_N_CTX=8192"
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
    "${REPO}",
    allow_patterns=[file_name],
)
src = Path(cache) / file_name
if not src.exists():
    # 有的仓会把文件放在子目录
    matches = list(Path(cache).rglob(file_name))
    if not matches:
        raise SystemExit(f"未找到 {file_name}")
    src = matches[0]
if dest.exists():
    dest.unlink()
shutil.copy2(src, dest)
print(dest)
PY
then
  ls -lh "${DEST}"
  echo "完成: ${DEST}"
  echo "请在 .env 写入:"
  echo "  LOCAL_MODEL_PATH=./models/${FILE}"
  echo "  LOCAL_N_CTX=8192"
  exit 0
fi

echo "=== 方式 2: 直链镜像 ==="
URLS=(
  "https://hf-mirror.com/${HF_REPO}/resolve/main/${FILE}"
  "https://huggingface.co/${HF_REPO}/resolve/main/${FILE}"
)

for url in "${URLS[@]}"; do
  echo "尝试: ${url}"
  if curl -L --fail --connect-timeout 20 --retry 2 --retry-delay 2 \
      -o "${DEST}.partial" "${url}"; then
    mv "${DEST}.partial" "${DEST}"
    ls -lh "${DEST}"
    echo "完成: ${DEST}"
    echo "请在 .env 写入:"
    echo "  LOCAL_MODEL_PATH=./models/${FILE}"
    echo "  LOCAL_N_CTX=8192"
    exit 0
  fi
  rm -f "${DEST}.partial"
done

echo "下载失败" >&2
exit 1
