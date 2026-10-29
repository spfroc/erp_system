-- 补齐 mall_customer 资料库展示字段（CREATE IF NOT EXISTS 不会改已有表）
-- 用法：mysql ... < sql/migrate_mall_customer_library.sql
-- 或：python cli.py init-db（会调用 _ensure_mall_customer_columns）

ALTER TABLE mall_customer
  ADD COLUMN IF NOT EXISTS signed VARCHAR(32) DEFAULT '0' COMMENT '状态 0有效 1已签约 2无效',
  ADD COLUMN IF NOT EXISTS tag VARCHAR(191) DEFAULT NULL COMMENT '标签',
  ADD COLUMN IF NOT EXISTS sell_id INT DEFAULT 0 COMMENT '旧系统销售 id',
  ADD COLUMN IF NOT EXISTS sell_user_id VARCHAR(64) DEFAULT NULL COMMENT 'ERP 负责人用户 id',
  ADD COLUMN IF NOT EXISTS sell_user_name VARCHAR(128) DEFAULT NULL COMMENT 'ERP 负责人姓名',
  ADD COLUMN IF NOT EXISTS remark TEXT COMMENT '备注',
  ADD COLUMN IF NOT EXISTS online_shop_product_number INT DEFAULT NULL COMMENT '电商店铺商品数量',
  ADD COLUMN IF NOT EXISTS manufacturer_shop_product_number INT DEFAULT NULL COMMENT '厂商店铺商品数量',
  ADD COLUMN IF NOT EXISTS entering_origin INT DEFAULT 0 COMMENT '录入来源 0平台抓取 >0用户录入',
  ADD COLUMN IF NOT EXISTS legacy_customer_id BIGINT DEFAULT NULL COMMENT '旧 customers.id';

-- MySQL 8.0.12 前无 IF NOT EXISTS；下面索引用过程忽略重复
-- 索引（已存在则跳过由 Python ensure 处理）
