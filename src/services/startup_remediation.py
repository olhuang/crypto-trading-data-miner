from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from config import settings
from ingestion.binance.public_rest import BinancePublicRestClient
from jobs.backfill_bars import run_bar_backfill
from jobs.data_quality import run_bar_gap_checks
from storage.db import connection_scope, transaction_scope
from storage.repositories.ops import DataGapRepository


@dataclass(slots=True)
class StartupGapRemediationResult:
    symbols_checked: int
    gaps_detected: int
    gaps_resolved: int
    backfill_runs: int


def _iter_configured_symbols() -> list[str]:
    return [symbol.strip() for symbol in settings.startup_gap_remediation_symbols.split(",") if symbol.strip()]


def _venue_symbol_from_unified_symbol(unified_symbol: str) -> str:
    if unified_symbol.endswith("_PERP"):
        return unified_symbol.removesuffix("_PERP")
    if unified_symbol.endswith("_SPOT"):
        return unified_symbol.removesuffix("_SPOT")
    return unified_symbol


def _find_open_bar_gaps(*, exchange_code: str, unified_symbol: str) -> list[dict]:
    with connection_scope() as connection:
        return DataGapRepository().list_recent(
            connection,
            data_type="bars_1m",
            status="open",
            exchange_code=exchange_code,
            unified_symbol=unified_symbol,
            limit=200,
        )


def _resolve_gap(gap_id: int, *, backfill_job_id: int) -> None:
    with transaction_scope() as connection:
        DataGapRepository().resolve_gap(
            connection,
            gap_id,
            detail_json={"resolved_by": "startup_gap_remediation", "backfill_job_id": backfill_job_id},
        )


def run_startup_gap_remediation(
    *,
    exchange_code: str | None = None,
    unified_symbols: Iterable[str] | None = None,
    lookback_hours: int | None = None,
    client: BinancePublicRestClient | None = None,
    observed_at: datetime | None = None,
) -> StartupGapRemediationResult:
    effective_exchange_code = exchange_code or settings.startup_gap_remediation_exchange_code
    effective_symbols = list(unified_symbols or _iter_configured_symbols())
    effective_lookback_hours = lookback_hours or settings.startup_gap_remediation_lookback_hours
    remediation_client = client or BinancePublicRestClient()

    now = observed_at or datetime.now(timezone.utc)
    start_time = now - timedelta(hours=effective_lookback_hours)
    result = StartupGapRemediationResult(
        symbols_checked=0,
        gaps_detected=0,
        gaps_resolved=0,
        backfill_runs=0,
    )

    for unified_symbol in effective_symbols:
        result.symbols_checked += 1
        run_bar_gap_checks(
            exchange_code=effective_exchange_code,
            unified_symbol=unified_symbol,
            start_time=start_time,
            end_time=now,
        )
        gaps = _find_open_bar_gaps(exchange_code=effective_exchange_code, unified_symbol=unified_symbol)
        result.gaps_detected += len(gaps)
        venue_symbol = _venue_symbol_from_unified_symbol(unified_symbol)
        for gap in gaps:
            backfill_result = run_bar_backfill(
                symbol=venue_symbol,
                unified_symbol=unified_symbol,
                interval="1m",
                start_time=gap["gap_start"],
                end_time=gap["gap_end"],
                client=remediation_client,
                requested_by="startup_gap_remediation",
                exchange_code=effective_exchange_code,
            )
            result.backfill_runs += 1
            if backfill_result.status == "succeeded":
                _resolve_gap(gap["gap_id"], backfill_job_id=backfill_result.ingestion_job_id)
                result.gaps_resolved += 1

    return result
