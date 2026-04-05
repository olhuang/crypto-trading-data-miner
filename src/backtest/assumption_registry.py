from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from models.backtest import AssumptionBundleConfig, RiskPolicyOverrideConfig


@dataclass(frozen=True, slots=True)
class RegisteredAssumptionBundle:
    assumption_bundle_code: str
    assumption_bundle_version: str
    display_name: str
    description: str
    market_scope: str
    assumptions: AssumptionBundleConfig


class UnknownAssumptionBundleError(LookupError):
    """Raised when a named assumption bundle code/version is referenced but not registered."""


class AssumptionBundleRegistry:
    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], RegisteredAssumptionBundle] = {}

    def register(self, entry: RegisteredAssumptionBundle) -> None:
        self._entries[(entry.assumption_bundle_code, entry.assumption_bundle_version)] = entry

    def resolve(self, assumption_bundle_code: str, assumption_bundle_version: str | None = None) -> AssumptionBundleConfig:
        if assumption_bundle_version is not None:
            entry = self._entries.get((assumption_bundle_code, assumption_bundle_version))
            if entry is None:
                raise UnknownAssumptionBundleError(
                    f"unknown assumption bundle registry entry: {assumption_bundle_code}@{assumption_bundle_version}"
                )
            return entry.assumptions

        matching_entries = [
            entry
            for (bundle_code, _bundle_version), entry in self._entries.items()
            if bundle_code == assumption_bundle_code
        ]
        if not matching_entries:
            raise UnknownAssumptionBundleError(f"unknown assumption bundle registry entry: {assumption_bundle_code}")
        if len(matching_entries) > 1:
            matching_versions = ", ".join(sorted(entry.assumption_bundle_version for entry in matching_entries))
            raise UnknownAssumptionBundleError(
                f"assumption bundle version required for {assumption_bundle_code}; available versions: {matching_versions}"
            )
        return matching_entries[0].assumptions

    def list_entries(self) -> list[RegisteredAssumptionBundle]:
        return [
            self._entries[key]
            for key in sorted(
                self._entries,
                key=lambda item: (item[0], item[1]),
            )
        ]


@lru_cache(maxsize=1)
def build_default_assumption_bundle_registry() -> AssumptionBundleRegistry:
    registry = AssumptionBundleRegistry()
    registry.register(
        RegisteredAssumptionBundle(
            assumption_bundle_code="baseline_perp_research",
            assumption_bundle_version="v1",
            display_name="Baseline Perp Research",
            description="Starter perpetual-futures research bundle using the default bars-based execution assumptions.",
            market_scope="perp",
            assumptions=AssumptionBundleConfig(
                assumption_bundle_code="baseline_perp_research",
                assumption_bundle_version="v1",
                market_data_version="md.bars_1m",
                fee_model_version="ref_fee_schedule_v1",
                slippage_model_version="fixed_bps_v1",
                fill_model_version="deterministic_bars_v1",
                latency_model_version="bars_next_open_v1",
                feature_input_version="bars_only_v1",
                benchmark_set_code="btc_perp_baseline_v1",
                risk_policy=RiskPolicyOverrideConfig(policy_code="perp_medium_v1"),
            ),
        )
    )
    registry.register(
        RegisteredAssumptionBundle(
            assumption_bundle_code="baseline_spot_research",
            assumption_bundle_version="v1",
            display_name="Baseline Spot Research",
            description="Starter spot-research bundle using the default bars-based execution assumptions and conservative spot risk.",
            market_scope="spot",
            assumptions=AssumptionBundleConfig(
                assumption_bundle_code="baseline_spot_research",
                assumption_bundle_version="v1",
                market_data_version="md.bars_1m",
                fee_model_version="ref_fee_schedule_v1",
                slippage_model_version="fixed_bps_v1",
                fill_model_version="deterministic_bars_v1",
                latency_model_version="bars_next_open_v1",
                feature_input_version="bars_only_v1",
                benchmark_set_code="btc_spot_baseline_v1",
                risk_policy=RiskPolicyOverrideConfig(policy_code="spot_conservative_v1"),
            ),
        )
    )
    registry.register(
        RegisteredAssumptionBundle(
            assumption_bundle_code="aggressive_perp_execution",
            assumption_bundle_version="v1",
            display_name="Aggressive Perp Execution",
            description="Perpetual-futures bundle with the same bars-only input assumptions but a more aggressive session risk envelope.",
            market_scope="perp",
            assumptions=AssumptionBundleConfig(
                assumption_bundle_code="aggressive_perp_execution",
                assumption_bundle_version="v1",
                market_data_version="md.bars_1m",
                fee_model_version="ref_fee_schedule_v1",
                slippage_model_version="fixed_bps_v1",
                fill_model_version="deterministic_bars_v1",
                latency_model_version="bars_next_open_v1",
                feature_input_version="bars_only_v1",
                benchmark_set_code="btc_perp_baseline_v1",
                risk_policy=RiskPolicyOverrideConfig(policy_code="perp_aggressive_v1"),
            ),
        )
    )
    registry.register(
        RegisteredAssumptionBundle(
            assumption_bundle_code="baseline_perp_sentiment_research",
            assumption_bundle_version="v1",
            display_name="Baseline Perp Sentiment Research",
            description="Starter perpetual-futures research bundle that keeps the bars-based execution assumptions but exposes perp context and sentiment ratios to strategies.",
            market_scope="perp",
            assumptions=AssumptionBundleConfig(
                assumption_bundle_code="baseline_perp_sentiment_research",
                assumption_bundle_version="v1",
                market_data_version="md.bars_1m",
                fee_model_version="ref_fee_schedule_v1",
                slippage_model_version="fixed_bps_v1",
                fill_model_version="deterministic_bars_v1",
                latency_model_version="bars_next_open_v1",
                feature_input_version="bars_perp_context_v1",
                benchmark_set_code="btc_perp_baseline_v1",
                risk_policy=RiskPolicyOverrideConfig(policy_code="perp_medium_v1"),
            ),
        )
    )
    registry.register(
        RegisteredAssumptionBundle(
            assumption_bundle_code="stress_costs",
            assumption_bundle_version="v1",
            display_name="Stress Costs Placeholder",
            description="Placeholder lineage bundle for future higher-cost execution studies; the current Phase 5 foundation does not yet change runtime fee/slippage behavior beyond bundle identity.",
            market_scope="perp",
            assumptions=AssumptionBundleConfig(
                assumption_bundle_code="stress_costs",
                assumption_bundle_version="v1",
                market_data_version="md.bars_1m",
                fee_model_version="ref_fee_schedule_v1",
                slippage_model_version="fixed_bps_v1",
                fill_model_version="deterministic_bars_v1",
                latency_model_version="bars_next_open_v1",
                feature_input_version="bars_only_v1",
                benchmark_set_code="btc_perp_stress_costs_v1",
                risk_policy=RiskPolicyOverrideConfig(policy_code="perp_medium_v1"),
                metadata={
                    "notes": "current Phase D foundation keeps stress-cost identity in metadata while runtime model selection remains future work"
                },
            ),
        )
    )
    return registry
