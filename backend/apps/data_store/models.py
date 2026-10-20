from django.db import models


class AppState(models.Model):
    """Legacy JSON snapshot kept for fallback and one-time imports."""

    key = models.CharField(max_length=100, unique=True)
    data = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "app_state"

    def __str__(self) -> str:
        return self.key


class BaseRecord(models.Model):
    id = models.CharField(max_length=64, primary_key=True)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.CharField(max_length=100, blank=True)

    class Meta:
        abstract = True

    @classmethod
    def from_payload(cls, payload: dict):
        payload_id = payload.get("id")
        if not payload_id:
            raise ValueError(f"{cls.__name__} payload requires id")
        return cls(id=payload_id, data=payload)


class RoleRecord(BaseRecord):
    name = models.CharField(max_length=100)

    class Meta:
        db_table = "roles"


class UserRecord(BaseRecord):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, default="启用")

    class Meta:
        db_table = "users"


class OrganizationRecord(BaseRecord):
    name = models.CharField(max_length=255, db_index=True)
    entity_type = models.CharField(max_length=50, blank=True)
    unified_credit_code = models.CharField(max_length=64, blank=True, db_index=True)
    roles = models.JSONField(default=list)
    status = models.CharField(max_length=20, default="正常")

    class Meta:
        db_table = "organizations"


class ProductRecord(BaseRecord):
    code = models.CharField(max_length=100, db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    kind = models.CharField(max_length=50)
    category = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "products"


class SupplierPriceRecord(BaseRecord):
    product_id = models.CharField(max_length=64, db_index=True)
    supplier_org_id = models.CharField(max_length=64, db_index=True)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    effective_date = models.CharField(max_length=20, blank=True)

    class Meta:
        db_table = "supplier_prices"
        indexes = [models.Index(fields=["product_id", "supplier_org_id", "effective_date"], name="supplier_pr_product_71c2f3_idx")]


class ProjectRecord(BaseRecord):
    project_no = models.CharField(max_length=100, db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    type = models.CharField(max_length=50, db_index=True)
    customer_org_id = models.CharField(max_length=64, db_index=True)
    usage_unit_org_id = models.CharField(max_length=64, blank=True)
    own_company_org_id = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=50, db_index=True)

    class Meta:
        db_table = "projects"


class ProjectItemRecord(BaseRecord):
    project_id = models.CharField(max_length=64, db_index=True)
    sales_order_id = models.CharField(max_length=64, blank=True, db_index=True)
    purchase_order_id = models.CharField(max_length=64, blank=True, db_index=True)
    product_id = models.CharField(max_length=64, db_index=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        db_table = "project_items"


class SalesOrderRecord(BaseRecord):
    project_id = models.CharField(max_length=64, db_index=True)
    order_no = models.CharField(max_length=100, db_index=True)
    customer_org_id = models.CharField(max_length=64, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    receivable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    received_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=50, db_index=True)

    class Meta:
        db_table = "sales_orders"


class PurchaseOrderRecord(BaseRecord):
    project_id = models.CharField(max_length=64, db_index=True)
    order_no = models.CharField(max_length=100, db_index=True)
    supplier_org_id = models.CharField(max_length=64, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=50, db_index=True)

    class Meta:
        db_table = "purchase_orders"


class ServiceOrderRecord(BaseRecord):
    project_id = models.CharField(max_length=64, db_index=True)
    order_no = models.CharField(max_length=100, db_index=True)
    service_id = models.CharField(max_length=64, db_index=True)
    customer_org_id = models.CharField(max_length=64, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    receivable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    received_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=50, db_index=True)

    class Meta:
        db_table = "service_orders"


class OnboardingRecord(BaseRecord):
    project_id = models.CharField(max_length=64, db_index=True)
    customer_org_id = models.CharField(max_length=64, db_index=True)
    platform = models.CharField(max_length=50, db_index=True)
    step = models.CharField(max_length=50, db_index=True)

    class Meta:
        db_table = "onboarding_records"


class PlatformAccountRecord(BaseRecord):
    customer_org_id = models.CharField(max_length=64, db_index=True)
    platform = models.CharField(max_length=50, db_index=True)
    account_name = models.CharField(max_length=255, blank=True)
    current_status = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "platform_accounts"


class WebsiteLeadRecord(BaseRecord):
    company_name = models.CharField(max_length=255, db_index=True)
    phone = models.CharField(max_length=50, db_index=True)
    contact_name = models.CharField(max_length=100, blank=True)
    platform = models.CharField(max_length=50, db_index=True)
    status = models.CharField(max_length=20, default="未跟进", db_index=True)

    class Meta:
        db_table = "website_leads"


class ProjectReminderRecord(BaseRecord):
    project_id = models.CharField(max_length=64, db_index=True)
    work_content = models.CharField(max_length=100)
    status = models.CharField(max_length=20, db_index=True)
    created_by_user_id = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "project_reminders"


class ProjectMemoRecord(BaseRecord):
    project_id = models.CharField(max_length=64, db_index=True)
    content = models.CharField(max_length=200)
    created_by = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "project_memos"


class OptionGroupRecord(BaseRecord):
    key = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100)

    class Meta:
        db_table = "option_groups"


class InvoiceRecord(BaseRecord):
    invoice_no = models.CharField(max_length=100, blank=True, db_index=True)
    invoice_date = models.CharField(max_length=20, blank=True)
    type = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=50, db_index=True)

    class Meta:
        db_table = "invoices"


class TransactionRecord(BaseRecord):
    project_id = models.CharField(max_length=64, db_index=True)
    type = models.CharField(max_length=20, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date = models.CharField(max_length=20, db_index=True)
    status = models.CharField(max_length=20, db_index=True)

    class Meta:
        db_table = "transactions"


class OperationLogRecord(BaseRecord):
    action = models.CharField(max_length=100, db_index=True)
    target_type = models.CharField(max_length=50, db_index=True)
    target_name = models.CharField(max_length=255, blank=True)
    operator = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "operation_logs"


class OcrJobRecord(BaseRecord):
    type = models.CharField(max_length=50, db_index=True)
    file_name = models.CharField(max_length=255)
    status = models.CharField(max_length=50, db_index=True)

    class Meta:
        db_table = "ocr_jobs"


class TrademarkCertificateRecord(BaseRecord):
    registration_no = models.CharField(max_length=64, db_index=True)
    registrant = models.CharField(max_length=255, db_index=True)
    registrant_address = models.CharField(max_length=500, blank=True)
    international_class = models.CharField(max_length=20, blank=True)
    registration_date = models.CharField(max_length=20, blank=True)
    valid_until = models.CharField(max_length=20, blank=True)

    class Meta:
        db_table = "trademark_certificates"


class NoticeRecord(BaseRecord):
    title = models.CharField(max_length=500, db_index=True)
    project_number = models.CharField(max_length=100, blank=True, db_index=True)
    supplier_name = models.CharField(max_length=255, blank=True, db_index=True)
    department = models.CharField(max_length=255, blank=True, db_index=True)
    category = models.CharField(max_length=100, blank=True, db_index=True)
    notice_kind = models.CharField(max_length=50, default="竞价项目", db_index=True)
    bid_status = models.CharField(max_length=50, blank=True, db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_public = models.BooleanField(default=False, db_index=True)
    source = models.CharField(max_length=30, default="manual", db_index=True)
    external_id = models.CharField(max_length=100, blank=True, db_index=True)
    published_at = models.CharField(max_length=40, blank=True, db_index=True)

    class Meta:
        db_table = "notices"


class NoticeCollectionSourceRecord(BaseRecord):
    name = models.CharField(max_length=100, db_index=True)
    kind = models.CharField(max_length=50, db_index=True)
    enabled = models.BooleanField(default=True, db_index=True)
    last_run_at = models.CharField(max_length=40, blank=True)
    last_status = models.CharField(max_length=20, blank=True)

    class Meta:
        db_table = "notice_collection_sources"


class NoticeCollectionRunRecord(BaseRecord):
    source_id = models.CharField(max_length=64, db_index=True)
    source_name = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, db_index=True)
    fetched_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    lead_count = models.PositiveIntegerField(default=0)
    started_at = models.CharField(max_length=40, blank=True, db_index=True)
    finished_at = models.CharField(max_length=40, blank=True)

    class Meta:
        db_table = "notice_collection_runs"


class OfficialSiteRecord(BaseRecord):
    key = models.CharField(max_length=50, db_index=True)
    name = models.CharField(max_length=100, db_index=True)
    domain = models.CharField(max_length=255, db_index=True)
    brand = models.CharField(max_length=100, blank=True)
    company_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, default="启用", db_index=True)

    class Meta:
        db_table = "official_sites"


class OfficialPageRecord(BaseRecord):
    site_id = models.CharField(max_length=64, db_index=True)
    slug = models.CharField(max_length=100, db_index=True)
    title = models.CharField(max_length=255, db_index=True)
    template = models.CharField(max_length=50, default="home", db_index=True)
    status = models.CharField(max_length=20, default="draft", db_index=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = "official_pages"


class LibraryContactRecord(BaseRecord):
    name = models.CharField(max_length=255, db_index=True)
    mobile = models.CharField(max_length=255, blank=True, db_index=True)
    license_code = models.CharField(max_length=64, blank=True, db_index=True)
    signed = models.CharField(max_length=20, default="有效", db_index=True)
    origin = models.CharField(max_length=50, blank=True, db_index=True)
    customer_type = models.CharField(max_length=50, blank=True, db_index=True)
    sell_user_id = models.CharField(max_length=64, blank=True, db_index=True)

    class Meta:
        db_table = "library_contacts"


class SmsTemplateRecord(BaseRecord):
    name = models.CharField(max_length=100, db_index=True)
    content = models.CharField(max_length=500, blank=True)
    prefix = models.CharField(max_length=50, blank=True)

    class Meta:
        db_table = "sms_templates"


class CustomerAccountRecord(BaseRecord):
    """官网客户控制台账号，与员工 UserRecord 分开。"""

    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=50, db_index=True)
    customer_name = models.CharField(max_length=255, blank=True)
    customer_org_id = models.CharField(max_length=64, blank=True, db_index=True)
    status = models.CharField(max_length=20, default="启用", db_index=True)

    class Meta:
        db_table = "customer_accounts"


class SmsRecordRecord(BaseRecord):
    task_id = models.CharField(max_length=100, blank=True, db_index=True)
    mobile = models.CharField(max_length=255, blank=True, db_index=True)
    content = models.CharField(max_length=500, blank=True)
    sms_type = models.CharField(max_length=50, blank=True, db_index=True)
    source = models.CharField(max_length=50, blank=True, db_index=True)
    result = models.CharField(max_length=100, blank=True)
    balance = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "sms_records"


class ManagedFile(models.Model):
    id = models.CharField(max_length=64, primary_key=True)
    document_type = models.CharField(max_length=30, db_index=True)
    owner_id = models.CharField(max_length=64, db_index=True)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    file = models.FileField(upload_to="business_documents/%Y/%m/")
    created_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "managed_files"
