from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    select,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from datetime import datetime

from config import settings
from utils import now as now_shanghai


class Base(DeclarativeBase):
    metadata = MetaData()


class NoticeRaw(Base):
    __tablename__ = "notice_raw"
    __table_args__ = (
        UniqueConstraint("site_id", "notice_key", name="uk_site_notice"),
        {"comment": "公告原始数据"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    site_id = Column(
        String(64),
        nullable=False,
        comment="站点标识：sd-ggzyjyzx / jd-quan-yicai / jd-qing-huicai",
    )
    notice_key = Column(
        String(128),
        nullable=False,
        comment="站点内唯一键 noticeGuid/auctionNo+noticeType",
    )
    auction_type = Column(String(32), comment="站点侧采购方式编码")
    notice_type = Column(String(32), comment="站点侧公告类型编码")
    title = Column(String(512), comment="公告标题")
    region_name = Column(String(128), comment="区域名称")
    publish_time = Column(DateTime, comment="发布时间")
    list_json = Column(JSON, comment="列表接口原始条目")
    detail_json = Column(JSON, comment="详情接口原始 JSON")
    content_html = Column(Text, comment="详情正文 HTML")
    content_text = Column(Text, comment="去标签正文，供模型解析")
    source_url = Column(String(1024), comment="来源页面 URL")
    crawl_status = Column(
        String(32),
        nullable=False,
        default="list_only",
        comment="抓取状态：list_only/detail_ok/detail_fail",
    )
    parse_status = Column(
        String(32),
        nullable=False,
        default="pending",
        comment="解析状态：pending/parsed/parse_fail/skipped",
    )
    error_message = Column(String(1000), comment="抓取/解析错误信息")
    crawled_at = Column(DateTime, default=now_shanghai, comment="列表抓取时间")
    detail_at = Column(DateTime, comment="详情抓取时间")
    updated_at = Column(
        DateTime, default=now_shanghai, onupdate=now_shanghai, comment="更新时间"
    )


class NoticeParsed(Base):
    __tablename__ = "notice_parsed"
    __table_args__ = {"comment": "公告关键字段（模型解析）"}

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    notice_raw_id = Column(BigInteger, nullable=False, unique=True, comment="关联 notice_raw.id")
    site_id = Column(String(64), nullable=False, comment="站点标识")
    notice_key = Column(String(128), nullable=False, comment="公告唯一键")
    project_code = Column(String(128), comment="项目编号")
    project_name = Column(String(512), comment="项目名称")
    notice_title = Column(String(512), comment="公告标题")
    buyer_name = Column(String(256), comment="采购单位")
    buyer_contact_name = Column(String(128), comment="项目联系人")
    buyer_phone = Column(String(64), comment="项目联系电话")
    buyer_address = Column(String(512), comment="采购人/项目地址")
    buyer_contact = Column(String(256), comment="兼容：联系人/电话合并")
    region_name = Column(String(128), comment="区域名称")
    budget_amount = Column(Numeric(18, 2), comment="预算金额")
    deal_amount = Column(Numeric(18, 2), comment="成交金额")
    deal_supplier = Column(String(256), comment="成交供应商")
    deal_supplier_phone = Column(String(64), comment="成交供应商电话")
    deal_supplier_address = Column(String(512), comment="成交供应商地址")
    quote_count = Column(Integer, comment="报价家数")
    notice_kind = Column(String(64), comment="公告种类：采购/成交/终止/废标等")
    procurement_mode = Column(String(64), comment="采购方式：竞价/反拍/询比/框架二次竞价等")
    publish_time = Column(DateTime, comment="发布时间")
    start_time = Column(DateTime, comment="开始时间")
    end_time = Column(DateTime, comment="截止时间")
    delivery_address = Column(String(512), comment="交货地点")
    quotes_json = Column(JSON, comment="报价名单数组")
    suppliers_json = Column(JSON, comment="相关供应商（含未成交）")
    extra_json = Column(JSON, comment="其它模型抽出字段")
    model_name = Column(String(128), comment="解析所用模型/后端")
    model_raw_json = Column(JSON, comment="模型原始输出")
    confidence = Column(Numeric(5, 4), comment="置信度 0~1")
    parsed_at = Column(DateTime, default=now_shanghai, comment="解析时间")
    updated_at = Column(
        DateTime, default=now_shanghai, onupdate=now_shanghai, comment="更新时间"
    )


class NoticeGoods(Base):
    """公告产品明细（一对多）。"""

    __tablename__ = "notice_goods"
    __table_args__ = {"comment": "公告产品明细"}

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    notice_raw_id = Column(BigInteger, nullable=False, comment="关联 notice_raw.id")
    notice_parsed_id = Column(BigInteger, comment="关联 notice_parsed.id")
    site_id = Column(String(64), nullable=False, comment="站点标识")
    notice_key = Column(String(128), nullable=False, comment="公告唯一键")
    line_no = Column(Integer, nullable=False, default=1, comment="明细行号，从1开始")
    product_name = Column(String(512), comment="产品名称")
    category = Column(String(256), comment="产品分类")
    quantity = Column(Numeric(18, 4), comment="购买数量")
    unit = Column(String(64), comment="计量单位")
    brand = Column(String(128), comment="品牌")
    model = Column(String(256), comment="型号")
    unit_price = Column(Numeric(18, 4), comment="单价")
    spec = Column(String(2000), comment="参数/规格")
    amount = Column(Numeric(18, 2), comment="金额小计")
    created_at = Column(DateTime, default=now_shanghai, comment="创建时间")
    updated_at = Column(
        DateTime, default=now_shanghai, onupdate=now_shanghai, comment="更新时间"
    )


class NoticeAttachment(Base):
    __tablename__ = "notice_attachment"
    # utf8mb4 下整列 URL 唯一索引会超 3072 字节，与 schema.sql 一致用前缀
    __table_args__ = (
        Index(
            "uk_raw_url",
            "notice_raw_id",
            "file_url",
            unique=True,
            mysql_length={"file_url": 255},
        ),
        {"comment": "公告附件及解析"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    notice_raw_id = Column(BigInteger, nullable=False, comment="关联 notice_raw.id")
    site_id = Column(String(64), nullable=False, comment="站点标识")
    notice_key = Column(String(128), nullable=False, comment="公告唯一键")
    file_name = Column(String(512), comment="附件文件名")
    file_url = Column(String(2048), nullable=False, comment="附件下载 URL")
    local_path = Column(String(1024), comment="本地保存路径")
    file_ext = Column(String(32), comment="文件扩展名")
    file_size = Column(BigInteger, comment="文件大小（字节）")
    content_sha256 = Column(String(64), comment="文件内容 SHA256")
    download_status = Column(
        String(32),
        nullable=False,
        default="pending",
        comment="下载状态：pending/done/fail/skip",
    )
    parse_status = Column(
        String(32),
        nullable=False,
        default="pending",
        comment="解析状态：pending/parsed/parse_fail/skipped",
    )
    extracted_text = Column(Text, comment="附件抽取文本")
    parsed_json = Column(JSON, comment="附件模型解析结果")
    error_message = Column(String(1000), comment="下载/解析错误信息")
    downloaded_at = Column(DateTime, comment="下载完成时间")
    parsed_at = Column(DateTime, comment="解析完成时间")
    created_at = Column(DateTime, default=now_shanghai, comment="创建时间")
    updated_at = Column(
        DateTime, default=now_shanghai, onupdate=now_shanghai, comment="更新时间"
    )


class CrawlCursor(Base):
    __tablename__ = "crawl_cursor"
    __table_args__ = (
        UniqueConstraint("site_id", "cursor_key", name="uk_site_cursor"),
        {"comment": "分页游标"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    site_id = Column(String(64), nullable=False, comment="站点标识")
    cursor_key = Column(
        String(128), nullable=False, comment="游标键，如 auctionType:noticeType"
    )
    last_page = Column(Integer, nullable=False, default=0, comment="上次抓取到的页码")
    last_total = Column(Integer, comment="上次接口返回的总条数")
    last_success_at = Column(DateTime, comment="上次成功抓取时间")
    extra_json = Column(JSON, comment="扩展状态 JSON")
    updated_at = Column(
        DateTime, default=now_shanghai, onupdate=now_shanghai, comment="更新时间"
    )


class MallCustomer(Base):
    """山东商城供应商（对齐 vip-rebuild customers / TouchCustomer）。"""

    __tablename__ = "mall_customer"
    __table_args__ = (
        UniqueConstraint("name", name="uk_mall_customer_name"),
        {"comment": "山东商城供应商客户"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    name = Column(String(256), nullable=False, comment="公司名称")
    platform_customer_id = Column(String(64), comment="平台供应商 id / supplierGuid")
    type = Column(String(128), comment="入驻类型")
    address = Column(Text, comment="地址")
    province = Column(String(64), comment="省")
    city = Column(String(64), comment="市")
    license = Column(String(256), comment="营业执照")
    license_code = Column(String(128), comment="统一社会信用代码")
    business_scope = Column(Text, comment="经营范围")
    enter_time = Column(String(64), comment="入驻时间")
    legal_person = Column(String(128), comment="法人/联系人")
    mobile = Column(String(512), comment="联系电话")
    new_mobile = Column(String(512), comment="新平台手机号")
    email = Column(String(256), comment="邮箱")
    origin = Column(String(64), default="10", comment="来源：4旧齐鲁云采 10新齐鲁云采")
    agent_shop_product_number = Column(Integer, comment="店铺商品数量")
    list_json = Column(JSON, comment="列表原始条目")
    store_json = Column(JSON, comment="店铺详情")
    crawled_at = Column(DateTime, default=now_shanghai, comment="首次抓取时间")
    updated_at = Column(
        DateTime, default=now_shanghai, onupdate=now_shanghai, comment="更新时间"
    )


engine = create_engine(settings.db_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def _ensure_parsed_columns() -> None:
    """已有 notice_parsed 时补齐新增列（create_all 不会 ALTER）。"""
    alters = [
        ("buyer_contact_name", "VARCHAR(128) NULL COMMENT '项目联系人'"),
        ("buyer_phone", "VARCHAR(64) NULL COMMENT '项目联系电话'"),
        ("buyer_address", "VARCHAR(512) NULL COMMENT '采购人/项目地址'"),
        ("deal_supplier_phone", "VARCHAR(64) NULL COMMENT '成交供应商电话'"),
        ("deal_supplier_address", "VARCHAR(512) NULL COMMENT '成交供应商地址'"),
    ]
    with engine.begin() as conn:
        existing = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'notice_parsed'"
                )
            )
        }
        if not existing:
            return
        for col, ddl in alters:
            if col in existing:
                continue
            conn.execute(text(f"ALTER TABLE notice_parsed ADD COLUMN {col} {ddl}"))


def _apply_table_comments() -> None:
    """已有表补全备注（CREATE IF NOT EXISTS 不会改注释）。"""
    from pathlib import Path

    sql_path = Path(__file__).resolve().parent / "sql" / "migrate_table_comments.sql"
    if not sql_path.exists():
        return
    raw = sql_path.read_text(encoding="utf-8")
    statements: list[str] = []
    buf: list[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("--"):
            continue
        buf.append(line)
        if s.endswith(";"):
            statements.append("\n".join(buf))
            buf = []
    with engine.begin() as conn:
        for stmt in statements:
            try:
                conn.execute(text(stmt))
            except Exception:  # noqa: BLE001
                # 某列尚未建出时跳过，避免整段失败
                continue


# 列表/筛选加速索引：(表名, 索引名, 列定义)
LIST_INDEXES: tuple[tuple[str, str, str], ...] = (
    ("notice_raw", "idx_raw_site_id", "site_id, id"),
    ("notice_raw", "idx_raw_site_notice_type", "site_id, notice_type"),
    ("notice_raw", "idx_raw_region", "region_name"),
    ("notice_raw", "idx_raw_parse_site", "parse_status, site_id, id"),
    ("notice_raw", "idx_raw_publish_id", "publish_time, id"),
    ("notice_parsed", "idx_parsed_site_kind", "site_id, notice_kind"),
    ("notice_parsed", "idx_parsed_region", "region_name"),
    ("notice_parsed", "idx_parsed_project_name", "project_name(191)"),
    ("notice_parsed", "idx_parsed_end_time", "end_time"),
    ("notice_parsed", "idx_parsed_start_time", "start_time"),
    ("notice_parsed", "idx_parsed_site_project", "site_id, project_code"),
    ("notice_parsed", "idx_parsed_publish_time", "publish_time"),
    ("notice_parsed", "idx_parsed_publish_raw", "publish_time, notice_raw_id"),
    ("notice_goods", "idx_goods_raw_product", "notice_raw_id, product_name(191)"),
)


def ensure_list_indexes(*, dry_run: bool = False) -> list[str]:
    """为公告列表查询补索引；已存在则跳过。返回本次新建的索引名。"""
    created: list[str] = []
    with engine.begin() as conn:
        existing = {
            (row[0], row[1])
            for row in conn.execute(
                text(
                    "SELECT TABLE_NAME, INDEX_NAME FROM information_schema.STATISTICS "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME IN ('notice_raw', 'notice_parsed', 'notice_goods')"
                )
            )
        }
        tables = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT TABLE_NAME FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME IN ('notice_raw', 'notice_parsed', 'notice_goods')"
                )
            )
        }
        for table, index_name, cols in LIST_INDEXES:
            if table not in tables:
                continue
            if (table, index_name) in existing:
                continue
            label = f"{table}.{index_name}"
            if dry_run:
                created.append(label)
                continue
            conn.execute(text(f"ALTER TABLE `{table}` ADD INDEX `{index_name}` ({cols})"))
            created.append(label)
    return created


def init_db() -> None:
    Base.metadata.create_all(engine)
    _ensure_parsed_columns()
    _apply_table_comments()
    ensure_list_indexes()


def get_session() -> Session:
    return SessionLocal()


def dumps(obj: Any) -> Any:
    """Ensure JSON-serializable structures for MySQL JSON columns."""
    return json.loads(json.dumps(obj, ensure_ascii=False, default=str))


def raw_exists(session: Session, site_id: str, notice_key: str) -> bool:
    row_id = session.execute(
        select(NoticeRaw.id).where(NoticeRaw.site_id == site_id, NoticeRaw.notice_key == notice_key)
    ).scalar_one_or_none()
    return row_id is not None


def upsert_raw(
    session: Session,
    *,
    site_id: str,
    notice_key: str,
    auction_type: Optional[str] = None,
    notice_type: Optional[str] = None,
    title: Optional[str] = None,
    region_name: Optional[str] = None,
    publish_time: Optional[datetime] = None,
    list_json: Any = None,
    detail_json: Any = None,
    content_html: Optional[str] = None,
    content_text: Optional[str] = None,
    source_url: Optional[str] = None,
    crawl_status: Optional[str] = None,
    error_message: Optional[str] = None,
) -> NoticeRaw:
    row = session.execute(
        select(NoticeRaw).where(NoticeRaw.site_id == site_id, NoticeRaw.notice_key == notice_key)
    ).scalar_one_or_none()
    if row is None:
        row = NoticeRaw(site_id=site_id, notice_key=notice_key)
        session.add(row)

    if auction_type is not None:
        row.auction_type = str(auction_type)
    if notice_type is not None:
        row.notice_type = str(notice_type)
    if title is not None:
        row.title = title[:512]
    if region_name is not None:
        row.region_name = region_name[:128]
    if publish_time is not None:
        row.publish_time = publish_time
    if list_json is not None:
        row.list_json = dumps(list_json)
    if detail_json is not None:
        row.detail_json = dumps(detail_json)
        row.detail_at = now_shanghai()
    if content_html is not None:
        row.content_html = content_html
    if content_text is not None:
        row.content_text = content_text
    if source_url is not None:
        row.source_url = source_url[:1024]
    if crawl_status is not None:
        row.crawl_status = crawl_status
    if error_message is not None:
        row.error_message = error_message[:1000]
    row.updated_at = now_shanghai()
    session.flush()
    return row


def save_cursor(
    session: Session,
    site_id: str,
    cursor_key: str,
    last_page: int,
    last_total: Optional[int] = None,
    extra: Any = None,
) -> None:
    row = session.execute(
        select(CrawlCursor).where(CrawlCursor.site_id == site_id, CrawlCursor.cursor_key == cursor_key)
    ).scalar_one_or_none()
    if row is None:
        row = CrawlCursor(site_id=site_id, cursor_key=cursor_key)
        session.add(row)
    row.last_page = last_page
    row.last_total = last_total
    row.last_success_at = now_shanghai()
    if extra is not None:
        row.extra_json = dumps(extra)
    session.flush()


def exists_mall_customer(session: Session, platform_id: str) -> bool:
    if not platform_id:
        return False
    row_id = session.execute(
        select(MallCustomer.id).where(MallCustomer.platform_customer_id == platform_id)
    ).scalar_one_or_none()
    return row_id is not None


def upsert_mall_customer(session: Session, data: dict) -> MallCustomer:
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("缺少公司名称")
    row = session.execute(select(MallCustomer).where(MallCustomer.name == name)).scalar_one_or_none()
    now = now_shanghai()
    if row is None:
        row = MallCustomer(name=name, crawled_at=now)
        session.add(row)
    for key in (
        "platform_customer_id",
        "type",
        "address",
        "province",
        "city",
        "license",
        "license_code",
        "business_scope",
        "enter_time",
        "legal_person",
        "mobile",
        "new_mobile",
        "email",
        "origin",
        "agent_shop_product_number",
    ):
        if key in data and data[key] is not None:
            setattr(row, key, data[key])
    if data.get("list_json") is not None:
        row.list_json = dumps(data["list_json"])
    if data.get("store_json") is not None:
        row.store_json = dumps(data["store_json"])
    row.updated_at = now
    if row.crawled_at is None:
        row.crawled_at = now
    session.flush()
    return row


def ping() -> str:
    with engine.connect() as conn:
        return str(conn.execute(text("SELECT 1")).scalar())
