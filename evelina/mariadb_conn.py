"""Подключение к MariaDB через PyMySQL (без SSL, для тестовых приложений)."""

import os

import pymysql
from pymysql.cursors import DictCursor
from pymysql.err import IntegrityError, OperationalError

DEFAULT_DATABASE = "evelina"
DEFAULT_HOST = "178.248.7.5"
DEFAULT_PORT = 3406


def _connect_kwargs():
    return {
        "host": os.environ.get("DB_HOST", DEFAULT_HOST),
        "port": int(os.environ.get("DB_PORT", str(DEFAULT_PORT))),
        "user": os.environ.get("DB_USER", "admin"),
        "password": os.environ.get("DB_PASSWORD", "admin"),
        "database": os.environ.get("DB_NAME", DEFAULT_DATABASE),
        "charset": "utf8mb4",
        "autocommit": False,
        "connect_timeout": 15,
    }


class Row(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            values = list(self.values())
            if 0 <= key < len(values):
                return values[key]
        return super().__getitem__(key)


class Cursor:
    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def fetchone(self):
        row = self._cursor.fetchone()
        return Row(row) if row else None

    def fetchall(self):
        return [Row(row) for row in self._cursor.fetchall()]

    def __iter__(self):
        return self

    def __next__(self):
        row = self.fetchone()
        if row is None:
            raise StopIteration
        return row


class Connection:
    def __init__(self, conn):
        self._conn = conn
        self.row_factory = None

    def execute(self, sql, params=None):
        if params is None:
            params = ()
        sql = sql.replace("?", "%s")
        cursor = self._conn.cursor(DictCursor)
        cursor.execute(sql, params)
        return Cursor(cursor)

    def executescript(self, script):
        for statement in script.split(";"):
            chunk = statement.strip()
            if chunk:
                self.execute(chunk)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        return False


def connect():
    kwargs = _connect_kwargs()
    host, port = kwargs["host"], kwargs["port"]
    try:
        raw = pymysql.connect(**kwargs)
    except OperationalError as exc:
        if exc.args and exc.args[0] == 2003:
            raise OperationalError(
                2003,
                (
                    f"Нет связи с MariaDB ({host}:{port}). "
                    "На VPS в панели хостинга откройте входящий TCP-порт 3406 — "
                    "без сертификатов, обычное подключение."
                ),
            ) from exc
        raise
    return Connection(raw)
