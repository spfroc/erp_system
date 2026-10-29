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
    && apt-get install -y --no-install-recommends nodejs npm ca-certificates util-linux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-docker.txt /app/requirements-docker.txt
RUN pip install --no-cache-dir -i https://mirrors.huaweicloud.com/repository/pypi/simple -r requirements-docker.txt

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
