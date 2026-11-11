"""爬虫站点与公告分类映射（与采集表分开，采集程序不读写）。"""

from django.db import models


class NoticeCrawlSite(models.Model):
    site_id = models.CharField(max_length=64, unique=True)
    label = models.CharField(max_length=64)
    enabled = models.BooleanField(default=True, db_index=True)
    sort_order = models.IntegerField(default=0, db_index=True)
    fixed_region = models.CharField(max_length=32, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notice_crawl_site"
        ordering = ["sort_order", "id"]


class NoticeMappedCategory(models.Model):
    """列表展示用的映射分类（可新建；与站点选项多对多对照）。"""

    name = models.CharField(max_length=64, unique=True)
    enabled = models.BooleanField(default=True, db_index=True)
    sort_order = models.IntegerField(default=0, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notice_mapped_category"
        ordering = ["sort_order", "id"]


class NoticeSiteOption(models.Model):
    """站点侧可选项：站点 + 种类 + 方式。"""

    site_id = models.CharField(max_length=64, db_index=True)
    channel_key = models.CharField(max_length=64, blank=True, default="")
    channel_label = models.CharField(max_length=64, blank=True, default="")
    notice_type = models.CharField(max_length=32)
    notice_type_label = models.CharField(max_length=64, blank=True, default="")
    enabled = models.BooleanField(default=True, db_index=True)
    sort_order = models.IntegerField(default=0, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notice_site_option"
        ordering = ["site_id", "sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "channel_key", "notice_type"],
                name="uk_notice_site_option",
            ),
        ]


class NoticeCategoryOptionLink(models.Model):
    """映射分类 ↔ 站点选项（多对多）。"""

    category = models.ForeignKey(
        NoticeMappedCategory,
        on_delete=models.CASCADE,
        related_name="option_links",
    )
    option = models.ForeignKey(
        NoticeSiteOption,
        on_delete=models.CASCADE,
        related_name="category_links",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notice_category_option_link"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["category", "option"],
                name="uk_notice_category_option_link",
            ),
        ]


# 旧表保留只读兼容，迁移后不再写入
class NoticeCategoryMap(models.Model):
    """旧：站点+种类+方式→分类字符串。已由 M2M 替代。"""

    site_id = models.CharField(max_length=64, db_index=True)
    channel_key = models.CharField(max_length=64, blank=True, default="")
    channel_label = models.CharField(max_length=64, blank=True, default="")
    notice_type = models.CharField(max_length=32)
    notice_type_label = models.CharField(max_length=64, blank=True, default="")
    category = models.CharField(max_length=64, db_index=True)
    enabled = models.BooleanField(default=True, db_index=True)
    sort_order = models.IntegerField(default=0, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notice_category_map"
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "channel_key", "notice_type"],
                name="uk_notice_category_map",
            ),
        ]
