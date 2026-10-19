-- 在已有 yicai_erp.notice_parsed 上补列（可重复执行前请先检查）
-- 或直接: python cli.py init-db （会自动 ADD 缺失列）

ALTER TABLE notice_parsed
  ADD COLUMN IF NOT EXISTS buyer_contact_name VARCHAR(128) NULL COMMENT '项目联系人' AFTER buyer_name,
  ADD COLUMN IF NOT EXISTS buyer_phone VARCHAR(64) NULL COMMENT '项目联系电话' AFTER buyer_contact_name,
  ADD COLUMN IF NOT EXISTS buyer_address VARCHAR(512) NULL COMMENT '采购人/项目地址' AFTER buyer_phone,
  ADD COLUMN IF NOT EXISTS deal_supplier_phone VARCHAR(64) NULL COMMENT '成交供应商电话' AFTER deal_supplier,
  ADD COLUMN IF NOT EXISTS deal_supplier_address VARCHAR(512) NULL COMMENT '成交供应商地址' AFTER deal_supplier_phone;
