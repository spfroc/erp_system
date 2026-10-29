"""公告抓取表（notice_crawler 写入），Django 只读映射，不建表。"""

from django.db import models


class NoticeRaw(models.Model):
    id = models.BigAutoField(primary_key=True)
    site_id = models.CharField(max_length=64)
    notice_key = models.CharField(max_length=256)
    auction_type = models.CharField(max_length=32, null=True, blank=True)
    notice_type = models.CharField(max_length=32, null=True, blank=True)
    title = models.CharField(max_length=512, null=True, blank=True)
    region_name = models.CharField(max_length=128, null=True, blank=True)
    district_name = models.CharField(max_length=128, null=True, blank=True)
    region_guid = models.CharField(max_length=64, null=True, blank=True)
    publish_time = models.DateTimeField(null=True, blank=True)
    list_json = models.JSONField(null=True, blank=True)
    detail_json = models.JSONField(null=True, blank=True)
    content_html = models.TextField(null=True, blank=True)
    content_text = models.TextField(null=True, blank=True)
    source_url = models.CharField(max_length=1024, null=True, blank=True)
    crawl_status = models.CharField(max_length=32, default="list_only")
    parse_status = models.CharField(max_length=32, default="pending")
    error_message = models.CharField(max_length=1000, null=True, blank=True)
    crawled_at = models.DateTimeField(null=True, blank=True)
    detail_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "notice_raw"


class NoticeParsed(models.Model):
    id = models.BigAutoField(primary_key=True)
    notice_raw_id = models.BigIntegerField(unique=True)
    site_id = models.CharField(max_length=64)
    notice_key = models.CharField(max_length=256)
    project_code = models.CharField(max_length=128, null=True, blank=True)
    project_name = models.CharField(max_length=512, null=True, blank=True)
    notice_title = models.CharField(max_length=512, null=True, blank=True)
    buyer_name = models.CharField(max_length=256, null=True, blank=True)
    buyer_contact_name = models.CharField(max_length=128, null=True, blank=True)
    buyer_phone = models.CharField(max_length=64, null=True, blank=True)
    buyer_address = models.CharField(max_length=512, null=True, blank=True)
    buyer_contact = models.CharField(max_length=256, null=True, blank=True)
    region_name = models.CharField(max_length=128, null=True, blank=True)
    district_name = models.CharField(max_length=128, null=True, blank=True)
    region_guid = models.CharField(max_length=64, null=True, blank=True)
    budget_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    deal_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    deal_supplier = models.CharField(max_length=256, null=True, blank=True)
    deal_supplier_phone = models.CharField(max_length=64, null=True, blank=True)
    deal_supplier_address = models.CharField(max_length=512, null=True, blank=True)
    quote_count = models.IntegerField(null=True, blank=True)
    notice_kind = models.CharField(max_length=64, null=True, blank=True)
    procurement_mode = models.CharField(max_length=64, null=True, blank=True)
    publish_time = models.DateTimeField(null=True, blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    delivery_address = models.CharField(max_length=512, null=True, blank=True)
    quotes_json = models.JSONField(null=True, blank=True)
    suppliers_json = models.JSONField(null=True, blank=True)
    extra_json = models.JSONField(null=True, blank=True)
    model_name = models.CharField(max_length=128, null=True, blank=True)
    model_raw_json = models.JSONField(null=True, blank=True)
    confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    parsed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "notice_parsed"


class NoticeGoods(models.Model):
    id = models.BigAutoField(primary_key=True)
    notice_raw_id = models.BigIntegerField()
    notice_parsed_id = models.BigIntegerField(null=True, blank=True)
    site_id = models.CharField(max_length=64)
    notice_key = models.CharField(max_length=256)
    line_no = models.IntegerField(default=1)
    product_name = models.CharField(max_length=512, null=True, blank=True)
    category = models.CharField(max_length=256, null=True, blank=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    unit = models.CharField(max_length=64, null=True, blank=True)
    brand = models.CharField(max_length=128, null=True, blank=True)
    product_model = models.CharField(max_length=256, null=True, blank=True, db_column="model")
    unit_price = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    spec = models.CharField(max_length=2000, null=True, blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "notice_goods"


class MallCustomer(models.Model):
    """山东商城供应商 / 资料库展示（notice_crawler 写入，Django unmanaged）。"""

    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=256)
    platform_customer_id = models.CharField(max_length=64, null=True, blank=True)
    type = models.CharField(max_length=128, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    province = models.CharField(max_length=64, null=True, blank=True)
    city = models.CharField(max_length=64, null=True, blank=True)
    license = models.CharField(max_length=256, null=True, blank=True)
    license_code = models.CharField(max_length=128, null=True, blank=True)
    business_scope = models.TextField(null=True, blank=True)
    enter_time = models.CharField(max_length=64, null=True, blank=True)
    legal_person = models.CharField(max_length=128, null=True, blank=True)
    mobile = models.CharField(max_length=512, null=True, blank=True)
    new_mobile = models.CharField(max_length=512, null=True, blank=True)
    email = models.CharField(max_length=256, null=True, blank=True)
    origin = models.CharField(max_length=64, null=True, blank=True)
    signed = models.CharField(max_length=32, null=True, blank=True)
    tag = models.CharField(max_length=191, null=True, blank=True)
    sell_id = models.IntegerField(null=True, blank=True)
    sell_user_id = models.CharField(max_length=64, null=True, blank=True)
    sell_user_name = models.CharField(max_length=128, null=True, blank=True)
    remark = models.TextField(null=True, blank=True)
    agent_shop_product_number = models.IntegerField(null=True, blank=True)
    online_shop_product_number = models.IntegerField(null=True, blank=True)
    manufacturer_shop_product_number = models.IntegerField(null=True, blank=True)
    entering_origin = models.IntegerField(null=True, blank=True)
    legacy_customer_id = models.BigIntegerField(null=True, blank=True)
    list_json = models.JSONField(null=True, blank=True)
    store_json = models.JSONField(null=True, blank=True)
    crawled_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "mall_customer"
