"""Merge mall portal leaf (0033) with preempt crawl leaf (0034)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0033_merge_mall_assistant_portal"),
        ("data_store", "0034_devopsjobrun_cancel_preempt"),
    ]

    operations = []
