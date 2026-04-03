from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import math
from typing import Sequence

from .state import PortfolioMark


@dataclass(slots=True)
class PerformancePoint:
    ts: datetime
    cash: Decimal
    equity: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    fee_cost: Decimal
    slippage_cost: Decimal
    turnover_notional: Decimal
    drawdown: Decimal


@dataclass(slots=True)
class PerformanceSummary:
    total_return: Decimal
    annualized_return: Decimal | None
    max_drawdown: Decimal
    turnover: Decimal
    win_rate: Decimal | None
    fee_cost: Decimal
    slippage_cost: Decimal
    final_equity: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal


def build_performance_point(*, ts: datetime, mark: PortfolioMark, running_peak_equity: Decimal) -> tuple[PerformancePoint, Decimal]:
    peak_equity = max(running_peak_equity, mark.equity)
    if peak_equity > 0:
        drawdown = (peak_equity - mark.equity) / peak_equity
    else:
        drawdown = Decimal("0")
    return (
        PerformancePoint(
            ts=ts,
            cash=mark.cash,
            equity=mark.equity,
            gross_exposure=mark.gross_exposure,
            net_exposure=mark.net_exposure,
            realized_pnl=mark.realized_pnl,
            unrealized_pnl=mark.unrealized_pnl,
            fee_cost=mark.fee_cost,
            slippage_cost=mark.slippage_cost,
            turnover_notional=mark.turnover_notional,
            drawdown=drawdown,
        ),
        peak_equity,
    )


def summarize_performance(
    *,
    initial_cash: Decimal,
    run_start: datetime,
    run_end: datetime,
    performance_points: Sequence[PerformancePoint],
) -> PerformanceSummary:
    if performance_points:
        final_point = performance_points[-1]
        final_equity = final_point.equity
        max_drawdown = max(point.drawdown for point in performance_points)
        turnover = final_point.turnover_notional / initial_cash if initial_cash > 0 else Decimal("0")
        total_return = (final_equity - initial_cash) / initial_cash if initial_cash > 0 else Decimal("0")
        win_rate = None
        annualized_return = _annualize_return(
            initial_cash=initial_cash,
            final_equity=final_equity,
            run_start=run_start,
            run_end=run_end,
        )
        return PerformanceSummary(
            total_return=total_return,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            turnover=turnover,
            win_rate=win_rate,
            fee_cost=final_point.fee_cost,
            slippage_cost=final_point.slippage_cost,
            final_equity=final_equity,
            realized_pnl=final_point.realized_pnl,
            unrealized_pnl=final_point.unrealized_pnl,
        )

    return PerformanceSummary(
        total_return=Decimal("0"),
        annualized_return=Decimal("0"),
        max_drawdown=Decimal("0"),
        turnover=Decimal("0"),
        win_rate=None,
        fee_cost=Decimal("0"),
        slippage_cost=Decimal("0"),
        final_equity=initial_cash,
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
    )


def _annualize_return(
    *,
    initial_cash: Decimal,
    final_equity: Decimal,
    run_start: datetime,
    run_end: datetime,
) -> Decimal | None:
    if initial_cash <= 0 or final_equity <= 0:
        return None

    duration_seconds = (run_end - run_start).total_seconds()
    if duration_seconds <= 0:
        return None
    if duration_seconds < 86_400:
        return None

    years = duration_seconds / 31_557_600
    if years <= 0:
        return None

    ratio = float(final_equity / initial_cash)
    if ratio <= 0:
        return None

    annualized = math.pow(ratio, 1 / years) - 1
    if not math.isfinite(annualized) or abs(annualized) >= 10_000_000_000:
        return None
    return Decimal(str(annualized))
