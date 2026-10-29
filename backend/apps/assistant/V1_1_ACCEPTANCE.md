# ERP 智能业务助手 V1.1 — 验收报告

日期：2026-10-29  
分支：`feature/assistant-v1.1`  
范围：管理后台可工作助手（非演示聊天页）；**未**部署生产、**未**默认下载大模型。

## 阶段提交

| 阶段 | Commit | 说明 |
|---|---|---|
| P0 | `465633c` / `7b9390e` | App、工具注册、权限、公告查询抽取 |
| P1 | `2774510` | 规则聊天 API、会话、React 工作台、菜单 |
| P2 | `be97435` | OpenAI-compatible LLM 意图、降级、上下文裁剪 |
| P3 | `facc325` | 安全任务确认执行与审计 |
| P4 | （本提交） | 场景测试与总验收 |

## 功能对照

| 验收项 | 状态 |
|---|---|
| 员工可进入智能助手 | 通过（菜单 `assistant` + `assistant.view`） |
| 自然语言查公告/商品/采购人 | 通过（规则工具 + 真实 ORM） |
| ERP 商品/订单查询 | 通过（字段白名单） |
| 功能导航 | 通过（`navigation.find`） |
| 多轮条件追加 | 通过（context + follow-up 规则） |
| 真实业务 API/服务复用 | 通过（`query_crawled_notices` / collection 模型） |
| 受控写操作 | 通过（`devops.run_safe_job` + 确认） |
| 本地小模型意图 | 已接入适配器；默认关闭，替身测通过 |
| 模型不可用降级 | 通过（`degraded` + 规则/快捷词仍可用） |
| 权限复用 | 通过（`assistant.*` + 业务权限二次校验） |
| 不影响采集/ERP | 通过（独立 App；模型不在 Gunicorn 加载） |

## 测试

### 后端

```bash
cd backend
$env:USE_SQLITE='1'
python manage.py test apps.assistant.tests --verbosity=1
```

结果：`Ran 36 tests … OK`（含场景 A–I 路由）。

### 前端

```bash
cd frontend
npx vitest run src/assistant/AssistantResultRenderer.test.tsx
```

结果：`Tests 3 passed`。

## 部署注意（非本期执行）

1. 迁移：`assistant` 初始表 + `0029_assistant_permissions` + `0030_assistant_nav`
2. 生产默认 `ASSISTANT_LLM_ENABLED=false`
3. Docker 模型地址用宿主机可达 URL，勿用容器内 `127.0.0.1`
4. 扩展可执行脚本前必须审阅副作用并写入 `ASSISTANT_SAFE_SCRIPT_KEYS`

## 已知限制

- 未在本机 i3 实测具体 1.5B～4B Q4 延迟；上线前需独立 smoke。
- 复杂自由文本在模型离线时需快捷词或更明确指令。
- 管理员跨用户会话审计未做（按需求 V1.1 不做）。
- 流式 SSE 未启用（WSGI Worker 占用评估后维持短请求）。
