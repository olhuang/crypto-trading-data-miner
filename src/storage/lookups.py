from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection


class LookupResolutionError(ValueError):
    """Raised when a human-readable identifier cannot be resolved."""


def _scalar_one_or_raise(connection: Connection, query: str, params: dict[str, object], *, error: str) -> int:
    result = connection.execute(text(query), params).scalar_one_or_none()
    if result is None:
        raise LookupResolutionError(error)
    return int(result)


def resolve_exchange_id(connection: Connection, exchange_code: str) -> int:
    return _scalar_one_or_raise(
        connection,
        "select exchange_id from ref.exchanges where exchange_code = :exchange_code",
        {"exchange_code": exchange_code},
        error=f"unknown exchange_code: {exchange_code}",
    )


def resolve_asset_id(connection: Connection, asset_code: str) -> int:
    return _scalar_one_or_raise(
        connection,
        "select asset_id from ref.assets where asset_code = :asset_code",
        {"asset_code": asset_code},
        error=f"unknown asset_code: {asset_code}",
    )


def resolve_account_id(connection: Connection, account_code: str) -> int:
    return _scalar_one_or_raise(
        connection,
        "select account_id from execution.accounts where account_code = :account_code",
        {"account_code": account_code},
        error=f"unknown account_code: {account_code}",
    )


def resolve_strategy_id(connection: Connection, strategy_code: str) -> int:
    return _scalar_one_or_raise(
        connection,
        "select strategy_id from strategy.strategies where strategy_code = :strategy_code",
        {"strategy_code": strategy_code},
        error=f"unknown strategy_code: {strategy_code}",
    )


def resolve_strategy_version_id(connection: Connection, strategy_code: str, strategy_version: str) -> int:
    return _scalar_one_or_raise(
        connection,
        """
        select sv.strategy_version_id
        from strategy.strategy_versions sv
        join strategy.strategies s on s.strategy_id = sv.strategy_id
        where s.strategy_code = :strategy_code
          and sv.version_code = :strategy_version
        """,
        {
            "strategy_code": strategy_code,
            "strategy_version": strategy_version,
        },
        error=(
            "unknown strategy version for "
            f"strategy_code={strategy_code} strategy_version={strategy_version}"
        ),
    )


def resolve_instrument_id(connection: Connection, exchange_code: str, unified_symbol: str) -> int:
    return _scalar_one_or_raise(
        connection,
        """
        select i.instrument_id
        from ref.instruments i
        join ref.exchanges e on e.exchange_id = i.exchange_id
        where e.exchange_code = :exchange_code
          and i.unified_symbol = :unified_symbol
        """,
        {"exchange_code": exchange_code, "unified_symbol": unified_symbol},
        error=f"unknown instrument for exchange_code={exchange_code} unified_symbol={unified_symbol}",
    )


def resolve_instrument_id_by_venue_symbol(connection: Connection, exchange_code: str, venue_symbol: str, instrument_type: str) -> int:
    return _scalar_one_or_raise(
        connection,
        """
        select i.instrument_id
        from ref.instruments i
        join ref.exchanges e on e.exchange_id = i.exchange_id
        where e.exchange_code = :exchange_code
          and i.venue_symbol = :venue_symbol
          and i.instrument_type = :instrument_type
        """,
        {
            "exchange_code": exchange_code,
            "venue_symbol": venue_symbol,
            "instrument_type": instrument_type,
        },
        error=(
            "unknown instrument for "
            f"exchange_code={exchange_code} venue_symbol={venue_symbol} instrument_type={instrument_type}"
        ),
    )
