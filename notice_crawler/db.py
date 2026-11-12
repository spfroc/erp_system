from __future__ import annotations

import json
import random
import time
from typing import Any, Callable, Optional

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
    or_,
    select,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from datetime import datetime

from config import settings
from utils import now as now_shanghai, strip_surrogates


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
        String(256),
        nullable=False,
        comment="站点内唯一键 noticeGuid/auctionNo+noticeType/ccgp加密id",
    )
    auction_type = Column(String(32), comment="站点侧采购方式编码")
    notice_type = Column(String(32), comment="站点侧公告类型编码")
    title = Column(String(512), comment="公告标题")
    region_name = Column(String(128), comment="区域名称（地市短名）")
    district_name = Column(String(128), comment="区县名称")
    region_guid = Column(String(64), comment="区域编号 regionGuid")
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
    notice_key = Column(String(256), nullable=False, comment="公告唯一键")
    project_code = Column(String(128), comment="项目编号")
    project_name = Column(String(512), comment="项目名称")
    notice_title = Column(String(512), comment="公告标题")
    buyer_name = Column(String(256), comment="采购单位")
    buyer_contact_name = Column(String(128), comment="项目联系人")
    buyer_phone = Column(String(64), comment="项目联系电话")
    buyer_address = Column(String(512), comment="采购人/项目地址")
    buyer_contact = Column(String(256), comment="兼容：联系人/电话合并")
    region_name = Column(String(128), comment="区域名称（地市短名）")
    district_name = Column(String(128), comment="区县名称")
    region_guid = Column(String(64), comment="区域编号 regionGuid")
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
    notice_key = Column(String(256), nullable=False, comment="公告唯一键")
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
    notice_key = Column(String(256), nullable=False, comment="公告唯一键")
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
    signed = Column(String(32), default="0", comment="状态 0有效 1已签约 2无效")
    tag = Column(String(191), comment="标签")
    sell_id = Column(Integer, default=0, comment="旧系统销售 id")
    sell_user_id = Column(String(64), comment="ERP 负责人用户 id")
    sell_user_name = Column(String(128), comment="ERP 负责人姓名")
    remark = Column(Text, comment="备注")
    agent_shop_product_number = Column(Integer, comment="代理商/经销商店铺商品数量")
    online_shop_product_number = Column(Integer, comment="电商店铺商品数量")
    manufacturer_shop_product_number = Column(Integer, comment="厂商店铺商品数量")
    entering_origin = Column(Integer, default=0, comment="录入来源 0平台抓取 >0用户录入")
    legacy_customer_id = Column(BigInteger, comment="旧 customers.id")
    list_json = Column(JSON, comment="列表原始条目")
    store_json = Column(JSON, comment="店铺详情")
    crawled_at = Column(DateTime, default=now_shanghai, comment="首次抓取时间")
    updated_at = Column(
        DateTime, default=now_shanghai, onupdate=now_shanghai, comment="更新时间"
    )


# READ COMMITTED：避免 REPEATABLE READ 的间隙锁。
# 多个抓取进程同时 DELETE+INSERT notice_goods 时，间隙锁会互相死锁。
engine = create_engine(
    settings.db_url,
    pool_pre_ping=True,
    future=True,
    isolation_level="READ COMMITTED",
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)

_LOCK_MYSQL_CODES = {1205, 1213}


def is_lock_conflict_message(message: Optional[str]) -> bool:
    text_value = message or ""
    return "Deadlock found" in text_value or "Lock wait timeout" in text_value


def is_lock_conflict(exc: BaseException) -> bool:
    """InnoDB 死锁 (1213) 或锁等待超时 (1205)。调用方应回滚后重试。"""
    seen: set[int] = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        orig = getattr(current, "orig", None)
        args = getattr(orig, "args", None) or ()
        if args and args[0] in _LOCK_MYSQL_CODES:
            return True
        if is_lock_conflict_message(str(current)):
            return True
        current = current.__cause__ or current.__context__
    return False


def commit_with_retry(session: Session, write: Callable[[], Any], *, attempts: int = 5) -> Any:
    """执行写入并提交。死锁时回滚并整段重做，避免把公告标成永久失败。"""
    delay = 0.05
    last: Optional[BaseException] = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            result = write()
            session.commit()
            return result
        except Exception as exc:
            last = exc
            session.rollback()
            if attempt >= attempts or not is_lock_conflict(exc):
                raise
            time.sleep(delay + random.random() * delay)
            delay = min(delay * 2, 1.0)
    if last is not None:
        raise last
    return None


def _ensure_table_columns(table: str, alters: list[tuple[str, str]]) -> None:
    """已有表时补齐新增列（create_all 不会 ALTER）。"""
    with engine.begin() as conn:
        existing = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table"
                ),
                {"table": table},
            )
        }
        if not existing:
            return
        for col, ddl in alters:
            if col in existing:
                continue
            conn.execute(text(f"ALTER TABLE `{table}` ADD COLUMN `{col}` {ddl}"))


def _ensure_parsed_columns() -> None:
    """已有 notice_parsed 时补齐新增列（create_all 不会 ALTER）。"""
    _ensure_table_columns(
        "notice_parsed",
        [
            ("buyer_contact_name", "VARCHAR(128) NULL COMMENT '项目联系人'"),
            ("buyer_phone", "VARCHAR(64) NULL COMMENT '项目联系电话'"),
            ("buyer_address", "VARCHAR(512) NULL COMMENT '采购人/项目地址'"),
            ("deal_supplier_phone", "VARCHAR(64) NULL COMMENT '成交供应商电话'"),
            ("deal_supplier_address", "VARCHAR(512) NULL COMMENT '成交供应商地址'"),
            ("district_name", "VARCHAR(128) NULL COMMENT '区县名称'"),
            ("region_guid", "VARCHAR(64) NULL COMMENT '区域编号 regionGuid'"),
        ],
    )


def _ensure_raw_region_columns() -> None:
    """notice_raw 补齐区县 / regionGuid。"""
    _ensure_table_columns(
        "notice_raw",
        [
            ("district_name", "VARCHAR(128) NULL COMMENT '区县名称'"),
            ("region_guid", "VARCHAR(64) NULL COMMENT '区域编号 regionGuid'"),
        ],
    )


def _ensure_notice_key_width() -> None:
    """ccgp 加密 id 超过原 128，统一加宽到 256。"""
    tables = ("notice_raw", "notice_parsed", "notice_goods", "notice_attachment")
    with engine.begin() as conn:
        for table in tables:
            row = conn.execute(
                text(
                    "SELECT CHARACTER_MAXIMUM_LENGTH FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table "
                    "AND COLUMN_NAME = 'notice_key'"
                ),
                {"table": table},
            ).first()
            if not row:
                continue
            length = int(row[0] or 0)
            if length >= 256:
                continue
            conn.execute(
                text(
                    f"ALTER TABLE `{table}` MODIFY COLUMN `notice_key` "
                    "VARCHAR(256) NOT NULL COMMENT '公告唯一键'"
                )
            )
    with engine.begin() as conn:
        existing = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT INDEX_NAME FROM information_schema.STATISTICS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'notice_raw'"
                )
            )
        }
        for index_name, cols in (
            ("idx_raw_district", "district_name"),
            ("idx_raw_region_guid", "region_guid"),
        ):
            if index_name in existing:
                continue
            try:
                conn.execute(text(f"ALTER TABLE notice_raw ADD INDEX `{index_name}` ({cols})"))
            except Exception:  # noqa: BLE001
                continue


def _ensure_mall_customer_columns() -> None:
    """已有 mall_customer 时补齐资料库展示字段。"""
    _ensure_table_columns(
        "mall_customer",
        [
            ("signed", "VARCHAR(32) DEFAULT '0' COMMENT '状态 0有效 1已签约 2无效'"),
            ("tag", "VARCHAR(191) NULL COMMENT '标签'"),
            ("sell_id", "INT DEFAULT 0 COMMENT '旧系统销售 id'"),
            ("sell_user_id", "VARCHAR(64) NULL COMMENT 'ERP 负责人用户 id'"),
            ("sell_user_name", "VARCHAR(128) NULL COMMENT 'ERP 负责人姓名'"),
            ("remark", "TEXT NULL COMMENT '备注'"),
            ("online_shop_product_number", "INT NULL COMMENT '电商店铺商品数量'"),
            ("manufacturer_shop_product_number", "INT NULL COMMENT '厂商店铺商品数量'"),
            ("entering_origin", "INT DEFAULT 0 COMMENT '录入来源 0平台抓取 >0用户录入'"),
            ("legacy_customer_id", "BIGINT NULL COMMENT '旧 customers.id'"),
        ],
    )
    with engine.begin() as conn:
        existing = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT INDEX_NAME FROM information_schema.STATISTICS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'mall_customer'"
                )
            )
        }
        for index_name, cols in (
            ("idx_signed", "signed"),
            ("idx_origin", "origin"),
            ("idx_legacy_customer_id", "legacy_customer_id"),
            ("idx_mall_customer_crawled_at", "crawled_at"),
        ):
            if index_name in existing:
                continue
            try:
                conn.execute(text(f"ALTER TABLE mall_customer ADD INDEX `{index_name}` ({cols})"))
            except Exception:  # noqa: BLE001
                continue


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
    ("notice_raw", "idx_raw_site_publish", "site_id, publish_time"),
    ("notice_parsed", "idx_parsed_site_kind", "site_id, notice_kind"),
    ("notice_parsed", "idx_parsed_site_publish", "site_id, publish_time"),
    ("notice_parsed", "idx_parsed_region", "region_name"),
    ("notice_parsed", "idx_parsed_project_name", "project_name(191)"),
    ("notice_parsed", "idx_parsed_end_time", "end_time"),
    ("notice_parsed", "idx_parsed_start_time", "start_time"),
    ("notice_parsed", "idx_parsed_site_project", "site_id, project_code"),
    ("notice_parsed", "idx_parsed_publish_time", "publish_time"),
    ("notice_parsed", "idx_parsed_publish_raw", "publish_time, notice_raw_id"),
    (
        "notice_parsed",
        "idx_parsed_stats_cover",
        "publish_time, site_id, notice_kind, budget_amount, deal_amount",
    ),
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
    _ensure_raw_region_columns()
    _ensure_notice_key_width()
    _ensure_mall_customer_columns()
    _apply_table_comments()
    ensure_list_indexes()


def get_session() -> Session:
    return SessionLocal()


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, str):
        return strip_surrogates(obj)
    if isinstance(obj, dict):
        return {
            strip_surrogates(key) if isinstance(key, str) else key: _json_safe(value)
            for key, value in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [_json_safe(value) for value in obj]
    return obj


def dumps(obj: Any) -> Any:
    """Ensure JSON-serializable structures for MySQL JSON columns."""
    return json.loads(json.dumps(_json_safe(obj), ensure_ascii=False, default=str))


def raw_exists(session: Session, site_id: str, notice_key: str) -> bool:
    row_id = session.execute(
        select(NoticeRaw.id).where(NoticeRaw.site_id == site_id, NoticeRaw.notice_key == notice_key)
    ).scalar_one_or_none()
    return row_id is not None


def notice_already_stored(session: Session, site_id: str, notice_key: str) -> bool:
    """已入库且不需要再拉详情。死锁写成的 detail_fail 视为未完成，下一轮重抓。"""
    row = session.execute(
        select(NoticeRaw.crawl_status, NoticeRaw.error_message).where(
            NoticeRaw.site_id == site_id,
            NoticeRaw.notice_key == notice_key,
        )
    ).first()
    if row is None:
        return False
    status, message = row[0], row[1]
    if status == "detail_fail" and is_lock_conflict_message(message):
        return False
    return True


def find_ccgp_raw(
    session: Session,
    *,
    notice_key: str,
    title: Optional[str] = None,
    publish_time: Optional[datetime] = None,
    notice_type: Optional[str] = None,
) -> Optional["NoticeRaw"]:
    """山东政采查重：先稳定 notice_key，再兼容旧版不稳定 id hash（按标题+发布时间+类型）。"""
    row = session.execute(
        select(NoticeRaw).where(NoticeRaw.site_id == "sd-ccgp", NoticeRaw.notice_key == notice_key)
    ).scalar_one_or_none()
    if row is not None:
        return row

    title_text = (title or "").strip()
    kind = (notice_type or "").strip()
    if not title_text or publish_time is None or not kind:
        return None

    # 标题空白差异：SQL 侧先按发布时间+类型收窄，再在 Python 里归一化比对
    candidates = session.execute(
        select(NoticeRaw)
        .where(
            NoticeRaw.site_id == "sd-ccgp",
            NoticeRaw.notice_type == kind,
            NoticeRaw.publish_time == publish_time,
        )
        .order_by(NoticeRaw.id.asc())
    ).scalars().all()
    if not candidates:
        return None

    import re

    needle = re.sub(r"\s+", "", title_text)
    for item in candidates:
        if re.sub(r"\s+", "", (item.title or "").strip()) == needle:
            return item
    return None


_PROJECT_CODE_PATTERNS = (
    # 标题 【SDGP…】
    r"【((?:SDGP|SDKJXY|SCJJ|ECJJ|SCDZ)[\w\-]+)】",
    # 正文 项目编号：SDGP…
    r"(?:采购)?项目编号\s*[:：]?\s*((?:SDGP|SDKJXY|SCJJ|ECJJ|SCDZ)[\w\-]+)",
    r"项目(?:采购)?编号\s*[:：]?\s*((?:SDGP|SDKJXY|SCJJ|ECJJ|SCDZ)[\w\-]+)",
    # 兜底裸编号
    r"\b((?:SDGP|SDKJXY|SCJJ|ECJJ|SCDZ)[A-Z0-9_\-]{8,})\b",
)


def extract_project_code(*texts: Optional[str]) -> Optional[str]:
    """从标题/正文抽出政府采购项目编号。"""
    import re

    for raw in texts:
        blob = (raw or "").strip()
        if not blob:
            continue
        for pattern in _PROJECT_CODE_PATTERNS:
            m = re.search(pattern, blob, flags=re.I)
            if m:
                return m.group(1).strip()
    return None


def mall_has_project_code(session: Session, project_code: str) -> bool:
    """网上商城（sd-ggzyjyzx）是否已有同项目编号公告。"""
    code = (project_code or "").strip()
    if not code:
        return False
    found = session.execute(
        select(NoticeParsed.id)
        .join(NoticeRaw, NoticeRaw.id == NoticeParsed.notice_raw_id)
        .where(
            NoticeRaw.site_id == "sd-ggzyjyzx",
            NoticeParsed.project_code == code,
        )
        .limit(1)
    ).scalar_one_or_none()
    if found is not None:
        return True
    # 商城刚入库尚未 parse 时，用标题/正文兜底
    found = session.execute(
        select(NoticeRaw.id)
        .where(
            NoticeRaw.site_id == "sd-ggzyjyzx",
            or_(
                NoticeRaw.title.contains(code),
                NoticeRaw.content_text.contains(code),
            ),
        )
        .limit(1)
    ).scalar_one_or_none()
    return found is not None


def upsert_raw(
    session: Session,
    *,
    site_id: str,
    notice_key: str,
    auction_type: Optional[str] = None,
    notice_type: Optional[str] = None,
    title: Optional[str] = None,
    region_name: Optional[str] = None,
    district_name: Any = ...,
    region_guid: Any = ...,
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
    if district_name is not ...:
        text = (str(district_name).strip() if district_name is not None else "")
        row.district_name = text[:128] or None
    if region_guid is not ...:
        text = str(region_guid or "").strip()
        row.region_guid = text[:64] or None
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


def backfill_district_from_list_json(*, limit: int | None = None, batch: int = 500) -> int:
    """从 list_json/detail_json 回填 district_name / region_guid（已有数据）。"""
    from utils import extract_district_name

    _ensure_raw_region_columns()
    _ensure_parsed_columns()
    session = SessionLocal()
    updated = 0
    try:
        stmt = (
            select(NoticeRaw)
            .where(
                NoticeRaw.list_json.isnot(None),
                or_(NoticeRaw.district_name.is_(None), NoticeRaw.region_guid.is_(None)),
            )
            .order_by(NoticeRaw.id)
        )
        if limit:
            stmt = stmt.limit(limit)
        rows = list(session.execute(stmt).scalars())
        for i, raw in enumerate(rows, 1):
            list_item = raw.list_json if isinstance(raw.list_json, dict) else {}
            detail = raw.detail_json if isinstance(raw.detail_json, dict) else {}
            raw_region = (
                detail.get("regionFullName")
                or detail.get("regionName")
                or list_item.get("regionFullName")
                or list_item.get("regionName")
            )
            guid = (
                detail.get("regionGuid")
                or list_item.get("regionGuid")
                or detail.get("regionId")
                or list_item.get("regionId")
            )
            changed = False
            if not raw.district_name:
                district = extract_district_name(raw_region)
                if district:
                    raw.district_name = district[:128]
                    changed = True
            if not raw.region_guid and guid:
                raw.region_guid = str(guid).strip()[:64]
                changed = True
            if changed:
                updated += 1
            if i % batch == 0:
                session.commit()
        session.commit()

        # 同步到已解析行
        parsed_rows = list(
            session.execute(
                select(NoticeParsed).where(
                    or_(NoticeParsed.district_name.is_(None), NoticeParsed.region_guid.is_(None))
                )
            ).scalars()
        )
        raw_map = {
            r.id: r
            for r in session.execute(
                select(NoticeRaw).where(NoticeRaw.id.in_([p.notice_raw_id for p in parsed_rows] or [0]))
            ).scalars()
        }
        for parsed in parsed_rows:
            raw = raw_map.get(parsed.notice_raw_id)
            if not raw:
                continue
            changed = False
            if not parsed.district_name and raw.district_name:
                parsed.district_name = raw.district_name
                changed = True
            if not parsed.region_guid and raw.region_guid:
                parsed.region_guid = raw.region_guid
                changed = True
            if changed:
                updated += 1
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return updated


def exists_mall_customer(session: Session, platform_id: str) -> bool:
    if not platform_id:
        return False
    # 历史数据可能同 platform_customer_id 多行，只判断是否存在
    row_id = session.execute(
        select(MallCustomer.id)
        .where(MallCustomer.platform_customer_id == platform_id)
        .limit(1)
    ).scalar_one_or_none()
    return row_id is not None


def upsert_mall_customer(session: Session, data: dict) -> MallCustomer:
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("缺少公司名称")
    # 同名多行时取最早一条做更新，避免 MultipleResultsFound 中断全量抓取
    row = session.execute(
        select(MallCustomer).where(MallCustomer.name == name).order_by(MallCustomer.id.asc()).limit(1)
    ).scalar_one_or_none()
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
        "signed",
        "tag",
        "sell_id",
        "sell_user_id",
        "sell_user_name",
        "remark",
        "agent_shop_product_number",
        "online_shop_product_number",
        "manufacturer_shop_product_number",
        "entering_origin",
        "legacy_customer_id",
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
