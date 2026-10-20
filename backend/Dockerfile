FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DEFAULT_TIMEOUT=300
ENV PIP_RETRIES=15
ENV PIP_INDEX_URL=https://mirrors.huaweicloud.com/repository/pypi/simple
ENV SAL_USE_VCLPLUGIN=svp

WORKDIR /app

RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's/deb.debian.org/mirrors.huaweicloud.com/g' /etc/apt/sources.list.d/debian.sources; \
      sed -i 's/security.debian.org/mirrors.huaweicloud.com/g' /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
      sed -i 's/deb.debian.org/mirrors.huaweicloud.com/g' /etc/apt/sources.list; \
      sed -i 's/security.debian.org/mirrors.huaweicloud.com/g' /etc/apt/sources.list; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      libreoffice-writer \
      fonts-noto-cjk \
      fontconfig; \
    rm -rf /var/lib/apt/lists/*

COPY fonts/99-contract-cjk.conf /etc/fonts/conf.d/99-contract-cjk.conf
RUN fc-cache -f

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
