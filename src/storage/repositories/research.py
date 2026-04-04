from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection


class CompareSetRepository:
    def upsert_compare_set(
        self,
        connection: Connection,
        *,
        compare_key: str,
        compare_name: str | None,
        benchmark_run_id: int | None,
        run_ids: list[int],
        compare_snapshot: dict[str, Any],
        actor_name: str,
    ) -> dict[str, Any]:
        row = connection.execute(
            text(
                """
                insert into backtest.compare_sets (
                    compare_key,
                    compare_name,
                    benchmark_run_id,
                    run_ids_json,
                    compare_snapshot_json,
                    created_by,
                    updated_by
                ) values (
                    :compare_key,
                    :compare_name,
                    :benchmark_run_id,
                    cast(:run_ids_json as jsonb),
                    cast(:compare_snapshot_json as jsonb),
                    :created_by,
                    :updated_by
                )
                on conflict (compare_key) do update
                set compare_name = excluded.compare_name,
                    benchmark_run_id = excluded.benchmark_run_id,
                    run_ids_json = excluded.run_ids_json,
                    compare_snapshot_json = excluded.compare_snapshot_json,
                    updated_by = excluded.updated_by,
                    updated_at = now()
                returning
                    compare_set_id,
                    compare_key,
                    compare_name,
                    benchmark_run_id,
                    run_ids_json,
                    compare_snapshot_json,
                    created_by,
                    updated_by,
                    created_at,
                    updated_at
                """
            ),
            {
                "compare_key": compare_key,
                "compare_name": compare_name,
                "benchmark_run_id": benchmark_run_id,
                "run_ids_json": json.dumps(run_ids),
                "compare_snapshot_json": json.dumps(compare_snapshot, default=str),
                "created_by": actor_name,
                "updated_by": actor_name,
            },
        ).mappings().one()
        return dict(row)

    def get_compare_set(self, connection: Connection, compare_set_id: int) -> dict[str, Any] | None:
        row = connection.execute(
            text(
                """
                select
                    compare_set_id,
                    compare_key,
                    compare_name,
                    benchmark_run_id,
                    run_ids_json,
                    compare_snapshot_json,
                    created_by,
                    updated_by,
                    created_at,
                    updated_at
                from backtest.compare_sets
                where compare_set_id = :compare_set_id
                """
            ),
            {"compare_set_id": compare_set_id},
        ).mappings().first()
        return dict(row) if row is not None else None


class AnnotationRepository:
    def upsert_system_annotation(
        self,
        connection: Connection,
        *,
        entity_type: str,
        entity_id: str,
        annotation_type: str,
        title: str,
        summary: str | None,
        status: str,
        verification_state: str,
        next_action: str | None,
        source_refs: dict[str, Any],
        facts_snapshot: dict[str, Any],
        actor_name: str,
    ) -> dict[str, Any]:
        row = connection.execute(
            text(
                """
                insert into research.annotations (
                    entity_type,
                    entity_id,
                    annotation_type,
                    status,
                    title,
                    summary,
                    note_source,
                    verification_state,
                    verified_findings_json,
                    open_questions_json,
                    next_action,
                    source_refs_json,
                    facts_snapshot_json,
                    created_by,
                    updated_by
                ) values (
                    :entity_type,
                    :entity_id,
                    :annotation_type,
                    :status,
                    :title,
                    :summary,
                    'system',
                    :verification_state,
                    '[]'::jsonb,
                    '[]'::jsonb,
                    :next_action,
                    cast(:source_refs_json as jsonb),
                    cast(:facts_snapshot_json as jsonb),
                    :created_by,
                    :updated_by
                )
                on conflict (entity_type, entity_id, annotation_type, note_source)
                where note_source = 'system'
                do update
                set status = excluded.status,
                    title = excluded.title,
                    summary = excluded.summary,
                    verification_state = excluded.verification_state,
                    next_action = excluded.next_action,
                    source_refs_json = excluded.source_refs_json,
                    facts_snapshot_json = excluded.facts_snapshot_json,
                    updated_by = excluded.updated_by,
                    updated_at = now()
                returning
                    annotation_id,
                    entity_type,
                    entity_id,
                    annotation_type,
                    status,
                    title,
                    summary,
                    note_source,
                    verification_state,
                    verified_findings_json,
                    open_questions_json,
                    next_action,
                    source_refs_json,
                    facts_snapshot_json,
                    created_by,
                    updated_by,
                    created_at,
                    updated_at
                """
            ),
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "annotation_type": annotation_type,
                "status": status,
                "title": title,
                "summary": summary,
                "verification_state": verification_state,
                "next_action": next_action,
                "source_refs_json": json.dumps(source_refs, default=str),
                "facts_snapshot_json": json.dumps(facts_snapshot, default=str),
                "created_by": actor_name,
                "updated_by": actor_name,
            },
        ).mappings().one()
        return dict(row)

    def create_annotation(
        self,
        connection: Connection,
        *,
        entity_type: str,
        entity_id: str,
        annotation_type: str,
        status: str,
        title: str,
        summary: str | None,
        note_source: str,
        verification_state: str,
        verified_findings: list[str],
        open_questions: list[str],
        next_action: str | None,
        source_refs: dict[str, Any],
        facts_snapshot: dict[str, Any],
        actor_name: str,
    ) -> dict[str, Any]:
        row = connection.execute(
            text(
                """
                insert into research.annotations (
                    entity_type,
                    entity_id,
                    annotation_type,
                    status,
                    title,
                    summary,
                    note_source,
                    verification_state,
                    verified_findings_json,
                    open_questions_json,
                    next_action,
                    source_refs_json,
                    facts_snapshot_json,
                    created_by,
                    updated_by
                ) values (
                    :entity_type,
                    :entity_id,
                    :annotation_type,
                    :status,
                    :title,
                    :summary,
                    :note_source,
                    :verification_state,
                    cast(:verified_findings_json as jsonb),
                    cast(:open_questions_json as jsonb),
                    :next_action,
                    cast(:source_refs_json as jsonb),
                    cast(:facts_snapshot_json as jsonb),
                    :created_by,
                    :updated_by
                )
                returning
                    annotation_id,
                    entity_type,
                    entity_id,
                    annotation_type,
                    status,
                    title,
                    summary,
                    note_source,
                    verification_state,
                    verified_findings_json,
                    open_questions_json,
                    next_action,
                    source_refs_json,
                    facts_snapshot_json,
                    created_by,
                    updated_by,
                    created_at,
                    updated_at
                """
            ),
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "annotation_type": annotation_type,
                "status": status,
                "title": title,
                "summary": summary,
                "note_source": note_source,
                "verification_state": verification_state,
                "verified_findings_json": json.dumps(verified_findings),
                "open_questions_json": json.dumps(open_questions),
                "next_action": next_action,
                "source_refs_json": json.dumps(source_refs, default=str),
                "facts_snapshot_json": json.dumps(facts_snapshot, default=str),
                "created_by": actor_name,
                "updated_by": actor_name,
            },
        ).mappings().one()
        return dict(row)

    def update_annotation(
        self,
        connection: Connection,
        *,
        annotation_id: int,
        status: str,
        title: str,
        summary: str | None,
        note_source: str,
        verification_state: str,
        verified_findings: list[str],
        open_questions: list[str],
        next_action: str | None,
        source_refs: dict[str, Any],
        actor_name: str,
    ) -> dict[str, Any] | None:
        row = connection.execute(
            text(
                """
                update research.annotations
                set status = :status,
                    title = :title,
                    summary = :summary,
                    note_source = :note_source,
                    verification_state = :verification_state,
                    verified_findings_json = cast(:verified_findings_json as jsonb),
                    open_questions_json = cast(:open_questions_json as jsonb),
                    next_action = :next_action,
                    source_refs_json = cast(:source_refs_json as jsonb),
                    updated_by = :updated_by,
                    updated_at = now()
                where annotation_id = :annotation_id
                returning
                    annotation_id,
                    entity_type,
                    entity_id,
                    annotation_type,
                    status,
                    title,
                    summary,
                    note_source,
                    verification_state,
                    verified_findings_json,
                    open_questions_json,
                    next_action,
                    source_refs_json,
                    facts_snapshot_json,
                    created_by,
                    updated_by,
                    created_at,
                    updated_at
                """
            ),
            {
                "annotation_id": annotation_id,
                "status": status,
                "title": title,
                "summary": summary,
                "note_source": note_source,
                "verification_state": verification_state,
                "verified_findings_json": json.dumps(verified_findings),
                "open_questions_json": json.dumps(open_questions),
                "next_action": next_action,
                "source_refs_json": json.dumps(source_refs, default=str),
                "updated_by": actor_name,
            },
        ).mappings().first()
        return dict(row) if row is not None else None

    def get_annotation(self, connection: Connection, annotation_id: int) -> dict[str, Any] | None:
        row = connection.execute(
            text(
                """
                select
                    annotation_id,
                    entity_type,
                    entity_id,
                    annotation_type,
                    status,
                    title,
                    summary,
                    note_source,
                    verification_state,
                    verified_findings_json,
                    open_questions_json,
                    next_action,
                    source_refs_json,
                    facts_snapshot_json,
                    created_by,
                    updated_by,
                    created_at,
                    updated_at
                from research.annotations
                where annotation_id = :annotation_id
                """
            ),
            {"annotation_id": annotation_id},
        ).mappings().first()
        return dict(row) if row is not None else None

    def list_annotations(
        self,
        connection: Connection,
        *,
        entity_type: str,
        entity_id: str,
        annotation_type: str | None = None,
    ) -> list[dict[str, Any]]:
        query = """
            select
                annotation_id,
                entity_type,
                entity_id,
                annotation_type,
                status,
                title,
                summary,
                note_source,
                verification_state,
                verified_findings_json,
                open_questions_json,
                next_action,
                source_refs_json,
                facts_snapshot_json,
                created_by,
                updated_by,
                created_at,
                updated_at
            from research.annotations
            where entity_type = :entity_type
              and entity_id = :entity_id
        """
        params: dict[str, Any] = {
            "entity_type": entity_type,
            "entity_id": entity_id,
        }
        if annotation_type is not None:
            query += " and annotation_type = :annotation_type"
            params["annotation_type"] = annotation_type
        query += " order by created_at asc, annotation_id asc"

        rows = connection.execute(text(query), params).mappings().all()
        return [dict(row) for row in rows]
