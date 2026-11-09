from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.data_store.notice_digest import default_digest_date, run_notice_digest


class Command(BaseCommand):
    help = "按订阅条件发送公告日汇总（微信服务号模板消息）。"

    def add_arguments(self, parser):
        parser.add_argument("--date", type=str, default="", help="汇总日期 YYYY-MM-DD，默认昨天")
        parser.add_argument("--dry-run", action="store_true", help="只匹配不发送")
        parser.add_argument("--limit", type=int, default=0, help="最多处理账号数，0 表示不限制")

    def handle(self, *args, **options):
        raw_date = (options.get("date") or "").strip()
        if raw_date:
            try:
                digest_date = date.fromisoformat(raw_date)
            except ValueError as exc:
                raise CommandError("日期格式应为 YYYY-MM-DD") from exc
        else:
            digest_date = default_digest_date()
        result = run_notice_digest(
            digest_date=digest_date,
            dry_run=bool(options.get("dry_run")),
            limit=int(options.get("limit") or 0),
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"date={result.get('date')} accounts={result.get('accounts')} "
                f"sent={result.get('sent')} failed={result.get('failed')} skipped={result.get('skipped')}"
            )
        )
