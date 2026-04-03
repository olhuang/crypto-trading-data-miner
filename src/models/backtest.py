from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from .common import BaseContractModel, Environment, OrderType


class ExecutionUrgency(StrEnum):
    PASSIVE = "passive"
    NORMAL = "normal"
    AGGRESSIVE = "aggressive"


class PositionNettingMode(StrEnum):
    ISOLATED_STRATEGY_SESSION = "isolated_strategy_session"
    SHARED_ACCOUNT_VIRTUAL_BOOKS = "shared_account_virtual_books"
    PORTFOLIO_NETTED = "portfolio_netted"


class ProtectionScope(StrEnum):
    POSITION = "position"
    LOT = "lot"


class ProtectionTriggerBasis(StrEnum):
    BAR_HIGH_LOW = "bar_high_low"
    LAST_TRADE = "last_trade"
    MARK_PRICE = "mark_price"
    INDEX_PRICE = "index_price"


class ExecutionPolicyConfig(BaseContractModel):
    policy_code: str = "default"
    order_type_preference: OrderType = OrderType.MARKET
    urgency: ExecutionUrgency = ExecutionUrgency.NORMAL
    maker_bias: bool = False
    reduce_only_on_exit: bool = True
    allow_position_flip: bool = True
    max_child_order_qty: Decimal | None = None
    max_participation_rate: Decimal | None = None
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="metadata",
        serialization_alias="metadata_json",
    )

    @model_validator(mode="after")
    def validate_policy_thresholds(self) -> "ExecutionPolicyConfig":
        if self.max_child_order_qty is not None and self.max_child_order_qty <= 0:
            raise ValueError("max_child_order_qty must be positive when provided")
        if self.max_participation_rate is not None and not (Decimal("0") < self.max_participation_rate <= Decimal("1")):
            raise ValueError("max_participation_rate must be within (0, 1] when provided")
        return self


class ProtectionPolicyConfig(BaseContractModel):
    policy_code: str = "default"
    scope_mode: ProtectionScope = ProtectionScope.POSITION
    trigger_basis: ProtectionTriggerBasis = ProtectionTriggerBasis.BAR_HIGH_LOW
    take_profit_bps: Decimal | None = None
    stop_loss_bps: Decimal | None = None
    trailing_stop_bps: Decimal | None = None
    time_exit_bars: int | None = None
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="metadata",
        serialization_alias="metadata_json",
    )

    @model_validator(mode="after")
    def validate_protection_thresholds(self) -> "ProtectionPolicyConfig":
        threshold_fields = (
            ("take_profit_bps", self.take_profit_bps),
            ("stop_loss_bps", self.stop_loss_bps),
            ("trailing_stop_bps", self.trailing_stop_bps),
        )
        for field_name, value in threshold_fields:
            if value is not None and value <= 0:
                raise ValueError(f"{field_name} must be positive when provided")
        if self.time_exit_bars is not None and self.time_exit_bars <= 0:
            raise ValueError("time_exit_bars must be positive when provided")
        return self


class RiskPolicyConfig(BaseContractModel):
    policy_code: str = "default"
    enforce_spot_cash_check: bool = True
    block_new_entries_below_equity: Decimal | None = Decimal("0")
    max_position_qty: Decimal | None = None
    max_order_qty: Decimal | None = None
    max_order_notional: Decimal | None = None
    max_gross_exposure_multiple: Decimal | None = None
    allow_reduce_only_when_blocked: bool = True
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="metadata",
        serialization_alias="metadata_json",
    )

    @model_validator(mode="after")
    def validate_risk_thresholds(self) -> "RiskPolicyConfig":
        if self.block_new_entries_below_equity is not None and self.block_new_entries_below_equity < 0:
            raise ValueError("block_new_entries_below_equity must be non-negative when provided")
        threshold_fields = (
            ("max_position_qty", self.max_position_qty),
            ("max_order_qty", self.max_order_qty),
            ("max_order_notional", self.max_order_notional),
            ("max_gross_exposure_multiple", self.max_gross_exposure_multiple),
        )
        for field_name, value in threshold_fields:
            if value is not None and value <= 0:
                raise ValueError(f"{field_name} must be positive when provided")
        return self


class StrategySessionConfig(BaseContractModel):
    session_code: str
    environment: Environment
    account_code: str
    strategy_code: str
    strategy_version: str
    exchange_code: str
    universe: list[str]
    netting_mode: PositionNettingMode = PositionNettingMode.ISOLATED_STRATEGY_SESSION
    execution_policy: ExecutionPolicyConfig = Field(default_factory=ExecutionPolicyConfig)
    protection_policy: ProtectionPolicyConfig = Field(default_factory=ProtectionPolicyConfig)
    risk_policy: RiskPolicyConfig = Field(default_factory=RiskPolicyConfig)
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="metadata",
        serialization_alias="metadata_json",
    )

    @model_validator(mode="after")
    def validate_session_config(self) -> "StrategySessionConfig":
        if not self.universe:
            raise ValueError("strategy sessions must include at least one instrument in universe")
        self.universe = list(dict.fromkeys(self.universe))
        return self


class BacktestRunConfig(BaseContractModel):
    run_name: str
    session: StrategySessionConfig
    start_time: datetime
    end_time: datetime
    bar_interval: str = "1m"
    initial_cash: Decimal = Decimal("100000")
    market_data_version: str = "md.bars_1m"
    fee_model_version: str = "ref_fee_schedule_v1"
    slippage_model_version: str = "fixed_bps_v1"
    latency_model_version: str = "bars_next_open_v1"
    strategy_params_json: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="strategy_params",
        serialization_alias="strategy_params_json",
    )
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="metadata",
        serialization_alias="metadata_json",
    )

    @model_validator(mode="after")
    def validate_run_config(self) -> "BacktestRunConfig":
        if self.session.environment != Environment.BACKTEST:
            raise ValueError("backtest run config requires a backtest strategy session")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if self.initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        if not self.bar_interval:
            raise ValueError("bar_interval must not be empty")
        return self
