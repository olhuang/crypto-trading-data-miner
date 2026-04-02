from __future__ import annotations

from contextlib import contextmanager
import time
from typing import Callable, Iterator, TypeVar

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import OperationalError

from config import settings


_engine: Engine | None = None
T = TypeVar("T")


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(settings.resolved_database_url, future=True, pool_pre_ping=True)
    return _engine


def run_with_retry(operation: Callable[[], T], *, attempts: int = 3, backoff_seconds: float = 0.1) -> T:
    last_error: OperationalError | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except OperationalError as exc:
            last_error = exc
            if attempt >= attempts:
                break
            time.sleep(backoff_seconds * attempt)
    assert last_error is not None
    raise last_error


@contextmanager
def connection_scope() -> Iterator[Connection]:
    connection = run_with_retry(lambda: get_engine().connect())
    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def transaction_scope() -> Iterator[Connection]:
    with run_with_retry(lambda: get_engine().begin()) as connection:
        yield connection
