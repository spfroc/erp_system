from django.db import migrations, models
from django.db.utils import OperationalError


def _is_duplicate_key_error(exc: BaseException) -> bool:
    args = getattr(exc, "args", ())
    if args and args[0] == 1061:
        return True
    return "Duplicate key name" in str(exc)


def add_library_contacts_index(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        vendor = schema_editor.connection.vendor
        if vendor == "mysql":
            cursor.execute(
                "SHOW INDEX FROM library_contacts WHERE Key_name = %s",
                ["library_contacts_del_id_idx"],
            )
            if cursor.fetchone():
                return
            try:
                cursor.execute(
                    "CREATE INDEX library_contacts_del_id_idx ON library_contacts (is_deleted, id)"
                )
            except OperationalError as exc:
                if _is_duplicate_key_error(exc):
                    return
                raise
        else:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS library_contacts_del_id_idx ON library_contacts (is_deleted, id)"
            )


def drop_library_contacts_index(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        vendor = schema_editor.connection.vendor
        if vendor == "mysql":
            cursor.execute(
                "SHOW INDEX FROM library_contacts WHERE Key_name = %s",
                ["library_contacts_del_id_idx"],
            )
            if not cursor.fetchone():
                return
            try:
                cursor.execute("DROP INDEX library_contacts_del_id_idx ON library_contacts")
            except OperationalError:
                return
        else:
            cursor.execute("DROP INDEX IF EXISTS library_contacts_del_id_idx")


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0030_assistant_nav"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    add_library_contacts_index,
                    drop_library_contacts_index,
                    atomic=False,
                ),
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name="librarycontactrecord",
                    index=models.Index(fields=["is_deleted", "id"], name="library_contacts_del_id_idx"),
                ),
            ],
        ),
    ]
