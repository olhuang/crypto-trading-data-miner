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
    max_drawdown_pct: Decimal | None = None
    max_daily_loss_pct: Decimal | None = None
    max_leverage: Decimal | None = None
    cooldown_bars_after_stop: int | None = None
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
            ("max_leverage", self.max_leverage),
        )
        for field_name, value in threshold_fields:
            if value is not None and value <= 0:
                raise ValueError(f"{field_name} must be positive when provided")
        percentage_fields = (
            ("max_drawdown_pct", self.max_drawdown_pct),
            ("max_daily_loss_pct", self.max_daily_loss_pct),
        )
        for field_name, value in percentage_fields:
            if value is not None and not (Decimal("0") < value <= Decimal("1")):
                raise ValueError(f"{field_name} must be within (0, 1] when provided")
        if self.cooldown_bars_after_stop is not None and self.cooldown_bars_after_stop <= 0:
            raise ValueError("cooldown_bars_after_stop must be positive when provided")
        return self

    def as_patch_dict(self, *, explicit_only: bool = False) -> dict[str, Any]:
        payload = self.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
            exclude_unset=explicit_only,
        )
        if not payload.get("metadata_json"):
            payload.pop("metadata_json", None)
        return payload


class RiskPolicyOverrideConfig(BaseContractModel):
    policy_code: str | None = None
    enforce_spot_cash_check: bool | None = None
    block_new_entries_below_equity: Decimal | None = None
    max_position_qty: Decimal | None = None
    max_order_qty: Decimal | None = None
    max_order_notional: Decimal | None = None
    max_gross_exposure_multiple: Decimal | None = None
    max_drawdown_pct: Decimal | None = None
    max_daily_loss_pct: Decimal | None = None
    max_leverage: Decimal | None = None
    cooldown_bars_after_stop: int | None = None
    allow_reduce_only_when_blocked: bool | None = None
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="metadata",
        serialization_alias="metadata_json",
    )

    @model_validator(mode="after")
    def validate_override_thresholds(self) -> "RiskPolicyOverrideConfig":
        if self.block_new_entries_below_equity is not None and self.block_new_entries_below_equity < 0:
            raise ValueError("block_new_entries_below_equity must be non-negative when provided")
        threshold_fields = (
            ("max_position_qty", self.max_position_qty),
            ("max_order_qty", self.max_order_qty),
            ("max_order_notional", self.max_order_notional),
            ("max_gross_exposure_multiple", self.max_gross_exposure_multiple),
            ("max_leverage", self.max_leverage),
        )
        for field_name, value in threshold_fields:
            if value is not None and value <= 0:
                raise ValueError(f"{field_name} must be positive when provided")
        percentage_fields = (
            ("max_drawdown_pct", self.max_drawdown_pct),
            ("max_daily_loss_pct", self.max_daily_loss_pct),
        )
        for field_name, value in percentage_fields:
            if value is not None and not (Decimal("0") < value <= Decimal("1")):
                raise ValueError(f"{field_name} must be within (0, 1] when provided")
        if self.cooldown_bars_after_stop is not None and self.cooldown_bars_after_stop <= 0:
            raise ValueError("cooldown_bars_after_stop must be positive when provided")
        return self

    def as_patch_dict(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json", by_alias=True, exclude_none=True)
        if not payload.get("metadata_json"):
            payload.pop("metadata_json", None)
        return payload


class AssumptionBundleConfig(BaseContractModel):
    assumption_bundle_code: str | None = None
    assumption_bundle_version: str | None = None
    market_data_version: str = "md.bars_1m"
    fee_model_version: str = "ref_fee_schedule_v1"
    slippage_model_version: str = "fixed_bps_v1"
    fill_model_version: str = "deterministic_bars_v1"
    latency_model_version: str = "bars_next_open_v1"
    feature_input_version: str = "bars_only_v1"
    benchmark_set_code: str | None = None
    risk_policy: RiskPolicyOverrideConfig = Field(default_factory=RiskPolicyOverrideConfig)
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="metadata",
        serialization_alias="metadata_json",
    )

    @model_validator(mode="after")
    def validate_assumption_bundle(self) -> "AssumptionBundleConfig":
        if self.assumption_bundle_code is not None and not self.assumption_bundle_code.strip():
            raise ValueError("assumption_bundle_code must not be empty when provided")
        if self.assumption_bundle_version is not None and not self.assumption_bundle_version.strip():
            raise ValueError("assumption_bundle_version must not be empty when provided")
        if self.assumption_bundle_version is not None and self.assumption_bundle_code is None:
            raise ValueError("assumption_bundle_version requires assumption_bundle_code")
        for field_name in (
            "market_data_version",
            "fee_model_version",
            "slippage_model_version",
            "fill_model_version",
            "latency_model_version",
            "feature_input_version",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must not be empty")
        if self.benchmark_set_code is not None and not self.benchmark_set_code.strip():
            raise ValueError("benchmark_set_code must not be empty when provided")
        return self

    def as_patch_dict(self, *, explicit_only: bool = False) -> dict[str, Any]:
        payload = self.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
            exclude_unset=explicit_only,
        )
        if not payload.get("metadata_json"):
            payload.pop("metadata_json", None)
        risk_policy = payload.get("risk_policy")
        if isinstance(risk_policy, dict) and not risk_policy:
            payload.pop("risk_policy", None)
        return payload


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
    fill_model_version: str = "deterministic_bars_v1"
    latency_model_version: str = "bars_next_open_v1"
    feature_input_version: str = "bars_only_v1"
    benchmark_set_code: str | None = None
    assumption_bundle_code: str | None = None
    assumption_bundle_version: str | None = None
    risk_overrides: RiskPolicyOverrideConfig = Field(default_factory=RiskPolicyOverrideConfig)
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
        if self.assumption_bundle_code is not None and not self.assumption_bundle_code.strip():
            raise ValueError("assumption_bundle_code must not be empty when provided")
        if self.assumption_bundle_version is not None and not self.assumption_bundle_version.strip():
            raise ValueError("assumption_bundle_version must not be empty when provided")
        if not self.fee_model_version:
            raise ValueError("fee_model_version must not be empty")
        if not self.slippage_model_version:
            raise ValueError("slippage_model_version must not be empty")
        if not self.fill_model_version:
            raise ValueError("fill_model_version must not be empty")
        if not self.latency_model_version:
            raise ValueError("latency_model_version must not be empty")
        if not self.feature_input_version:
            raise ValueError("feature_input_version must not be empty")
        if self.benchmark_set_code is not None and not self.benchmark_set_code.strip():
            raise ValueError("benchmark_set_code must not be empty when provided")
        return self

    def build_assumption_overrides(self) -> dict[str, Any]:
        overrides: dict[str, Any] = {}
        for field_name in (
            "market_data_version",
            "fee_model_version",
            "slippage_model_version",
            "fill_model_version",
            "latency_model_version",
            "feature_input_version",
            "benchmark_set_code",
        ):
            if field_name in self.model_fields_set:
                value = getattr(self, field_name)
                if value is not None:
                    overrides[field_name] = value
        return overrides

    def resolve_selected_assumption_bundle(self) -> AssumptionBundleConfig | None:
        if self.assumption_bundle_code is None:
            return None

        from backtest.assumption_registry import build_default_assumption_bundle_registry

        registry = build_default_assumption_bundle_registry()
        return registry.resolve(self.assumption_bundle_code, self.assumption_bundle_version)

    def build_effective_assumption_snapshot(self) -> AssumptionBundleConfig:
        base_payload = AssumptionBundleConfig(
            assumption_bundle_code=self.assumption_bundle_code,
            assumption_bundle_version=self.assumption_bundle_version,
        ).model_dump(mode="json", by_alias=True, exclude_none=True)

        selected_bundle = self.resolve_selected_assumption_bundle()
        if selected_bundle is not None:
            bundle_payload = selected_bundle.model_dump(mode="json", by_alias=True, exclude_none=True)
            base_payload = _merge_assumption_payload(base_payload, bundle_payload)

        override_payload = self.build_assumption_overrides()
        if override_payload:
            base_payload = _merge_assumption_payload(base_payload, override_payload)

        return AssumptionBundleConfig.model_validate(base_payload)

    def resolve_session_risk_policy(self) -> RiskPolicyConfig:
        from backtest.risk_registry import build_default_risk_policy_registry

        registry = build_default_risk_policy_registry()
        return registry.resolve_session_policy(self.session.risk_policy)

    def build_effective_risk_policy(self) -> RiskPolicyConfig:
        from backtest.risk_registry import build_default_risk_policy_registry

        registry = build_default_risk_policy_registry()
        session_policy = self.resolve_session_risk_policy()
        effective_assumptions = self.build_effective_assumption_snapshot()
        assumption_risk_policy = effective_assumptions.risk_policy
        if assumption_risk_policy.as_patch_dict():
            session_policy = registry.apply_run_overrides(session_policy, assumption_risk_policy)
        return registry.apply_run_overrides(session_policy, self.risk_overrides)


def _merge_assumption_payload(base_payload: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base_payload)
    patch = dict(patch)
    if patch.get("metadata_json"):
        merged_metadata = dict(merged.get("metadata_json") or {})
        merged_metadata.update(patch["metadata_json"])
        merged["metadata_json"] = merged_metadata
        patch.pop("metadata_json", None)
    if patch.get("risk_policy"):
        merged_risk_policy = dict(merged.get("risk_policy") or {})
        merged_risk_policy.update(patch["risk_policy"])
        merged["risk_policy"] = merged_risk_policy
        patch.pop("risk_policy", None)
    merged.update(patch)
    return merged
