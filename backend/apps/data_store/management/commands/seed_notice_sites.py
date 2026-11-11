"""填充爬虫站点与站点选项（不含映射分类/对照）。

用法：
  python manage.py seed_notice_sites
  python manage.py seed_notice_sites --clear-mappings
"""

from django.core.management.base import BaseCommand

from apps.data_store.notice_site_config import seed_notice_sites_and_options


class Command(BaseCommand):
    help = "填充 NoticeCrawlSite / NoticeSiteOption；不写入映射分类与对照。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear-mappings",
            action="store_true",
            help="先清空映射分类与对照关系，再填充站点/选项。",
        )

    def handle(self, *args, **options):
        clear_mappings = bool(options.get("clear_mappings"))
        result = seed_notice_sites_and_options(clear_mappings=clear_mappings)
        self.stdout.write(
            self.style.SUCCESS(
                "seed_notice_sites done: "
                f"sites +{result['createdSites']}/~{result['updatedSites']}, "
                f"options +{result['createdOptions']}, "
                f"cleared categories={result['clearedCategories']} links={result['clearedLinks']}"
            )
        )
