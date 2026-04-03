from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from hashlib import sha1
from typing import Mapping

from models.common import Direction, SignalType
from models.strategy import Signal, TargetPosition


def build_signals_from_target_position(
    target_position: TargetPosition,
    current_positions: Mapping[str, Decimal],
    *,
    session_code: str,
) -> list[Signal]:
    signals: list[Signal] = []
    for index, position in enumerate(target_position.positions, start=1):
        if position.target_qty is None:
            continue
        current_qty = Decimal(current_positions.get(position.unified_symbol, Decimal("0")))
        target_qty = position.target_qty
        delta_qty = target_qty - current_qty
        if delta_qty == 0:
            continue

        signal_type = _derive_signal_type(current_qty, target_qty)
        direction = _derive_direction(target_qty)
        signal = Signal(
            strategy_code=target_position.strategy_code,
            strategy_version=target_position.strategy_version,
            signal_id=_build_deterministic_signal_id(
                session_code=session_code,
                target_time=target_position.target_time,
                unified_symbol=position.unified_symbol,
                ordinal=index,
            ),
            signal_time=target_position.target_time,
            exchange_code=position.exchange_code,
            unified_symbol=position.unified_symbol,
            signal_type=signal_type,
            direction=direction,
            target_qty=abs(target_qty) if direction == Direction.SHORT else target_qty,
            target_notional=position.target_notional,
            reason_code=_derive_reason_code(signal_type),
            metadata_json={
                **target_position.metadata_json,
                "source": "target_position_projection",
                "current_qty": str(current_qty),
                "target_qty_signed": str(target_qty),
                "delta_qty": str(delta_qty),
            },
        )
        signals.append(signal)
    return signals


def _build_deterministic_signal_id(
    *,
    session_code: str,
    target_time: datetime,
    unified_symbol: str,
    ordinal: int,
) -> str:
    payload = f"{session_code}|{target_time.isoformat()}|{unified_symbol}|{ordinal}"
    return f"sig_{sha1(payload.encode('utf-8')).hexdigest()[:16]}"


def _derive_signal_type(current_qty: Decimal, target_qty: Decimal) -> SignalType:
    if current_qty == 0 and target_qty != 0:
        return SignalType.ENTRY
    if current_qty != 0 and target_qty == 0:
        return SignalType.EXIT
    if current_qty != 0 and target_qty != 0 and ((current_qty > 0) != (target_qty > 0)):
        return SignalType.REVERSE
    if abs(target_qty) < abs(current_qty):
        return SignalType.REDUCE
    return SignalType.REBALANCE


def _derive_direction(target_qty: Decimal) -> Direction | None:
    if target_qty > 0:
        return Direction.LONG
    if target_qty < 0:
        return Direction.SHORT
    return Direction.FLAT


def _derive_reason_code(signal_type: SignalType) -> str:
    return {
        SignalType.ENTRY: "target_entry",
        SignalType.EXIT: "target_exit",
        SignalType.REVERSE: "target_reverse",
        SignalType.REDUCE: "target_reduce",
        SignalType.REBALANCE: "target_rebalance",
    }[signal_type]
