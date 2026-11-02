from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.data_store.dev_ops_catalog import get_script, list_scripts
from apps.data_store.dev_ops_models import DevOpsJob, DevOpsJobRun
from apps.data_store.dev_ops_schedule import cron_matches, next_run_at
from apps.data_store.dev_ops_tasks import (
    ORPHAN_CELERY_GRACE_SECONDS,
    PENDING_STALE_SECONDS,
    preempt_notice_crawl_all,
    reap_stale_dev_ops_runs,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")


class DevOpsScheduleTests(SimpleTestCase):
    def test_catalog_whitelist(self):
        keys = {item["key"] for item in list_scripts()}
        self.assertIn("tag_notice_results", keys)
        self.assertIn("notice_crawl_once", keys)
        self.assertIn("notice_crawl_all", keys)
        self.assertIsNone(get_script("seed_database"))
        all_script = get_script("notice_crawl_all")
        self.assertIsNotNone(all_script)
        self.assertNotIn("lookback_days", {field["key"] for field in all_script["argSchema"]})

    def test_interval_next_run(self):
        now = datetime(2026, 10, 26, 10, 0, tzinfo=SHANGHAI)
        nxt = next_run_at(schedule_type="interval", interval_seconds=3600, cron_expr="", now=now, last_run_at=None)
        self.assertEqual(nxt, datetime(2026, 10, 26, 11, 0, tzinfo=SHANGHAI))

    def test_cron_matches_and_next(self):
        when = datetime(2026, 10, 26, 3, 0, tzinfo=SHANGHAI)
        self.assertTrue(cron_matches("0 3 * * *", when))
        self.assertFalse(cron_matches("0 4 * * *", when))
        nxt = next_run_at(schedule_type="cron", interval_seconds=None, cron_expr="0 3 * * *", now=when)
        self.assertEqual(nxt.hour, 3)
        self.assertEqual(nxt.minute, 0)
        self.assertGreater(nxt, when)


class DevOpsStaleRunTests(TestCase):
    def test_reap_stale_pending_and_running(self):
        now = timezone.now()
        job = DevOpsJob.objects.create(
            script_key="tag_notice_results",
            name="打标",
            enabled=False,
            schedule_type="manual",
            args_json={},
        )
        stale_pending = DevOpsJobRun.objects.create(job=job, trigger="manual", status="pending")
        DevOpsJobRun.objects.filter(id=stale_pending.id).update(
            created_at=now - timedelta(seconds=PENDING_STALE_SECONDS + 10)
        )
        stale_running = DevOpsJobRun.objects.create(job=job, trigger="manual", status="running")
        DevOpsJobRun.objects.filter(id=stale_running.id).update(
            started_at=now - timedelta(seconds=1800 + 700),
            created_at=now - timedelta(seconds=1800 + 800),
        )
        fresh = DevOpsJobRun.objects.create(job=job, trigger="manual", status="running", started_at=now)

        result = reap_stale_dev_ops_runs(now=now)
        self.assertGreaterEqual(result["reaped"], 2)
        stale_pending.refresh_from_db()
        stale_running.refresh_from_db()
        fresh.refresh_from_db()
        self.assertEqual(stale_pending.status, "failed")
        self.assertEqual(stale_running.status, "failed")
        self.assertEqual(fresh.status, "running")

    def test_reap_orphan_celery_running(self):
        now = timezone.now()
        job = DevOpsJob.objects.create(
            script_key="notice_crawl_once",
            name="一轮",
            enabled=False,
            schedule_type="manual",
            args_json={},
        )
        orphan = DevOpsJobRun.objects.create(
            job=job,
            trigger="manual",
            status="running",
            celery_task_id="dead-task-id",
            started_at=now - timedelta(seconds=ORPHAN_CELERY_GRACE_SECONDS + 30),
        )
        live = DevOpsJobRun.objects.create(
            job=job,
            trigger="manual",
            status="running",
            celery_task_id="live-task-id",
            started_at=now - timedelta(seconds=ORPHAN_CELERY_GRACE_SECONDS + 30),
        )

        with (
            patch(
                "apps.data_store.dev_ops_tasks._active_or_reserved_celery_task_ids",
                return_value={"live-task-id"},
            ),
            patch(
                "apps.data_store.dev_ops_tasks._celery_task_finished_terminal",
                return_value=False,
            ),
        ):
            result = reap_stale_dev_ops_runs(now=now)

        self.assertIn(f"running#{orphan.id}:orphan", result["runs"])
        orphan.refresh_from_db()
        live.refresh_from_db()
        self.assertEqual(orphan.status, "failed")
        self.assertIn("Celery 任务已不在 worker", orphan.stderr)
        self.assertEqual(live.status, "running")


class DevOpsPreemptCrawlAllTests(TestCase):
    def test_preempt_marks_running_and_fails_pending(self):
        all_job = DevOpsJob.objects.create(
            script_key="notice_crawl_all",
            name="全量",
            enabled=False,
            schedule_type="manual",
            args_json={},
        )
        once_job = DevOpsJob.objects.create(
            script_key="notice_crawl_once",
            name="一轮",
            enabled=False,
            schedule_type="manual",
            args_json={},
        )
        once_run = DevOpsJobRun.objects.create(job=once_job, trigger="manual", status="pending")
        running_all = DevOpsJobRun.objects.create(
            job=all_job, trigger="manual", status="running", started_at=timezone.now()
        )
        pending_all = DevOpsJobRun.objects.create(
            job=all_job, trigger="schedule", status="pending", celery_task_id="fake-task"
        )
        other = DevOpsJobRun.objects.create(
            job=once_job, trigger="manual", status="running", started_at=timezone.now()
        )

        preempted = preempt_notice_crawl_all(by_run_id=once_run.id)
        self.assertCountEqual(preempted, [running_all.id, pending_all.id])

        running_all.refresh_from_db()
        pending_all.refresh_from_db()
        other.refresh_from_db()
        self.assertTrue(running_all.cancel_requested)
        self.assertEqual(running_all.preempted_by_run_id, once_run.id)
        self.assertEqual(running_all.status, "running")
        self.assertIn("抢占暂停", running_all.stderr)
        self.assertEqual(pending_all.status, "failed")
        self.assertTrue(pending_all.cancel_requested)
        self.assertIn("抢占暂停", pending_all.stderr)
        self.assertEqual(other.status, "running")
        self.assertFalse(other.cancel_requested)
