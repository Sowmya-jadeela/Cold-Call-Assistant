
create extension if not exists pgcrypto;

create table if not exists public.calls (
    id uuid primary key default gen_random_uuid(),
    prospect_name text not null,
    company text not null default '',
    caller_name text not null default '',
    status text not null default 'in_progress'
        check (status in ('in_progress', 'completed')),
    current_stage integer not null default 1
        check (current_stage between 1 and 8),
    outcome text,
    summary text not null default '',
    created_at timestamptz not null default now(),
    closed_at timestamptz
);

create table if not exists public.stage_results (
    id uuid primary key default gen_random_uuid(),
    call_id uuid not null references public.calls(id)
        on delete cascade,
    stage_number integer not null
        check (stage_number between 1 and 8),
    stage_name text not null,
    what_happened text not null
        check (
            what_happened in (
                'completed', 'positive', 'objection',
                'skipped', 'ended', 'follow_up'
            )
        ),
    prospect_words text not null default '',
    notes text not null default '',
    created_at timestamptz not null default now(),
    unique (call_id, stage_number)
);

create index if not exists idx_calls_created_at
    on public.calls(created_at desc);

create index if not exists idx_stage_results_call_id
    on public.stage_results(call_id);
