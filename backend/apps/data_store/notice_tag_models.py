"""结果公告标签。与采集表分开，采集程序不读写这些表。"""

from django.db import models


class NoticeBuyerProfile(models.Model):
    name_key = models.CharField(max_length=256, unique=True)
    buyer_name = models.CharField(max_length=256)
    org_type = models.CharField(max_length=32, blank=True, default="")
    nature = models.CharField(max_length=32, blank=True, default="")
    province = models.CharField(max_length=32, blank=True, default="")
    city = models.CharField(max_length=64, blank=True, default="")
    district = models.CharField(max_length=64, blank=True, default="")
    source = models.CharField(max_length=16, default="rule")
    confidence = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    locked = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notice_buyer_profile"


class NoticeResultTag(models.Model):
    DEAL_KIND_GOODS = "商品"
    DEAL_KIND_SERVICE = "服务"
    DEAL_KIND_ENGINEERING = "工程"
    DEAL_KIND_UNKNOWN = "未识别"
    DEAL_KIND_CHOICES = (
        (DEAL_KIND_GOODS, "商品"),
        (DEAL_KIND_SERVICE, "服务"),
        (DEAL_KIND_ENGINEERING, "工程"),
        (DEAL_KIND_UNKNOWN, "未识别"),
    )

    notice_raw_id = models.BigIntegerField(unique=True)
    buyer_profile = models.ForeignKey(NoticeBuyerProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name="notices")
    deal_kind = models.CharField(max_length=16, blank=True, default="", db_index=True)
    source = models.CharField(max_length=16, default="rule")
    confidence = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    locked = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notice_result_tag"


class NoticeProductTag(models.Model):
    notice_raw_id = models.BigIntegerField(db_index=True)
    goods_id = models.BigIntegerField(null=True, blank=True)
    category = models.CharField(max_length=128, blank=True, default="")
    product_name = models.CharField(max_length=512, blank=True, default="")
    brand = models.CharField(max_length=128, blank=True, default="")
    source = models.CharField(max_length=16, default="rule")
    confidence = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    locked = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notice_product_tag"
        constraints = [
            models.UniqueConstraint(fields=["notice_raw_id", "goods_id"], name="uk_notice_product_goods"),
        ]


class NoticeTagRule(models.Model):
    """人工修正沉淀的词典。pattern 命中采购人或商品名时优先于内置规则。"""

    kind = models.CharField(max_length=32)
    pattern = models.CharField(max_length=256)
    value = models.CharField(max_length=128)
    source = models.CharField(max_length=16, default="manual")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notice_tag_rule"
        constraints = [
            models.UniqueConstraint(fields=["kind", "pattern"], name="uk_notice_tag_rule"),
        ]


class NoticeDictItem(models.Model):
    """公告标签用的可管理字典：公告类型(org_type) / 性质(nature)。"""

    KIND_ORG_TYPE = "org_type"
    KIND_NATURE = "nature"
    KIND_CHOICES = (
        (KIND_ORG_TYPE, "公告类型"),
        (KIND_NATURE, "性质"),
    )

    kind = models.CharField(max_length=16, choices=KIND_CHOICES, db_index=True)
    name = models.CharField(max_length=32)
    sort_order = models.IntegerField(default=0)
    enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notice_dict_item"
        constraints = [
            models.UniqueConstraint(fields=["kind", "name"], name="uk_notice_dict_kind_name"),
        ]
        ordering = ["sort_order", "id"]
