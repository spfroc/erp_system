from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0008_order_list_permissions"),
    ]

    operations = [
        migrations.CreateModel(
            name="TrademarkCertificateRecord",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("deleted_by", models.CharField(blank=True, max_length=100)),
                ("registration_no", models.CharField(db_index=True, max_length=64)),
                ("registrant", models.CharField(db_index=True, max_length=255)),
                ("registrant_address", models.CharField(blank=True, max_length=500)),
                ("international_class", models.CharField(blank=True, max_length=20)),
                ("registration_date", models.CharField(blank=True, max_length=20)),
                ("valid_until", models.CharField(blank=True, max_length=20)),
            ],
            options={"db_table": "trademark_certificates"},
        ),
    ]
