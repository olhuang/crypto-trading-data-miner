from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field, model_validator

from .common import BaseContractModel, Direction, SignalType


class Signal(BaseContractModel):
    strategy_code: str
    strategy_version: str
    signal_id: str
    signal_time: datetime
    exchange_code: str
    unified_symbol: str
    signal_type: SignalType
    direction: Direction | None = None
    score: Decimal | None = None
    target_qty: Decimal | None = None
    target_notional: Decimal | None = None
    reason_code: str | None = None
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="metadata",
        serialization_alias="metadata_json",
    )

    @model_validator(mode="after")
    def validate_signal_rules(self) -> "Signal":
        tradable_signal_types = {
            SignalType.ENTRY,
            SignalType.REDUCE,
            SignalType.REVERSE,
            SignalType.REBALANCE,
        }
        if self.signal_type in tradable_signal_types and self.target_qty is None and self.target_notional is None:
            raise ValueError("tradable signals must include target_qty or target_notional")
        if self.signal_type == SignalType.EXIT and self.direction not in (None, Direction.FLAT):
            raise ValueError("exit signals may omit direction or set it to flat only")
        return self


class TargetPositionItem(BaseContractModel):
    exchange_code: str
    unified_symbol: str
    target_qty: Decimal | None = None
    target_weight: Decimal | None = None
    target_notional: Decimal | None = None

    @model_validator(mode="after")
    def validate_target_fields(self) -> "TargetPositionItem":
        if self.target_qty is None and self.target_weight is None and self.target_notional is None:
            raise ValueError("target position items must include target_qty, target_weight, or target_notional")
        return self


class TargetPosition(BaseContractModel):
    strategy_code: str
    strategy_version: str
    target_time: datetime
    positions: list[TargetPositionItem]
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="metadata",
        serialization_alias="metadata_json",
    )

    @model_validator(mode="after")
    def validate_positions(self) -> "TargetPosition":
        if not self.positions:
            raise ValueError("positions must not be empty")
        return self
