create schema if not exists research;

create table if not exists backtest.compare_sets (
    compare_set_id         bigserial primary key,
    compare_key            text not null unique,
    compare_name           text,
    benchmark_run_id       bigint references backtest.runs(run_id),
    run_ids_json           jsonb not null,
    compare_snapshot_json  jsonb not null,
    created_by             text not null,
    updated_by             text not null,
    created_at             timestamptz not null default now(),
    updated_at             timestamptz not null default now()
);

create index if not exists idx_compare_sets_created_at
    on backtest.compare_sets(created_at desc);

create table if not exists research.annotations (
    annotation_id            bigserial primary key,
    entity_type              text not null,
    entity_id                text not null,
    annotation_type          text not null,
    status                   text not null,
    title                    text not null,
    summary                  text,
    note_source              text not null,
    verification_state       text not null,
    verified_findings_json   jsonb not null default '[]'::jsonb,
    open_questions_json      jsonb not null default '[]'::jsonb,
    next_action              text,
    source_refs_json         jsonb not null default '{}'::jsonb,
    facts_snapshot_json      jsonb not null default '{}'::jsonb,
    created_by               text not null,
    updated_by               text not null,
    created_at               timestamptz not null default now(),
    updated_at               timestamptz not null default now()
);

create index if not exists idx_annotations_entity
    on research.annotations(entity_type, entity_id, created_at desc);

create unique index if not exists uq_annotations_system_note
    on research.annotations(entity_type, entity_id, annotation_type, note_source)
    where note_source = 'system';
