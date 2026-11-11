from django.db import models


class PortalNoticeInbox(models.Model):
    """门户订阅命中公告消息（按账号收件箱展示）。"""

    customer_account_id = models.CharField(max_length=64, db_index=True)
    notice_raw_id = models.BigIntegerField(db_index=True)
    digest_date = models.DateField(db_index=True)
    push_log_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    title = models.CharField(max_length=500, blank=True, default="")
    project_name = models.CharField(max_length=255, blank=True, default="")
    buyer_name = models.CharField(max_length=255, blank=True, default="")
    region_name = models.CharField(max_length=128, blank=True, default="")
    site_id = models.CharField(max_length=64, blank=True, default="")
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "portal_notice_inbox"
        constraints = [
            models.UniqueConstraint(
                fields=["customer_account_id", "notice_raw_id", "digest_date"],
                name="uniq_portal_notice_inbox_account_notice_day",
            )
        ]
        indexes = [
            models.Index(
                fields=["customer_account_id", "-created_at"],
                name="portal_inbox_account_created_idx",
            ),
            models.Index(
                fields=["customer_account_id", "is_read", "-created_at"],
                name="portal_inbox_account_read_idx",
            ),
        ]
