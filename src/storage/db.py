from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

from config import settings


_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(settings.resolved_database_url, future=True)
    return _engine


@contextmanager
def connection_scope() -> Iterator[Connection]:
    connection = get_engine().connect()
    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def transaction_scope() -> Iterator[Connection]:
    with get_engine().begin() as connection:
        yield connection
