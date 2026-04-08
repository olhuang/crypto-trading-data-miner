from __future__ import annotations

from collections import Counter
from typing import Any

from storage.repositories.backtest import BacktestRunRepository
from storage.repositories.research import AnnotationRepository


class TraceInvestigationNoteError(ValueError):
    pass


class TraceInvestigationNotFoundError(LookupError):
    pass


class TraceInvestigationNoteService:
    def __init__(
        self,
        *,
        backtest_run_repository: BacktestRunRepository | None = None,
        annotation_repository: AnnotationRepository | None = None,
    ) -> None:
        self.backtest_run_repository = backtest_run_repository or BacktestRunRepository()
        self.annotation_repository = annotation_repository or AnnotationRepository()

    def list_trace_notes(
        self,
        connection,
        *,
        run_id: int,
        debug_trace_id: int,
        actor_name: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        trace_row = self._require_trace(connection, run_id=run_id, debug_trace_id=debug_trace_id)
        self.annotation_repository.upsert_system_annotation(
            connection,
            entity_type="debug_trace",
            entity_id=str(debug_trace_id),
            annotation_type="investigation",
            title=self._build_seed_title(trace_row),
            summary="System-seeded trace investigation draft with step facts, risk evidence, and existing anchors.",
            status="draft",
            verification_state="system_fact",
            next_action="Review trace evidence, then record expected vs observed behavior and the next debugging step.",
            source_refs=self._build_source_refs(trace_row),
            facts_snapshot=self._build_facts_snapshot(trace_row),
            actor_name=actor_name,
        )
        notes = self.annotation_repository.list_annotations(
            connection,
            entity_type="debug_trace",
            entity_id=str(debug_trace_id),
        )
        return trace_row, notes

    def create_or_update_trace_note(
        self,
        connection,
        *,
        run_id: int,
        debug_trace_id: int,
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
        trace_row = self._require_trace(connection, run_id=run_id, debug_trace_id=debug_trace_id)
        source_refs = self._build_source_refs(trace_row)
        facts_snapshot = self._build_facts_snapshot(trace_row)

        if annotation_id is None:
            return self.annotation_repository.create_annotation(
                connection,
                entity_type="debug_trace",
                entity_id=str(debug_trace_id),
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
                facts_snapshot=facts_snapshot,
                actor_name=actor_name,
            )

        existing = self.annotation_repository.get_annotation(connection, annotation_id)
        if existing is None or existing["entity_type"] != "debug_trace" or existing["entity_id"] != str(debug_trace_id):
            raise TraceInvestigationNotFoundError(f"trace investigation note not found: {annotation_id}")
        if existing["note_source"] == "system":
            raise TraceInvestigationNoteError(
                "system-seeded trace investigation notes are read-only; create a human/agent investigation note instead"
            )

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

    def build_expected_vs_observed_overview(
        self,
        connection,
        *,
        run_id: int,
    ) -> dict[str, Any]:
        run_row = self.backtest_run_repository.get_run(connection, run_id)
        if run_row is None:
            raise TraceInvestigationNotFoundError(f"backtest run not found: {run_id}")

        annotation_rows = self.annotation_repository.list_debug_trace_annotations_for_run(connection, run_id=run_id)
        items: list[dict[str, Any]] = []
        status_counts: Counter[str] = Counter()
        annotation_type_counts: Counter[str] = Counter()
        note_source_counts: Counter[str] = Counter()
        scenario_counts: Counter[str] = Counter()
        trace_ids_with_notes: set[int] = set()

        for row in annotation_rows:
            status = str(row["status"])
            annotation_type = str(row["annotation_type"])
            note_source = str(row["note_source"])
            source_refs = dict(row.get("source_refs_json") or {})
            scenario_ids = list(source_refs.get("scenario_ids") or [])

            status_counts[status] += 1
            annotation_type_counts[annotation_type] += 1
            note_source_counts[note_source] += 1
            for scenario_id in scenario_ids:
                scenario_counts[str(scenario_id)] += 1

            debug_trace_id = int(row["debug_trace_id"])
            trace_ids_with_notes.add(debug_trace_id)
            items.append(
                {
                    "annotation_id": int(row["annotation_id"]),
                    "debug_trace_id": debug_trace_id,
                    "step_index": int(row["step_index"]),
                    "bar_time": row["bar_time"].isoformat(),
                    "unified_symbol": str(row["unified_symbol"]),
                    "annotation_type": annotation_type,
                    "status": status,
                    "note_source": note_source,
                    "verification_state": str(row["verification_state"]),
                    "title": str(row["title"]),
                    "summary": row.get("summary"),
                    "verified_findings": list(row.get("verified_findings_json") or []),
                    "open_questions": list(row.get("open_questions_json") or []),
                    "next_action": row.get("next_action"),
                    "scenario_ids": scenario_ids,
                    "source_refs_json": source_refs,
                    "facts_snapshot_json": dict(row.get("facts_snapshot_json") or {}),
                    "created_at": row["created_at"].isoformat(),
                    "updated_at": row["updated_at"].isoformat(),
                }
            )

        total_trace_count = self.backtest_run_repository.count_debug_traces(connection, run_id=run_id)
        notes_with_expected_observed = sum(
            1
            for item in items
            if item["annotation_type"] == "expected_vs_observed"
            or bool(item["source_refs_json"].get("scenario_ids"))
        )
        unresolved_count = sum(1 for item in items if item["status"] not in {"resolved", "accepted", "rejected"})

        return {
            "run_id": run_id,
            "run_name": run_row.get("run_name"),
            "total_trace_count": total_trace_count,
            "trace_count_with_notes": len(trace_ids_with_notes),
            "total_note_count": len(items),
            "expected_vs_observed_note_count": notes_with_expected_observed,
            "unresolved_note_count": unresolved_count,
            "status_counts": dict(status_counts),
            "annotation_type_counts": dict(annotation_type_counts),
            "note_source_counts": dict(note_source_counts),
            "scenario_counts": dict(scenario_counts),
            "items": items,
        }

    def _require_trace(self, connection, *, run_id: int, debug_trace_id: int) -> dict[str, Any]:
        trace_row = self.backtest_run_repository.get_debug_trace_record(
            connection,
            run_id=run_id,
            debug_trace_id=debug_trace_id,
        )
        if trace_row is None:
            raise TraceInvestigationNotFoundError(
                f"debug trace not found for run: run_id={run_id}, debug_trace_id={debug_trace_id}"
            )
        return trace_row

    def _build_seed_title(self, trace_row: dict[str, Any]) -> str:
        return (
            f"Trace {trace_row['step_index']} investigation "
            f"for {trace_row['unified_symbol']} @ {trace_row['bar_time'].isoformat()}"
        )

    def _build_source_refs(self, trace_row: dict[str, Any]) -> dict[str, Any]:
        anchors = list(trace_row.get("investigation_anchors_json") or [])
        return {
            "run_id": int(trace_row["run_id"]),
            "debug_trace_id": int(trace_row["debug_trace_id"]),
            "step_index": int(trace_row["step_index"]),
            "unified_symbol": str(trace_row["unified_symbol"]),
            "bar_time": trace_row["bar_time"].isoformat(),
            "anchor_ids": [int(anchor["anchor_id"]) for anchor in anchors if anchor.get("anchor_id") is not None],
            "scenario_ids": [anchor["scenario_id"] for anchor in anchors if anchor.get("scenario_id")],
        }

    def _build_facts_snapshot(self, trace_row: dict[str, Any]) -> dict[str, Any]:
        anchors = []
        for anchor in trace_row.get("investigation_anchors_json") or []:
            anchors.append(
                {
                    "anchor_id": int(anchor["anchor_id"]),
                    "scenario_id": anchor.get("scenario_id"),
                    "expected_behavior": anchor.get("expected_behavior"),
                    "observed_behavior": anchor.get("observed_behavior"),
                    "created_at": anchor["created_at"].isoformat()
                    if hasattr(anchor.get("created_at"), "isoformat")
                    else anchor.get("created_at"),
                    "updated_at": anchor["updated_at"].isoformat()
                    if hasattr(anchor.get("updated_at"), "isoformat")
                    else anchor.get("updated_at"),
                }
            )

        return {
            "run_id": int(trace_row["run_id"]),
            "debug_trace_id": int(trace_row["debug_trace_id"]),
            "step_index": int(trace_row["step_index"]),
            "bar_time": trace_row["bar_time"].isoformat(),
            "unified_symbol": str(trace_row["unified_symbol"]),
            "close_price": str(trace_row["close_price"]),
            "signal_count": int(trace_row["signal_count"]),
            "intent_count": int(trace_row["intent_count"]),
            "blocked_intent_count": int(trace_row["blocked_intent_count"]),
            "created_order_count": int(trace_row["created_order_count"]),
            "fill_count": int(trace_row["fill_count"]),
            "blocked_codes": list(trace_row.get("blocked_codes_json") or []),
            "market_context": dict(trace_row.get("market_context_json") or {}),
            "decision": dict(trace_row.get("decision_json") or {}),
            "risk_outcomes": list(trace_row.get("risk_outcomes_json") or []),
            "investigation_anchors": anchors,
        }
