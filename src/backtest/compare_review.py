from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any

from backtest.compare import BacktestCompareSet
from storage.repositories.research import AnnotationRepository, CompareSetRepository


class CompareReviewAnnotationError(ValueError):
    pass


class CompareReviewNotFoundError(LookupError):
    pass


class CompareReviewService:
    def __init__(
        self,
        *,
        compare_set_repository: CompareSetRepository | None = None,
        annotation_repository: AnnotationRepository | None = None,
    ) -> None:
        self.compare_set_repository = compare_set_repository or CompareSetRepository()
        self.annotation_repository = annotation_repository or AnnotationRepository()

    def persist_compare_set(
        self,
        connection,
        *,
        compare_set: BacktestCompareSet,
        actor_name: str,
    ) -> BacktestCompareSet:
        compare_snapshot = self._build_compare_snapshot(compare_set)
        compare_key = self._build_compare_key(compare_set)
        compare_row = self.compare_set_repository.upsert_compare_set(
            connection,
            compare_key=compare_key,
            compare_name=compare_set.compare_name,
            benchmark_run_id=compare_set.benchmark_run_id,
            run_ids=compare_set.run_ids,
            compare_snapshot=compare_snapshot,
            actor_name=actor_name,
        )
        compare_set_id = int(compare_row["compare_set_id"])
        self.annotation_repository.upsert_system_annotation(
            connection,
            entity_type="compare_set",
            entity_id=str(compare_set_id),
            annotation_type="review",
            title=self._build_seed_title(compare_set),
            summary="System-seeded compare review draft with KPI, assumption, benchmark, and diagnostics facts.",
            status="draft",
            verification_state="system_fact",
            next_action="Review KPI and assumption diffs, then record verified findings and rerun/promote decision.",
            source_refs={
                "compare_set_id": compare_set_id,
                "run_ids": compare_set.run_ids,
                "benchmark_run_id": compare_set.benchmark_run_id,
            },
            facts_snapshot=compare_snapshot,
            actor_name=actor_name,
        )
        return replace(compare_set, compare_set_id=compare_set_id, persisted=True)

    def list_compare_notes(self, connection, *, compare_set_id: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        compare_row = self.compare_set_repository.get_compare_set(connection, compare_set_id)
        if compare_row is None:
            raise CompareReviewNotFoundError(f"compare set not found: {compare_set_id}")
        notes = self.annotation_repository.list_annotations(
            connection,
            entity_type="compare_set",
            entity_id=str(compare_set_id),
        )
        return compare_row, notes

    def create_or_update_compare_note(
        self,
        connection,
        *,
        compare_set_id: int,
        annotation_id: int | None,
        annotation_type: str,
        status: str,
        title: str,
        summary: str | None,
        note_source: str,
        verification_state: str,
        verified_findings: list[str],
        open_questions: list[str],
        next_action: str | None,
        actor_name: str,
    ) -> dict[str, Any]:
        compare_row = self.compare_set_repository.get_compare_set(connection, compare_set_id)
        if compare_row is None:
            raise CompareReviewNotFoundError(f"compare set not found: {compare_set_id}")

        compare_snapshot = dict(compare_row.get("compare_snapshot_json") or {})
        source_refs = {
            "compare_set_id": compare_set_id,
            "run_ids": list(compare_row.get("run_ids_json") or []),
            "benchmark_run_id": compare_row.get("benchmark_run_id"),
        }

        if annotation_id is None:
            return self.annotation_repository.create_annotation(
                connection,
                entity_type="compare_set",
                entity_id=str(compare_set_id),
                annotation_type=annotation_type,
                status=status,
                title=title,
                summary=summary,
                note_source=note_source,
                verification_state=verification_state,
                verified_findings=verified_findings,
                open_questions=open_questions,
                next_action=next_action,
                source_refs=source_refs,
                facts_snapshot=compare_snapshot,
                actor_name=actor_name,
            )

        existing = self.annotation_repository.get_annotation(connection, annotation_id)
        if existing is None or existing["entity_type"] != "compare_set" or existing["entity_id"] != str(compare_set_id):
            raise CompareReviewNotFoundError(f"compare note not found: {annotation_id}")
        if existing["note_source"] == "system":
            raise CompareReviewAnnotationError("system-seeded compare notes are read-only; create a human/agent review note instead")

        return self.annotation_repository.update_annotation(
            connection,
            annotation_id=annotation_id,
            status=status,
            title=title,
            summary=summary,
            note_source=note_source,
            verification_state=verification_state,
            verified_findings=verified_findings,
            open_questions=open_questions,
            next_action=next_action,
            source_refs=source_refs,
            actor_name=actor_name,
        ) or existing

    def _build_compare_key(self, compare_set: BacktestCompareSet) -> str:
        identity_payload = {
            "compare_name": compare_set.compare_name,
            "run_ids": compare_set.run_ids,
            "benchmark_run_id": compare_set.benchmark_run_id,
        }
        return hashlib.sha256(
            json.dumps(identity_payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()

    def _build_seed_title(self, compare_set: BacktestCompareSet) -> str:
        if compare_set.compare_name:
            return f"{compare_set.compare_name} review"
        return f"Compare review for runs {', '.join(str(run_id) for run_id in compare_set.run_ids)}"

    def _build_compare_snapshot(self, compare_set: BacktestCompareSet) -> dict[str, Any]:
        return {
            "compare_name": compare_set.compare_name,
            "run_ids": compare_set.run_ids,
            "benchmark_run_id": compare_set.benchmark_run_id,
            "available_period_types": compare_set.available_period_types,
            "compared_runs": [
                {
                    "run_id": run.run_id,
                    "run_name": run.run_name,
                    "strategy_code": run.strategy_code,
                    "strategy_version": run.strategy_version,
                    "account_code": run.account_code,
                    "environment": run.environment,
                    "status": run.status,
                    "start_time": run.start_time.isoformat(),
                    "end_time": run.end_time.isoformat(),
                    "universe": run.universe,
                    "diagnostic_status": run.diagnostic_status,
                    "total_return": None if run.total_return is None else str(run.total_return),
                    "annualized_return": None if run.annualized_return is None else str(run.annualized_return),
                    "max_drawdown": None if run.max_drawdown is None else str(run.max_drawdown),
                    "turnover": None if run.turnover is None else str(run.turnover),
                    "win_rate": None if run.win_rate is None else str(run.win_rate),
                    "fee_cost": None if run.fee_cost is None else str(run.fee_cost),
                    "slippage_cost": None if run.slippage_cost is None else str(run.slippage_cost),
                }
                for run in compare_set.compared_runs
            ],
            "assumption_diffs": [
                {
                    "field_name": diff.field_name,
                    "distinct_value_count": diff.distinct_value_count,
                    "values_by_run": [
                        {
                            "run_id": value.run_id,
                            "value": value.value,
                        }
                        for value in diff.values_by_run
                    ],
                }
                for diff in compare_set.assumption_diffs
            ],
            "benchmark_deltas": [
                {
                    "run_id": delta.run_id,
                    "benchmark_run_id": delta.benchmark_run_id,
                    "total_return_delta": None if delta.total_return_delta is None else str(delta.total_return_delta),
                    "annualized_return_delta": None if delta.annualized_return_delta is None else str(delta.annualized_return_delta),
                    "max_drawdown_delta": None if delta.max_drawdown_delta is None else str(delta.max_drawdown_delta),
                    "turnover_delta": None if delta.turnover_delta is None else str(delta.turnover_delta),
                    "win_rate_delta": None if delta.win_rate_delta is None else str(delta.win_rate_delta),
                }
                for delta in compare_set.benchmark_deltas
            ],
            "diagnostics_snapshot": {
                "statuses_by_run": [
                    {
                        "run_id": run.run_id,
                        "diagnostic_status": run.diagnostic_status,
                    }
                    for run in compare_set.compared_runs
                ],
                "comparison_flags": [
                    {
                        "code": flag.code,
                        "severity": flag.severity,
                        "message": flag.message,
                    }
                    for flag in compare_set.comparison_flags
                ],
            },
        }
