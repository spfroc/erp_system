"""开发运维定时任务。仅开发人员权限可管理。"""

from django.db import models


class DevOpsJob(models.Model):
    script_key = models.CharField(max_length=64, db_index=True)
    name = models.CharField(max_length=128)
    enabled = models.BooleanField(default=False, db_index=True)
    schedule_type = models.CharField(max_length=16, default="manual")  # interval|cron|manual
    interval_seconds = models.PositiveIntegerField(null=True, blank=True)
    cron_expr = models.CharField(max_length=64, blank=True, default="")
    args_json = models.JSONField(default=dict, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True, db_index=True)
    updated_by = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dev_ops_job"


class DevOpsJobRun(models.Model):
    job = models.ForeignKey(DevOpsJob, on_delete=models.CASCADE, related_name="runs")
    trigger = models.CharField(max_length=16, default="manual")  # schedule|manual
    status = models.CharField(max_length=16, default="pending", db_index=True)
    celery_task_id = models.CharField(max_length=64, blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    stdout = models.TextField(blank=True, default="")
    stderr = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "dev_ops_job_run"
        ordering = ["-id"]
