-- 产品明细独立表；旧 goods_json 可保留不删，解析不再写入
-- 或直接: python cli.py init-db

CREATE TABLE IF NOT EXISTS notice_goods (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
  notice_raw_id     BIGINT UNSIGNED NOT NULL COMMENT '关联 notice_raw.id',
  notice_parsed_id  BIGINT UNSIGNED NULL COMMENT '关联 notice_parsed.id',
  site_id           VARCHAR(64)  NOT NULL COMMENT '站点标识',
  notice_key        VARCHAR(128) NOT NULL COMMENT '公告唯一键',
  line_no           INT NOT NULL DEFAULT 1 COMMENT '明细行号，从1开始',
  product_name      VARCHAR(512) NULL COMMENT '产品名称',
  category          VARCHAR(256) NULL COMMENT '产品分类',
  quantity          DECIMAL(18,4) NULL COMMENT '购买数量',
  unit              VARCHAR(64)  NULL COMMENT '计量单位',
  brand             VARCHAR(128) NULL COMMENT '品牌',
  model             VARCHAR(256) NULL COMMENT '型号',
  unit_price        DECIMAL(18,4) NULL COMMENT '单价',
  spec              VARCHAR(2000) NULL COMMENT '参数/规格',
  amount            DECIMAL(18,2) NULL COMMENT '金额小计',
  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  KEY idx_goods_raw (notice_raw_id),
  KEY idx_goods_parsed (notice_parsed_id),
  KEY idx_goods_site_key (site_id, notice_key),
  KEY idx_goods_name (product_name(191)),
  CONSTRAINT fk_goods_raw FOREIGN KEY (notice_raw_id) REFERENCES notice_raw(id) ON DELETE CASCADE,
  CONSTRAINT fk_goods_parsed FOREIGN KEY (notice_parsed_id) REFERENCES notice_parsed(id) ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='公告产品明细';
