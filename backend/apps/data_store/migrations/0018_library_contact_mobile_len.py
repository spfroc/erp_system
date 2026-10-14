from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0017_library_sms_permissions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="librarycontactrecord",
            name="mobile",
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
    ]
