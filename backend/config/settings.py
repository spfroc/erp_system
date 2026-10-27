import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.getenv(
    "DJANGO_ALLOWED_HOSTS",
    "localhost,127.0.0.1,0.0.0.0,backend,comp,one,182.168.1.166,182.168.1.120",
).split(",")
CSRF_TRUSTED_ORIGINS = [
    origin
    for origin in [
        *os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(","),
        "http://localhost:18082",
        "http://127.0.0.1:18082",
        "http://comp:18082",
        "http://one:18082",
        "http://182.168.1.166:18082",
        "http://182.168.1.120:18082",
    ]
    if origin.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "apps.data_store",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("MYSQL_DATABASE", "yicai_erp"),
        "USER": os.getenv("MYSQL_USER", "yicai"),
        "PASSWORD": os.getenv("MYSQL_PASSWORD", "yicai"),
        "HOST": os.getenv("MYSQL_HOST", "localhost"),
        "PORT": os.getenv("MYSQL_PORT", "3306"),
        "CONN_MAX_AGE": int(os.getenv("MYSQL_CONN_MAX_AGE", "60")),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

if os.getenv("USE_SQLITE", "0") == "1":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "local-preview.sqlite3",
        }
    }

if mysql_ssl_ca := os.getenv("MYSQL_SSL_CA"):
    DATABASES["default"]["OPTIONS"]["ssl"] = {"ca": mysql_ssl_ca}

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_SAVE_EVERY_REQUEST = False
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"

CORS_ALLOWED_ORIGINS = [
    origin
    for origin in [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:18082",
        "http://127.0.0.1:18082",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://comp:5173",
        "http://comp:5174",
        "http://comp:18082",
        "http://comp:8000",
        "http://comp:18080",
        "http://182.168.1.166:18082",
        "http://182.168.1.166:18080",
        "http://one:18082",
        "http://one:18080",
        "http://182.168.1.120:18082",
        "http://182.168.1.120:18080",
        "https://assist.qlyc.co",
        "https://qlyc.co",
        "https://www.qlyc.co",
        "https://yizhichan.co",
        "https://www.yizhichan.co",
        "http://qinghuicai.cn",
        "http://www.qinghuicai.cn",
        "https://qinghuicai.cn",
        "https://www.qinghuicai.cn",
        *os.getenv("DJANGO_CORS_ALLOWED_ORIGINS", "").split(","),
    ]
    if origin.strip()
]
CORS_ALLOW_ALL_ORIGINS = os.getenv("CORS_ALLOW_ALL_ORIGINS", "0") == "1"
CORS_ALLOW_CREDENTIALS = True

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "apps.data_store.dev_ops_tasks.run_crawler_script": {"queue": "crawler"},
}
CELERY_BEAT_SCHEDULE = {
    "tick-dev-ops-jobs": {
        "task": "apps.data_store.dev_ops_tasks.tick_scheduled_jobs",
        "schedule": 60.0,
    },
}
NOTICE_CRAWLER_DIR = os.getenv("NOTICE_CRAWLER_DIR", str(BASE_DIR.parent / "notice_crawler"))

