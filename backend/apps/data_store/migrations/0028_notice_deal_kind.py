from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("data_store", "0027_merge_notice_dict_nav"),
    ]

    operations = [
        migrations.AddField(
            model_name="noticeresulttag",
            name="deal_kind",
            field=models.CharField(blank=True, db_index=True, default="", max_length=16),
        ),
    ]
