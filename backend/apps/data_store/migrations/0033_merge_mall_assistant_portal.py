"""Merge mall-customer leaf with assistant/portal migration chain."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0025_rename_mall_customer_menu"),
        ("data_store", "0032_portal_enterprise_permissions"),
    ]

    operations = []
