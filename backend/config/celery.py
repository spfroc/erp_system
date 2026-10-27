import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("yzc_erp")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
# 任务在 data_store/dev_ops_tasks.py，不是默认的 tasks.py
app.autodiscover_tasks(related_name="dev_ops_tasks")
