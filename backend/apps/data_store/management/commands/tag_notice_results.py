from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from apps.data_store.notice_tagging import tag_result_notices


class Command(BaseCommand):
    help = "按规则给结果公告打采购人和商品标签。不改采集表，可重复执行。"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200)
        parser.add_argument("--rebuild", action="store_true", help="重算未锁定的已有标签")

    def handle(self, *args, **options):
        limit = max(1, min(int(options["limit"]), 2000))
        try:
            result = tag_result_notices(limit=limit, rebuild=bool(options["rebuild"]))
        except DatabaseError as exc:
            raise CommandError(f"公告表或标签表不可用：{exc}") from exc
        self.stdout.write(f"已打标 {result['tagged']} 条，跳过 {result['skipped']} 条。")
