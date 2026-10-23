from __future__ import annotations

import argparse

from db import ensure_list_indexes, init_db, ping
from pipeline.attachments import download_pending, parse_attachments
from pipeline.crawl import crawl_jd, crawl_sd_mall
from clients.qlyc_login import ensure_access_token
from pipeline.crawl_supplier import crawl_suppliers
from pipeline.parse_llm import parse_pending, reenrich_parsed, reparse_existing


def main() -> None:
    parser = argparse.ArgumentParser(description="政府采购公告抓取 / 解析")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db", help="创建表结构")
    sub.add_parser("ping", help="测试数据库连接")
    p_idx = sub.add_parser(
        "migrate-list-indexes",
        help="补齐公告列表/筛选加速索引（已存在则跳过）",
    )
    p_idx.add_argument("--dry-run", action="store_true", help="只打印将要新建的索引")

    p_crawl = sub.add_parser("crawl", help="抓取列表+详情到 notice_raw")
    p_crawl.add_argument(
        "--site",
        choices=["all", "sd-mall", "jd"],
        default="all",
    )
    p_crawl.add_argument("--max-pages", type=int, default=None, help="每类最多页数，调试用")
    p_crawl.add_argument("--page-size", type=int, default=20)
    p_crawl.add_argument("--list-only", action="store_true", help="只抓列表不拉详情")
    p_crawl.add_argument(
        "--start-date",
        default=None,
        help="开始日期 YYYY-MM-DD。商城传给列表接口；京东按 createTime 倒序截断",
    )
    p_crawl.add_argument(
        "--end-date",
        default=None,
        help="结束日期 YYYY-MM-DD。商城传给列表接口；京东跳过更晚的公告",
    )
    p_crawl.add_argument(
        "--stop-dup",
        type=int,
        default=None,
        help="同一类型连续多少条已入库后停止该类（京东和商城）",
    )

    p_parse = sub.add_parser(
        "parse",
        help="用本地模型解析 notice_raw -> notice_parsed（读 .env EXTRACTOR_BACKEND）",
    )
    p_parse.add_argument("--limit", type=int, default=50)
    p_parse.add_argument("--site", default=None, help="site_id 过滤")
    p_parse.add_argument(
        "--force",
        action="store_true",
        help="已解析的也重跑本地模型并覆盖（版式不固定、结果不全时用）",
    )

    p_dl = sub.add_parser("download-att", help="下载待处理附件")
    p_dl.add_argument("--limit", type=int, default=50)
    p_dl.add_argument("--site", default=None)

    p_att = sub.add_parser("parse-att", help="抽取附件文本并用本地模型解析")
    p_att.add_argument("--limit", type=int, default=50)
    p_att.add_argument("--site", default=None)
    p_att.add_argument("--no-llm", action="store_true", help="只抽文本不跑模型")

    p_en = sub.add_parser(
        "enrich",
        help="不跑模型：用 list/detail JSON / 正文报价时间补结构化字段",
    )
    p_en.add_argument("--limit", type=int, default=500)
    p_en.add_argument("--site", default=None)
    p_en.add_argument(
        "--missing-start",
        action="store_true",
        help="只处理报价开始时间为空的公告（优先回填）",
    )
    p_en.add_argument(
        "--missing-phone",
        action="store_true",
        help="只处理项目联系电话为空的公告（优先回填）",
    )

    p_rp = sub.add_parser(
        "reparse",
        help="对已抓取公告重新抽取（默认跟 .env 本地模型；可改 --backend heuristic）",
    )
    p_rp.add_argument("--limit", type=int, default=500)
    p_rp.add_argument("--site", default=None)
    p_rp.add_argument(
        "--backend",
        default=None,
        help="留空=跟 .env；或 heuristic / local_gguf / local_hf",
    )
    p_rp.add_argument(
        "--force",
        action="store_true",
        help="整单覆盖已有解析结果（默认只补空字段）",
    )

    p_login = sub.add_parser(
        "login-qlyc",
        help="登录齐鲁云采并缓存 access_token（需 SD_ACCOUNT / SD_PASSWORD）",
    )
    p_login.add_argument("--force", action="store_true", help="忽略缓存强制重新登录")

    p_sup = sub.add_parser(
        "crawl-supplier",
        help="抓取山东商城供应商到 mall_customer（TouchCustomer Python 版）",
    )
    p_sup.add_argument(
        "--type",
        dest="types",
        type=int,
        nargs="*",
        default=None,
        help="协议类型：1超市厂商 2定点 3代理商 4经销商 5超市电商；默认全部",
    )
    p_sup.add_argument("--max-pages", type=int, default=None)
    p_sup.add_argument("--page-size", type=int, default=50)
    p_sup.add_argument(
        "--stop-dup",
        type=int,
        default=None,
        help="同一类型连续多少条已入库后停止该类",
    )
    p_sup.add_argument(
        "--with-store",
        action="store_true",
        help="拉取店铺详情（需 SD_ACCESS_TOKEN）",
    )

    args = parser.parse_args()

    if args.cmd == "init-db":
        init_db()
        print("tables created (columns/comments/list indexes ensured)")
        return
    if args.cmd == "ping":
        print("db ok:", ping())
        return
    if args.cmd == "migrate-list-indexes":
        created = ensure_list_indexes(dry_run=args.dry_run)
        if not created:
            print("indexes already up to date")
        else:
            prefix = "would create" if args.dry_run else "created"
            print(f"{prefix} {len(created)} indexes:")
            for name in created:
                print(f"  - {name}")
        return
    if args.cmd == "crawl":
        with_detail = not args.list_only
        common = dict(
            max_pages=args.max_pages,
            page_size=args.page_size,
            with_detail=with_detail,
            start_date=args.start_date,
            end_date=args.end_date,
            stop_dup=args.stop_dup,
        )
        if args.site in ("all", "sd-mall"):
            crawl_sd_mall(**common)
        if args.site in ("all", "jd"):
            crawl_jd(**common)
        print("crawl done")
        return
    if args.cmd == "parse":
        n = parse_pending(limit=args.limit, site_id=args.site, force=args.force)
        print(f"parsed ok: {n}")
        return
    if args.cmd == "download-att":
        n = download_pending(limit=args.limit, site_id=args.site)
        print(f"downloaded: {n}")
        return
    if args.cmd == "parse-att":
        n = parse_attachments(limit=args.limit, site_id=args.site, use_llm=not args.no_llm)
        print(f"attachment parsed: {n}")
        return
    if args.cmd == "enrich":
        n = reenrich_parsed(
            limit=args.limit,
            site_id=args.site,
            missing_start=args.missing_start,
            missing_phone=args.missing_phone,
        )
        print(f"enriched: {n}")
        return
    if args.cmd == "reparse":
        n = reparse_existing(
            limit=args.limit,
            site_id=args.site,
            force=args.force,
            backend=args.backend,
        )
        print(f"reparsed: {n}")
        return
    if args.cmd == "login-qlyc":
        token = ensure_access_token(force_login=args.force)
        print(f"login ok, access_token length={len(token)}")
        print("cached at data/qlyc_access_token.json")
        return
    if args.cmd == "crawl-supplier":
        n = crawl_suppliers(
            agreement_types=args.types,
            max_pages=args.max_pages,
            page_size=args.page_size,
            with_store=args.with_store,
            stop_dup=args.stop_dup,
        )
        print(f"crawl-supplier done, upserted: {n}")
        return


if __name__ == "__main__":
    main()
