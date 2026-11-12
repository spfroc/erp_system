FROM python:3.12-slim-bookworm

RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's/deb.debian.org/mirrors.huaweicloud.com/g' /etc/apt/sources.list.d/debian.sources; \
      sed -i 's/security.debian.org/mirrors.huaweicloud.com/g' /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
      sed -i 's/deb.debian.org/mirrors.huaweicloud.com/g' /etc/apt/sources.list; \
      sed -i 's/security.debian.org/mirrors.huaweicloud.com/g' /etc/apt/sources.list; \
    fi; \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        nodejs npm ca-certificates util-linux \
        build-essential cmake \
        libglib2.0-0 libgl1 libxcb1 libsm6 libxext6 libxrender1

WORKDIR /app

COPY requirements-docker.txt /app/requirements-docker.txt
# llama-cpp-python 常需源码编译；装完后卸掉编译器，保留 OCR 运行库
RUN pip install --no-cache-dir -i https://mirrors.huaweicloud.com/repository/pypi/simple -r requirements-docker.txt \
    && apt-get purge -y --auto-remove build-essential cmake \
    && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/* /root/.cache/pip

COPY js/package.json js/package-lock.json* /app/js/
RUN cd /app/js && npm install --omit=dev --registry https://repo.huaweicloud.com/repository/npm/

COPY . /app
RUN chmod +x /app/docker/entrypoint.sh \
    && mkdir -p /app/data/attachments

ENV PYTHONUNBUFFERED=1 \
    EXTRACTOR_BACKEND=heuristic \
    LOCAL_MODEL_PATH=/app/models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
    REQUEST_INTERVAL=0.4

CMD ["/app/docker/entrypoint.sh"]
