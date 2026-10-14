from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0015_site_permissions"),
    ]

    operations = [
        migrations.CreateModel(
            name="LibraryContactRecord",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("deleted_by", models.CharField(blank=True, max_length=100)),
                ("name", models.CharField(db_index=True, max_length=255)),
                ("mobile", models.CharField(blank=True, db_index=True, max_length=50)),
                ("license_code", models.CharField(blank=True, db_index=True, max_length=64)),
                ("signed", models.CharField(db_index=True, default="有效", max_length=20)),
                ("origin", models.CharField(blank=True, db_index=True, max_length=50)),
                ("customer_type", models.CharField(blank=True, db_index=True, max_length=50)),
                ("sell_user_id", models.CharField(blank=True, db_index=True, max_length=64)),
            ],
            options={"db_table": "library_contacts"},
        ),
        migrations.CreateModel(
            name="SmsTemplateRecord",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("deleted_by", models.CharField(blank=True, max_length=100)),
                ("name", models.CharField(db_index=True, max_length=100)),
                ("content", models.CharField(blank=True, max_length=500)),
                ("prefix", models.CharField(blank=True, max_length=50)),
            ],
            options={"db_table": "sms_templates"},
        ),
        migrations.CreateModel(
            name="SmsRecordRecord",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("deleted_by", models.CharField(blank=True, max_length=100)),
                ("task_id", models.CharField(blank=True, db_index=True, max_length=100)),
                ("mobile", models.CharField(blank=True, db_index=True, max_length=255)),
                ("content", models.CharField(blank=True, max_length=500)),
                ("sms_type", models.CharField(blank=True, db_index=True, max_length=50)),
                ("source", models.CharField(blank=True, db_index=True, max_length=50)),
                ("result", models.CharField(blank=True, max_length=100)),
                ("balance", models.IntegerField(blank=True, null=True)),
            ],
            options={"db_table": "sms_records"},
        ),
    ]
