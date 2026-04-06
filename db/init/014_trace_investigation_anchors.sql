create table if not exists research.trace_investigation_anchors (
    anchor_id                 bigserial primary key,
    debug_trace_id            bigint not null references backtest.debug_traces(debug_trace_id) on delete cascade,
    scenario_id               text,
    expected_behavior         text,
    observed_behavior         text,
    created_by                text not null,
    updated_by                text not null,
    created_at                timestamptz not null default now(),
    updated_at                timestamptz not null default now()
);

create index if not exists idx_trace_investigation_anchors_trace_id
    on research.trace_investigation_anchors(debug_trace_id);
