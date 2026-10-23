-- 公告列表/筛选加速索引（已存在则跳过）
-- mysql ... < sql/migrate_list_indexes.sql

SET @db := DATABASE();

DROP PROCEDURE IF EXISTS add_notice_list_index;
DELIMITER $$
CREATE PROCEDURE add_notice_list_index(IN p_table VARCHAR(64), IN p_index VARCHAR(64), IN p_cols VARCHAR(255))
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.statistics
    WHERE table_schema = @db AND table_name = p_table AND index_name = p_index
  ) THEN
    SET @sql := CONCAT('ALTER TABLE `', p_table, '` ADD INDEX `', p_index, '` (', p_cols, ')');
    PREPARE stmt FROM @sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
  END IF;
END$$
DELIMITER ;

CALL add_notice_list_index('notice_raw', 'idx_raw_site_id', 'site_id, id');
CALL add_notice_list_index('notice_raw', 'idx_raw_site_notice_type', 'site_id, notice_type');
CALL add_notice_list_index('notice_raw', 'idx_raw_region', 'region_name');
CALL add_notice_list_index('notice_raw', 'idx_raw_parse_site', 'parse_status, site_id, id');

CALL add_notice_list_index('notice_parsed', 'idx_parsed_site_kind', 'site_id, notice_kind');
CALL add_notice_list_index('notice_parsed', 'idx_parsed_region', 'region_name');
CALL add_notice_list_index('notice_parsed', 'idx_parsed_project_name', 'project_name(191)');
CALL add_notice_list_index('notice_parsed', 'idx_parsed_end_time', 'end_time');
CALL add_notice_list_index('notice_parsed', 'idx_parsed_start_time', 'start_time');
CALL add_notice_list_index('notice_parsed', 'idx_parsed_site_project', 'site_id, project_code');

DROP PROCEDURE IF EXISTS add_notice_list_index;
