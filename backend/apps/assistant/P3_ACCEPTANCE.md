# P3 验收记录 — 受控写操作确认链

日期：2026-10-29  
分支：`feature/assistant-v1.1`

## 实现摘要

- 新增工具 `devops.run_safe_job`（`requires_confirmation=True`，权限 `dev.ops.manage`）
- 助手仅允许执行脚本白名单：`tag_notice_results`
- 采集/全量/外部系统任务返回导航入口，不自动执行
- 确认链：预览 → `confirmation_token`（仅客户端一次）→ 服务端哈希校验 → 二次权限校验 → 真实 `enqueue_job_run` → 审计落库
- API：`GET/POST /api/assistant/actions/{id}/`、`.../confirm/`
- 前端：`tool_preview` 卡片「确认执行」

## 测试命令与结果

```bash
cd backend
$env:USE_SQLITE='1'
python manage.py test apps.assistant.tests --verbosity=1
# → Ran 27 tests … OK
```

## 已知问题

- Celery 未启动时入队会失败并写失败审计，属预期。
- 仅开放一个安全任务；扩展需显式加入 `ASSISTANT_SAFE_SCRIPT_KEYS`。
