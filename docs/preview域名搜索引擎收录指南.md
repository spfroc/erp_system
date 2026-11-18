# Preview 动态站纳入搜索爬虫操作指南

面向：老板 / 运营 / 站长  
更新日期：2026-11-18  
目的：在**保留正式静态站**的前提下，让搜索引擎抓取并评估三个品牌的 **preview 动态站**（含公告 SSR 页面），用于 SEO 验证；验证通过后再切换正式域名。

---

## 1. 域名对照

| 品牌 | 正式静态站（现行对外主站） | Preview 动态站（本次纳入爬虫） |
|------|----------------------------|--------------------------------|
| 齐鲁云采 / 壹采（qlyc） | https://www.qlyc.co | https://preview.qlyc.co |
| 壹采（yizhichan） | https://www.yizhichan.co | https://preview.yizhichan.co |
| 青慧采 | https://www.qinghuicai.cn | https://preview.qinghuicai.cn |

说明：

- Preview 与正式站内容同源品牌，但是**独立主机名**。
- 壹采另有历史预览地址 `https://yizhichan.qlyc.co`，请统一以 `preview.yizhichan.co` 为准提交，避免双域名分散权重。
- 客户门户 `https://portal.qlyc.co` **不纳入**本次官网收录范围。

---

## 2. 建议收录范围（验证期）

**优先收录（动态能力，SEO 重点验证）：**

- 首页：`/`
- 公告列表：`/notices`
- 公告详情：`/notices/{id}`
- 公告站点地图：`/sitemap-notices.xml`

**可一并提交：**

- 站点地图：`/sitemap.xml`
- robots：`/robots.txt`

**暂不作为验证重点：**

- 门户登录相关页面
- 仅内部调试、带参数的筛选长链（可抓取，但不必主动推送）

---

## 3. 各站需提交的地址清单

### 3.1 preview.qlyc.co

- 站点首页：https://preview.qlyc.co/
- robots：https://preview.qlyc.co/robots.txt
- 静态/综合 sitemap：https://preview.qlyc.co/sitemap.xml
- 公告 sitemap：https://preview.qlyc.co/sitemap-notices.xml
- 公告列表：https://preview.qlyc.co/notices

### 3.2 preview.yizhichan.co

- 站点首页：https://preview.yizhichan.co/
- robots：https://preview.yizhichan.co/robots.txt
- 静态/综合 sitemap：https://preview.yizhichan.co/sitemap.xml
- 公告 sitemap：https://preview.yizhichan.co/sitemap-notices.xml
- 公告列表：https://preview.yizhichan.co/notices

### 3.3 preview.qinghuicai.cn

- 站点首页：https://preview.qinghuicai.cn/
- robots：https://preview.qinghuicai.cn/robots.txt
- 静态/综合 sitemap：https://preview.qinghuicai.cn/sitemap.xml
- 公告 sitemap：https://preview.qinghuicai.cn/sitemap-notices.xml
- 公告列表：https://preview.qinghuicai.cn/notices

> 当前公告 sitemap 中的 `<loc>` 已是 preview 域名（例如 `https://preview.yizhichan.co/notices/378176`），适合作为动态页抓取入口。

---

## 4. 平台操作步骤

三个 preview 域名需**分别**添加为独立站点（不要只加 www）。

### 4.1 百度搜索资源平台（国内主渠道）

入口：https://ziyuan.baidu.com/

对每个 preview 域名重复：

1. **用户中心 → 站点管理 → 添加网站**  
   填写：`https://preview.xxx`（带 https，一般不加路径）。
2. **验证归属**（任选其一，推荐顺序）  
   - HTML 文件验证  
   - Meta 标签验证（需技术在首页 `<head>` 写入 `baidu-site-verification`）  
   - CNAME / 扫码等平台提供的方式  
3. 验证通过后进入该站点：  
   - **普通收录 → sitemap**：提交  
     - `https://preview.xxx/sitemap.xml`  
     - `https://preview.xxx/sitemap-notices.xml`  
   - **普通收录 → 手动提交 / API 提交**：先推送首页、`/notices`、若干条公告详情样例（各 5～20 条即可）  
4. 关注数据：索引量、抓取频次、抓取异常、死链。

### 4.2 Google Search Console

入口：https://search.google.com/search-console

1. 添加资源：选择「网址前缀」，填 `https://preview.xxx/`
2. 完成所有权验证（HTML 标签 / 文件 / DNS TXT）
3. **站点地图** 提交上述两个 sitemap URL
4. 用「网址检查」抽查：首页、公告列表、1～2 条详情，确认「可编入索引」
5. 观察：已编入索引、覆盖率、体验报告

### 4.3 必应 Webmaster Tools（可选，国际补充）

入口：https://www.bing.com/webmasters

1. 添加站点 `https://preview.xxx`
2. 验证后提交 sitemap
3. 可与 Google 共用部分验证文件（按平台提示）

### 4.4 360 / 搜狗（可选）

若公司有开通账号，按同样方式：

1. 添加 preview 站点并验证  
2. 提交 sitemap  
3. 抽查公告详情是否可抓取  

国内政企业务以**百度**为主，Google/必应作对照即可。

---

## 5. 验证清单（老板可按此验收）

每个 preview 域名勾选：

- [ ] HTTPS 正常打开，证书无浏览器警告  
- [ ] `/robots.txt` 返回 `Allow: /`（允许抓取）  
- [ ] `/sitemap-notices.xml` 可打开，且 `<loc>` 为 **preview 域名**  
- [ ] `/notices` 与任一公告详情页可打开，标题/描述正常  
- [ ] 百度站长已添加并验证该 preview 站点  
- [ ] 已提交 sitemap（综合 + 公告）  
- [ ] 已手动推送首页 + 公告列表 + 若干详情  
- [ ] 3～7 天后能在站长平台看到抓取/收录数据变化  

快速自检命令（技术可代跑）：

```bash
curl -sI https://preview.yizhichan.co/
curl -s  https://preview.yizhichan.co/robots.txt
curl -s  https://preview.yizhichan.co/sitemap-notices.xml | head
```

---

## 6. 与正式站的关系（务必知晓）

| 项目 | 正式 www 静态站 | Preview 动态站 |
|------|-----------------|----------------|
| 当前对外主入口 | 是 | 否（验证期） |
| 是否保留 | 验证通过前必须保留 | 验证通过后可承接正式流量 |
| 收录目的 | 维持现有关键词与老页面 | 验证动态页（尤其公告）SEO 表现 |
| 切换时机 | SEO 指标达标后再切 | 切到 www / 裸域后，preview 可降权或停收录 |

**风险说明：**

1. Preview 与 www 短期会并存两套可访问页面，搜索引擎可能视为相似内容。验证期可接受；正式切换后需用 301 / 统一 canonical 收敛。  
2. 当前部分 `robots.txt` 里的 Sitemap 行仍指向 **www** 域名；站长平台请**直接提交 preview 自己的 sitemap URL**（第 3 节），不要只依赖 robots 自动发现。  
3. 请勿在验证期把 preview 设为广告/对外主推唯一入口，避免用户书签与正式品牌域名混乱。

---

## 7. 技术侧配合事项（研发执行）

为让爬虫更顺畅发现 preview URL，建议研发完成：

1. **preview 的 robots.txt**  
   - Sitemap 改为指向本域：  
     - `Sitemap: https://preview.xxx/sitemap.xml`  
     - `Sitemap: https://preview.xxx/sitemap-notices.xml`  
2. **站长验证码**  
   - 在后台官网 SEO 配置或页面 `<head>` 写入百度 / Google 验证 meta（每个 preview 域名各一份）。  
3. **抽查 canonical**  
   - 公告 SSR 页在 preview 访问时，canonical 应为 preview URL（便于验证期按 preview 收录）。  
   - 正式切 www 前，再统一改为正式域 canonical，并配置 301。  
4. **切正式域后**  
   - Traefik / DNS 将 www 切到动态站；  
   - preview 可改为 `noindex` 或仅内网/登录可访问，避免双站长期抢收录。

---

## 8. 建议观察周期与通过标准（可调整）

**观察周期：** 提交后 2～4 周（百度通常慢于 Google）。

**建议通过标准（示例）：**

- 公告详情样例页可被抓取，无大面积 4xx/5xx  
- 百度/Google 对 `/notices` 与部分详情出现索引或有效抓取记录  
- 移动端打开正常，核心区块（标题、正文、结构化信息）可见  
- 无因 preview 导致正式 www 收录异常下跌（并列表对比）

达标后，再安排「正式域名切换动态站」方案，不在本文件展开。

---

## 9. 联系与分工

| 角色 | 职责 |
|------|------|
| 老板 / 运营 | 站长平台添加站点、提交 sitemap、查看收录报表、拍板是否切换 |
| 技术 | 域名证书、robots/sitemap、验证码埋点、抓取异常排查 |
| 运维 | preview 域名解析与 HTTPS、服务可用性 |

---

## 附录：一键复制提交列表

```
https://preview.qlyc.co/
https://preview.qlyc.co/sitemap.xml
https://preview.qlyc.co/sitemap-notices.xml

https://preview.yizhichan.co/
https://preview.yizhichan.co/sitemap.xml
https://preview.yizhichan.co/sitemap-notices.xml

https://preview.qinghuicai.cn/
https://preview.qinghuicai.cn/sitemap.xml
https://preview.qinghuicai.cn/sitemap-notices.xml
```
