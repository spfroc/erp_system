from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("data_store", "0004_hash_user_passwords")]

    operations = [
        migrations.CreateModel(
            name="ManagedFile",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("document_type", models.CharField(db_index=True, max_length=30)),
                ("owner_id", models.CharField(db_index=True, max_length=64)),
                ("original_name", models.CharField(max_length=255)),
                ("content_type", models.CharField(blank=True, max_length=100)),
                ("size", models.PositiveBigIntegerField(default=0)),
                ("file", models.FileField(upload_to="business_documents/%Y/%m/")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("uploaded_by", models.CharField(blank=True, max_length=100)),
            ],
            options={"db_table": "managed_files"},
        ),
        migrations.AddConstraint(
            model_name="managedfile",
            constraint=models.UniqueConstraint(fields=("document_type", "owner_id"), name="unique_document_per_owner"),
        ),
    ]
