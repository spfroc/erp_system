from django.db import migrations, models


RECORD_MODELS = [
    "invoicerecord",
    "ocrjobrecord",
    "onboardingrecord",
    "operationlogrecord",
    "optiongrouprecord",
    "organizationrecord",
    "platformaccountrecord",
    "productrecord",
    "projectitemrecord",
    "projectrecord",
    "projectreminderrecord",
    "purchaseorderrecord",
    "rolerecord",
    "salesorderrecord",
    "serviceorderrecord",
    "supplierpricerecord",
    "transactionrecord",
    "userrecord",
    "websiteleadrecord",
]


def soft_delete_fields(model_name: str):
    return [
        migrations.AddField(
            model_name=model_name,
            name="is_deleted",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name=model_name,
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name=model_name,
            name="deleted_by",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0002_business_tables"),
    ]

    operations = [
        operation
        for model_name in RECORD_MODELS
        for operation in soft_delete_fields(model_name)
    ]
