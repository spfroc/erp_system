# P1 验收记录 — 聊天工作台（规则模式真查询）

日期：2026-10-29  
分支：`feature/assistant-v1.1`

## 实现摘要

- 后端：`rule_router` → `orchestrator` → `tool_executor`；会话 CRUD + `POST /api/assistant/chat/`
- 前端：`AssistantPage` 工作台（会话、快捷词、结果卡片）；菜单「智能助手」挂到总览
- 权限：沿用 `assistant.view/use/manage`；工具仍二次校验业务权限
- 模式：`rule_only`（本阶段不调用 LLM）

## 变更文件（主要）

- `backend/apps/assistant/services/{rule_router,conversation,orchestrator}.py`
- `backend/apps/assistant/views.py` / `urls.py`
- `backend/apps/assistant/tools/notice_tools.py`（相对时间段）
- `backend/apps/data_store/nav_defaults.py` + `migrations/0030_assistant_nav.py`
- `frontend/src/assistant/*`
- `frontend/src/navCatalog.ts` / `App.tsx` / `styles.css`

## 测试命令与结果

```bash
cd backend
$env:USE_SQLITE='1'
python manage.py test apps.assistant.tests --verbosity=1
# → Ran 15 tests … OK

cd ../frontend
npx vitest run src/assistant/AssistantResultRenderer.test.tsx
# → Test Files 1 passed · Tests 2 passed
```

## 已知问题

- 本阶段无本地模型；复杂自由文本会要求澄清。
- 生产菜单需跑迁移 `0030_assistant_nav` 后才会写入 DB；未迁移前仍可从 `DEFAULT_NAV_ITEMS` 合并显示（取决于现有菜单加载逻辑）。
- ERP 订单「未完成」状态依赖关键词过滤，未与全部状态枚举逐一对齐。
