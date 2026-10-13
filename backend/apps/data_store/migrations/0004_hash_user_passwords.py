from django.contrib.auth.hashers import identify_hasher, make_password
from django.db import migrations


def _hash_if_needed(value):
    if not value:
        return value
    password = str(value)
    try:
        identify_hasher(password)
        return password
    except ValueError:
        return make_password(password)


def hash_user_passwords(apps, schema_editor):
    UserRecord = apps.get_model("data_store", "UserRecord")
    AppState = apps.get_model("data_store", "AppState")

    for user in UserRecord.objects.all().iterator():
        data = dict(user.data or {})
        if data.get("password"):
            data["password"] = _hash_if_needed(data["password"])
            user.data = data
            user.save(update_fields=["data"])

    for state in AppState.objects.all().iterator():
        data = dict(state.data or {})
        users = data.get("users")
        if not isinstance(users, list):
            continue
        data["users"] = [
            {**user, "password": _hash_if_needed(user.get("password"))}
            if isinstance(user, dict) and user.get("password") else user
            for user in users
        ]
        state.data = data
        state.save(update_fields=["data"])


class Migration(migrations.Migration):
    dependencies = [("data_store", "0003_soft_delete_fields")]
    operations = [migrations.RunPython(hash_user_passwords, migrations.RunPython.noop)]
