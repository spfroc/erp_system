# P0 验收记录 — 源码适配与业务服务抽取

## 分支

`feature/assistant-v1.1`（基于与 `origin/main` 一致的 `ae2f4e6`）

## 变更摘要

- 新增 Django App `apps.assistant`（模型 / 迁移 / 工具注册 / 执行器）
- 公告查询封装 `services/notice_query.py`，复用 `query_crawled_notices` 与详情序列化
- 静态注册 V1.1 必选工具（公告/商品/采购人/成交/ERP/导航/运维状态）
- 权限目录同步：`assistant.view|use|manage`
- API：`GET /api/assistant/status/`、`GET /api/assistant/tools/`（chat 占位 501）

## 测试命令

```bash
cd backend
# 本地无 MySQL 时用 SQLite（仅跑 SimpleTestCase，不建库）
set USE_SQLITE=1
python manage.py test apps.assistant.tests.test_tool_registry -v 2
```

## 测试结果

```text
Ran 7 tests in 0.002s
OK
- 11 个必选工具已注册
- 缺 assistant.use / 业务权限 → forbidden
- 未知工具 → unknown_tool
- navigation.find 在授权下可执行并写审计落库调用（mock）
```

## 已知问题

- `chat` 编排、会话 CRUD、前端页面在 P1
- LLM Adapter / 模型探测在 P2（status.llm.online 固定 false）
- 写操作确认链在 P3
- data_store 迁移图原有双叶节点，`0029_assistant_permissions` 合并依赖

## 验收标准对照

| 标准 | 状态 |
|---|---|
| 工具可独立测试 | 是 |
| 不复制公告 SQL | 是（调用 query_crawled_notices） |
| 不引入独立业务库 | 是（共用 MySQL） |
| 模型默认不加载 | 是 |
