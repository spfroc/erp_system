# Preview 动态站搜索收录 · 一页纸

**目的**：正式静态站先不动；用三个 preview 动态站做 SEO 验证，通过后再切正式域名。  
**日期**：2026-11-18

---

## 域名对照

| 品牌 | 正式站（保留） | Preview（本次收录） |
|------|----------------|---------------------|
| 齐鲁云采 / 壹采 | www.qlyc.co | **preview.qlyc.co** |
| 壹采 | www.yizhichan.co | **preview.yizhichan.co** |
| 青慧采 | www.qinghuicai.cn | **preview.qinghuicai.cn** |

> 统一用上表 preview，勿再用 `yizhichan.qlyc.co`。门户 `portal.qlyc.co` 不收录。

---

## 每个站点提交这 3 个地址

以壹采为例（另两站改域名即可）：

1. https://preview.yizhichan.co/  
2. https://preview.yizhichan.co/sitemap.xml  
3. https://preview.yizhichan.co/sitemap-notices.xml  

另两站：

```
https://preview.qlyc.co/          + /sitemap.xml + /sitemap-notices.xml
https://preview.qinghuicai.cn/    + /sitemap.xml + /sitemap-notices.xml
```

---

## 操作（10 分钟 / 站）

1. 打开 [百度搜索资源平台](https://ziyuan.baidu.com/)（主渠道）  
2. **添加网站** → 填 `https://preview.xxx` → 完成验证  
3. **提交 sitemap**：综合 + 公告 各一份  
4. 可选：再推送首页、`/notices` 各一次  
5. （可选对照）Google Search Console 同样添加并提交 sitemap  

---

## 验收看什么（2～4 周）

- [ ] 三个 preview HTTPS 正常打开  
- [ ] 站长平台已验证并提交 sitemap  
- [ ] 有抓取 / 索引数据，无明显大面积失败  
- [ ] 正式 www 收录未异常下跌  

达标后再安排「正式域名切动态站」。

---

## 注意（一句话）

验证期 **www 与 preview 并存**；站长平台请直接提交 preview 的 sitemap，不要只依赖 robots。切换正式域后，再把 preview 降权或停收录。
