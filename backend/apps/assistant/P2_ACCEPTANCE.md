# P2 验收记录 — 本地轻量模型适配与降级

日期：2026-10-29  
分支：`feature/assistant-v1.1`

## 实现摘要

- `llm_adapter`：OpenAI-compatible `/v1/chat/completions` + `/models` 探活；单并发锁；超时降级
- `intent_router`：规则优先 → LLM JSON Schema 校验 → 白名单工具；未知工具拒绝
- `context_manager`：裁剪会话上下文后再送给模型
- `orchestrator` 按权限过滤可调用工具；响应 `mode`=`rule_only|llm_assisted|degraded`
- 生产默认不启模型：`ASSISTANT_LLM_ENABLED=false`

## 配置（示例）

```env
ASSISTANT_ENABLED=true
ASSISTANT_LLM_ENABLED=false
ASSISTANT_LLM_BASE_URL=http://host.docker.internal:8080/v1
ASSISTANT_LLM_MODEL=
ASSISTANT_LLM_TIMEOUT=20
ASSISTANT_LLM_MAX_OUTPUT_TOKENS=384
ASSISTANT_FALLBACK_ENABLED=true
```

Docker 内勿写容器自身的 `127.0.0.1` 指向宿主机模型。

## 测试命令与结果

```bash
cd backend
$env:USE_SQLITE='1'
python manage.py test apps.assistant.tests --verbosity=1
```

真实 1.5B～4B Q4 模型需本机另起 llama.cpp/Ollama；本期以替身验证安全链路，不默认下载大模型。

## 已知问题

- 未在本机实测具体 GGUF 延迟；上线前需用目标硬件跑 `smoke`。
- 模型输出若缺 `response_format` 支持，依赖 JSON 围栏解析回退。
