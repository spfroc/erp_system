# 政府采购公告抓取（Python）

覆盖站点见 `docs/notice-sites-api.md`：

| site_id | 说明 |
|---------|------|
| `sd-ggzyjyzx` | 山东网上商城采购公告（全省） |
| `jd-quan-yicai` | 京东泉易采（普通竞价/反拍/询比）+ 附件 |

## 数据流

```
接口列表 → notice_raw(list_json)
     ↓
接口详情 → notice_raw(detail_json, content_html/text)   【原始数据完整保留】
     ↓
LLM 解析 → notice_parsed（项目编号、采购单位、成交金额、商品、报价名单…）
     ↓（京东）
附件下载 → notice_attachment(local_path, extracted_text)
     ↓
附件 LLM → notice_attachment.parsed_json
```

## 库表

见 `sql/schema.sql`：

- `notice_raw`：原始列表/详情/HTML
- `notice_parsed`：模型抽取关键字段 + `goods_json` / `quotes_json`
- `notice_attachment`：附件文件与解析
- `crawl_cursor`：分页游标
- `mall_customer`：山东商城供应商（TouchCustomer）

## 准备

```bash
cd notice_crawler
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
# 编辑 NOTICE_DB_URL / JD_CONTRACT_NUM
```

### 本地模型（默认 `EXTRACTOR_BACKEND=local_gguf`）

本机无 GPU 时推荐 GGUF + `llama-cpp-python`（CPU）：

```bash
bash scripts/download_gguf.sh
# 默认落到 models/qwen2.5-1.5b-instruct-q4_k_m.gguf

# 冒烟：加载模型并抽一条样例
python scripts/smoke_local_model.py
```

`.env` 关键项：

| 变量 | 说明 |
|------|------|
| `EXTRACTOR_BACKEND` | `local_gguf` / `local_hf` / `heuristic` / `api` |
| `LOCAL_MODEL_PATH` | `.gguf` 或 HF 权重目录 |
| `LOCAL_N_GPU_LAYERS` | GPU 层数，CPU 填 `0` |
| `LOCAL_N_CTX` | 上下文长度，默认 4096 |

有 NVIDIA 时可把 `LOCAL_N_GPU_LAYERS=-1`（全部上卡），并安装带 CUDA 的 `llama-cpp-python`。  
改走云端时：`EXTRACTOR_BACKEND=api` 并配置 `LLM_*`。

MySQL 可先执行：

```bash
mysql -h ... -u ... -p < sql/schema.sql
```

或：

```bash
python cli.py init-db
python cli.py ping
```

## 常用命令

```bash
# 调试：每个类型只抓 1 页
python cli.py crawl --site sd-mall --max-pages 1 --page-size 10
python cli.py crawl --site jd --max-pages 1

# 按日期增量：商城走接口 startDate/endDate；京东按创建时间倒序截断
# 同一类型连续 5 条已在库中则停止该类
python cli.py crawl --site all --start-date 2026-10-01 --end-date 2026-10-16 --stop-dup 5

# 全量（慎用，数据量大）
python cli.py crawl --site all

# 抓取时会顺带解析（商城走 HTML 表格规则，无需再单独 parse）
python cli.py crawl --site sd-mall --max-pages 1

# 仅补解析已抓未解析的历史数据时才用 parse
python cli.py parse --site sd-ggzyjyzx --limit 100

# 结构化字段补洞（接口自带的 endTime/预算等）
python cli.py enrich --limit 500

# 京东附件（正文常在 PDF 里）
python cli.py download-att --site jd-quan-yicai --limit 20
python cli.py parse-att --site jd-quan-yicai --limit 20

# 供应商（vip-rebuild TouchCustomer）：写入 mall_customer
# 流程对齐 QlycLoginService：账号密码登录拿 access_token → 本地 js/decode.js 解密列表
cd js && npm install && cd ..
# .env 填 SD_ACCOUNT / SD_PASSWORD
python cli.py login-qlyc
python cli.py crawl-supplier --type 2 --max-pages 1 --page-size 50
```

## 解析字段（notice_parsed）

- 项目：编号、名称、采购单位、联系人 / 电话 / 地址、区域、预算、公告种类、采购方式、发布/开始/截止时间、交货地址
- 成交：供应商名称 / 电话 / 地址、成交金额、报价家数、报价名单
- 产品表 `notice_goods`（一对多）：名称、分类、数量、单位、品牌、型号、单价、参数、金额小计

**主路径是本地模型**（`EXTRACTOR_BACKEND=local_gguf`）：公告版式不固定时靠模型抽 JSON，规则只作兜底/补洞。  
CPU 上 1.5B 大约每条几十秒～两分钟；有 GPU 可设 `LOCAL_N_GPU_LAYERS=-1`。  
云端时改 `EXTRACTOR_BACKEND=api` 并配置 `LLM_*`。

## 注意

1. 山东商城全省抓取：**不要**在列表 Body 里写死 `regionGuidList=["1487001"]`。
2. 京东必须 `curl_cffi` 伪装，且带 `contractNum` + `appSource` + `businessType`。
3. 询比公告 `noticeType=5`（不是竞价的 1）。
4. 先 `--max-pages 1` 验证，再放开全量。
