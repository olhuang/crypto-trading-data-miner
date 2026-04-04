from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from typing import Any

from models.backtest import RiskPolicyConfig, RiskPolicyOverrideConfig


@dataclass(frozen=True, slots=True)
class RegisteredRiskPolicy:
    policy_code: str
    display_name: str
    description: str
    market_scope: str
    risk_policy: RiskPolicyConfig


class UnknownRiskPolicyError(LookupError):
    """Raised when a named risk policy code is referenced but not registered."""


class RiskPolicyRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, RegisteredRiskPolicy] = {}

    def register(self, entry: RegisteredRiskPolicy) -> None:
        self._entries[entry.policy_code] = entry

    def get(self, policy_code: str) -> RegisteredRiskPolicy:
        try:
            return self._entries[policy_code]
        except KeyError as exc:
            raise UnknownRiskPolicyError(f"unknown risk policy registry entry: {policy_code}") from exc

    def list_entries(self) -> list[RegisteredRiskPolicy]:
        ordered_codes = sorted(self._entries)
        if "default" in ordered_codes:
            ordered_codes.remove("default")
            ordered_codes = ["default", *ordered_codes]
        return [self._entries[policy_code] for policy_code in ordered_codes]

    def resolve_session_policy(self, policy: RiskPolicyConfig) -> RiskPolicyConfig:
        patch = policy.as_patch_dict(explicit_only=True)
        return self._resolve_base_policy(policy.policy_code, patch=patch)

    def apply_run_overrides(
        self,
        session_policy: RiskPolicyConfig,
        overrides: RiskPolicyOverrideConfig,
    ) -> RiskPolicyConfig:
        patch = overrides.as_patch_dict()
        override_policy_code = patch.get("policy_code")
        if override_policy_code and str(override_policy_code) in self._entries:
            return self._resolve_base_policy(str(override_policy_code), patch=patch)

        merged = session_policy.model_dump(mode="json", by_alias=True)
        return self._merge_patch(merged, patch)

    def _resolve_base_policy(
        self,
        policy_code: str,
        *,
        patch: dict[str, Any] | None = None,
    ) -> RiskPolicyConfig:
        patch = dict(patch or {})
        entry = self._entries.get(policy_code)
        if entry is None:
            non_identity_patch = {
                key: value
                for key, value in patch.items()
                if key not in {"policy_code", "metadata_json"}
            }
            if not non_identity_patch:
                raise UnknownRiskPolicyError(f"unknown risk policy registry entry: {policy_code}")
            merged = RiskPolicyConfig(policy_code=policy_code).model_dump(mode="json", by_alias=True)
            return self._merge_patch(merged, patch)

        merged = entry.risk_policy.model_dump(mode="json", by_alias=True)
        return self._merge_patch(merged, patch)

    @staticmethod
    def _merge_patch(base_payload: dict[str, Any], patch: dict[str, Any]) -> RiskPolicyConfig:
        merged = dict(base_payload)
        if patch.get("metadata_json"):
            merged_metadata = dict(merged.get("metadata_json") or {})
            merged_metadata.update(patch["metadata_json"])
            merged["metadata_json"] = merged_metadata
            patch = {key: value for key, value in patch.items() if key != "metadata_json"}
        merged.update(patch)
        return RiskPolicyConfig.model_validate(merged)


@lru_cache(maxsize=1)
def build_default_risk_policy_registry() -> RiskPolicyRegistry:
    registry = RiskPolicyRegistry()
    registry.register(
        RegisteredRiskPolicy(
            policy_code="default",
            display_name="Default",
            description="Baseline shared guardrails with only the built-in equity floor and spot cash checks enabled.",
            market_scope="shared",
            risk_policy=RiskPolicyConfig(),
        )
    )
    registry.register(
        RegisteredRiskPolicy(
            policy_code="spot_conservative_v1",
            display_name="Spot Conservative v1",
            description="Conservative spot research policy with cash checks plus tighter size and exposure caps.",
            market_scope="spot",
            risk_policy=RiskPolicyConfig(
                policy_code="spot_conservative_v1",
                max_position_qty=Decimal("0.25"),
                max_order_qty=Decimal("0.25"),
                max_order_notional=Decimal("25000"),
                max_gross_exposure_multiple=Decimal("1.0"),
                max_drawdown_pct=Decimal("0.20"),
                max_daily_loss_pct=Decimal("0.03"),
                max_leverage=Decimal("1.0"),
                cooldown_bars_after_stop=15,
            ),
        )
    )
    registry.register(
        RegisteredRiskPolicy(
            policy_code="perp_medium_v1",
            display_name="Perp Medium v1",
            description="Starter perpetual-futures policy for one-contract-class directional research with moderate gross exposure.",
            market_scope="perp",
            risk_policy=RiskPolicyConfig(
                policy_code="perp_medium_v1",
                max_position_qty=Decimal("1"),
                max_order_qty=Decimal("1"),
                max_order_notional=Decimal("100000"),
                max_gross_exposure_multiple=Decimal("1.5"),
                max_drawdown_pct=Decimal("0.25"),
                max_daily_loss_pct=Decimal("0.05"),
                max_leverage=Decimal("1.5"),
                cooldown_bars_after_stop=10,
            ),
        )
    )
    registry.register(
        RegisteredRiskPolicy(
            policy_code="perp_aggressive_v1",
            display_name="Perp Aggressive v1",
            description="Higher-envelope perpetual-futures policy for aggressive research runs while still honoring shared guardrails.",
            market_scope="perp",
            risk_policy=RiskPolicyConfig(
                policy_code="perp_aggressive_v1",
                max_position_qty=Decimal("2"),
                max_order_qty=Decimal("2"),
                max_order_notional=Decimal("250000"),
                max_gross_exposure_multiple=Decimal("3.0"),
                max_drawdown_pct=Decimal("0.35"),
                max_daily_loss_pct=Decimal("0.08"),
                max_leverage=Decimal("3.0"),
                cooldown_bars_after_stop=5,
            ),
        )
    )
    return registry
