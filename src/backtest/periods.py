from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable, Literal, Sequence

from storage.repositories.backtest import BacktestRunRepository

from .performance import PerformancePoint


PeriodType = Literal["year", "quarter", "month"]


@dataclass(slots=True)
class PeriodBreakdownEntry:
    period_type: PeriodType
    period_start: datetime
    period_end: datetime
    start_equity: Decimal
    end_equity: Decimal
    total_return: Decimal
    max_drawdown: Decimal
    turnover: Decimal
    fee_cost: Decimal
    slippage_cost: Decimal
    signal_count: int
    fill_count: int


class BacktestPeriodBreakdownProjector:
    def __init__(self, run_repository: BacktestRunRepository | None = None) -> None:
        self.run_repository = run_repository or BacktestRunRepository()

    def build(self, connection, *, run_id: int, period_type: PeriodType) -> list[PeriodBreakdownEntry] | None:
        run_row = self.run_repository.get_run(connection, run_id)
        if run_row is None:
            return None

        params_json = run_row.get("params_json") or {}
        initial_cash = Decimal(str(params_json.get("initial_cash", "0")))
        performance_points = [
            PerformancePoint(
                ts=row["ts"],
                equity=Decimal(row["equity"]),
                cash=Decimal(row["cash"]),
                gross_exposure=Decimal(row["gross_exposure"]),
                net_exposure=Decimal(row["net_exposure"]),
                drawdown=Decimal(row["drawdown"]),
                realized_pnl=Decimal("0"),
                unrealized_pnl=Decimal("0"),
                fee_cost=Decimal("0"),
                slippage_cost=Decimal("0"),
                turnover_notional=Decimal("0"),
            )
            for row in self.run_repository.list_timeseries(connection, run_id=run_id)
        ]
        fill_records = self.run_repository.list_fill_records(connection, run_id=run_id)
        signal_records = self.run_repository.list_signal_records(connection, run_id=run_id)
        return build_period_breakdown(
            performance_points=performance_points,
            fill_records=fill_records,
            signal_records=signal_records,
            initial_cash=initial_cash,
            period_type=period_type,
        )


def build_period_breakdown(
    *,
    performance_points: Sequence[PerformancePoint],
    fill_records: Sequence[dict[str, object]],
    signal_records: Sequence[dict[str, object]],
    initial_cash: Decimal,
    period_type: PeriodType,
) -> list[PeriodBreakdownEntry]:
    if not performance_points:
        return []

    fills_by_bucket = _group_fills_by_period(fill_records, period_type)
    signals_by_bucket = _group_signals_by_period(signal_records, period_type)

    entries: list[PeriodBreakdownEntry] = []
    baseline_equity = initial_cash
    current_bucket: tuple[int, ...] | None = None
    current_points: list[PerformancePoint] = []

    for point in performance_points:
        bucket = _period_bucket(point.ts, period_type)
        if current_bucket is None:
            current_bucket = bucket
        if bucket != current_bucket:
            entries.append(
                _build_entry(
                    period_type=period_type,
                    bucket=current_bucket,
                    points=current_points,
                    fills=fills_by_bucket.get(current_bucket, []),
                    signals=signals_by_bucket.get(current_bucket, []),
                    initial_cash=initial_cash,
                    start_equity=baseline_equity,
                )
            )
            baseline_equity = current_points[-1].equity
            current_bucket = bucket
            current_points = []
        current_points.append(point)

    assert current_bucket is not None
    entries.append(
        _build_entry(
            period_type=period_type,
            bucket=current_bucket,
            points=current_points,
            fills=fills_by_bucket.get(current_bucket, []),
            signals=signals_by_bucket.get(current_bucket, []),
            initial_cash=initial_cash,
            start_equity=baseline_equity,
        )
    )
    return entries


def _build_entry(
    *,
    period_type: PeriodType,
    bucket: tuple[int, ...],
    points: Sequence[PerformancePoint],
    fills: Sequence[dict[str, object]],
    signals: Sequence[dict[str, object]],
    initial_cash: Decimal,
    start_equity: Decimal,
) -> PeriodBreakdownEntry:
    period_start = _bucket_start(bucket, period_type, tzinfo=points[0].ts.tzinfo or timezone.utc)
    period_end = points[-1].ts
    end_equity = points[-1].equity
    total_return = Decimal("0") if start_equity == 0 else (end_equity - start_equity) / start_equity

    local_peak = start_equity
    local_max_drawdown = Decimal("0")
    for point in points:
        local_peak = max(local_peak, point.equity)
        if local_peak > 0:
            local_max_drawdown = max(local_max_drawdown, (local_peak - point.equity) / local_peak)

    turnover_notional = Decimal("0")
    fee_cost = Decimal("0")
    slippage_cost = Decimal("0")
    for fill in fills:
        turnover_notional += Decimal(fill["price"]) * Decimal(fill["qty"])
        fee_cost += Decimal(fill["fee"] or 0)
        slippage_cost += Decimal(fill["slippage_cost"] or 0)
    turnover = turnover_notional / initial_cash if initial_cash > 0 else Decimal("0")

    return PeriodBreakdownEntry(
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        start_equity=start_equity,
        end_equity=end_equity,
        total_return=total_return,
        max_drawdown=local_max_drawdown,
        turnover=turnover,
        fee_cost=fee_cost,
        slippage_cost=slippage_cost,
        signal_count=len(signals),
        fill_count=len(fills),
    )


def _group_fills_by_period(fill_records: Sequence[dict[str, object]], period_type: PeriodType) -> dict[tuple[int, ...], list[dict[str, object]]]:
    buckets: dict[tuple[int, ...], list[dict[str, object]]] = defaultdict(list)
    for fill in fill_records:
        bucket = _period_bucket(fill["fill_time"], period_type)
        buckets[bucket].append(fill)
    return buckets


def _group_signals_by_period(signal_records: Sequence[dict[str, object]], period_type: PeriodType) -> dict[tuple[int, ...], list[dict[str, object]]]:
    buckets: dict[tuple[int, ...], list[dict[str, object]]] = defaultdict(list)
    for signal in signal_records:
        bucket = _period_bucket(signal["signal_time"], period_type)
        buckets[bucket].append(signal)
    return buckets


def _period_bucket(ts: datetime, period_type: PeriodType) -> tuple[int, ...]:
    if period_type == "year":
        return (ts.year,)
    if period_type == "quarter":
        return (ts.year, ((ts.month - 1) // 3) + 1)
    if period_type == "month":
        return (ts.year, ts.month)
    raise ValueError(f"unsupported period_type: {period_type}")


def _bucket_start(bucket: tuple[int, ...], period_type: PeriodType, *, tzinfo) -> datetime:
    if period_type == "year":
        return datetime(bucket[0], 1, 1, tzinfo=tzinfo)
    if period_type == "quarter":
        start_month = (bucket[1] - 1) * 3 + 1
        return datetime(bucket[0], start_month, 1, tzinfo=tzinfo)
    if period_type == "month":
        return datetime(bucket[0], bucket[1], 1, tzinfo=tzinfo)
    raise ValueError(f"unsupported period_type: {period_type}")
