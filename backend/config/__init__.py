import pymysql

from .celery import app as celery_app

pymysql.version_info = (2, 2, 1, "final", 0)
pymysql.install_as_MySQLdb()

__all__ = ("celery_app",)
