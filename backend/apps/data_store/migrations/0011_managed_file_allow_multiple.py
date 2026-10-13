from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0010_trademark_certificate_permissions"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="managedfile",
            name="unique_document_per_owner",
        ),
    ]
