from django.db import models


class NoticePushLog(models.Model):
    """门户公告订阅推送日志（日汇总幂等）。"""

    customer_account_id = models.CharField(max_length=64, db_index=True)
    channel = models.CharField(max_length=32, default="wechat_mp", db_index=True)
    digest_date = models.DateField(db_index=True)
    openid = models.CharField(max_length=64, blank=True, default="")
    filter_snapshot = models.JSONField(default=dict, blank=True)
    notice_ids = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=16, default="pending", db_index=True)
    errcode = models.IntegerField(default=0)
    errmsg = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notice_push_logs"
        constraints = [
            models.UniqueConstraint(
                fields=["customer_account_id", "channel", "digest_date"],
                name="uniq_notice_push_account_channel_date",
            )
        ]
        indexes = [
            models.Index(fields=["digest_date", "status"], name="notice_push_date_status_idx"),
        ]
