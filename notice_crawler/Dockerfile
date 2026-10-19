FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-docker.txt /app/requirements-docker.txt
RUN pip install --no-cache-dir -r requirements-docker.txt

COPY js/package.json js/package-lock.json* /app/js/
RUN cd /app/js && npm install --omit=dev

COPY . /app
RUN chmod +x /app/docker/entrypoint.sh \
    && mkdir -p /app/data/attachments

ENV PYTHONUNBUFFERED=1 \
    EXTRACTOR_BACKEND=heuristic \
    REQUEST_INTERVAL=0.4

CMD ["/app/docker/entrypoint.sh"]
