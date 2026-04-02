from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field, model_validator

from .common import BaseContractModel, RiskDecision, RiskSeverity


class RiskLimit(BaseContractModel):
    account_code: str
    exchange_code: str | None = None
    unified_symbol: str | None = None
    max_position_qty: Decimal | None = None
    max_notional: Decimal | None = None
    max_leverage: Decimal | None = None
    max_daily_loss: Decimal | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_limit_scope_and_thresholds(self) -> "RiskLimit":
        if (
            self.max_position_qty is None
            and self.max_notional is None
            and self.max_leverage is None
            and self.max_daily_loss is None
        ):
            raise ValueError("risk limits must define at least one threshold")
        if (self.exchange_code is None) != (self.unified_symbol is None):
            raise ValueError("instrument-scoped risk limits must provide both exchange_code and unified_symbol")
        return self


class RiskEvent(BaseContractModel):
    account_code: str | None = None
    exchange_code: str | None = None
    unified_symbol: str | None = None
    event_time: datetime
    event_type: str
    severity: RiskSeverity | None = None
    decision: RiskDecision | None = None
    detail_json: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="detail",
        serialization_alias="detail_json",
    )

    @model_validator(mode="after")
    def validate_scope(self) -> "RiskEvent":
        if (self.exchange_code is None) != (self.unified_symbol is None):
            raise ValueError("instrument-scoped risk events must provide both exchange_code and unified_symbol")
        return self
