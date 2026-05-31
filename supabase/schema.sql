-- ============================================================
--  AI Business Enterprise - Supabase Schema
--  इसे Supabase Dashboard -> SQL Editor में paste करके Run करें
-- ============================================================

-- UUID generation extension (Supabase में आम तौर पर पहले से होता है)
create extension if not exists "pgcrypto";

-- ------------------------------------------------------------
-- agents: कौन-कौन से agent types हैं (metadata/registry)
-- ------------------------------------------------------------
create table if not exists public.agents (
    id          uuid primary key default gen_random_uuid(),
    agent_type  text not null unique,          -- research / strategy / dev / sales / delivery
    name        text not null,
    role        text,
    is_active   boolean not null default true,
    created_at  timestamptz not null default now()
);

-- ------------------------------------------------------------
-- tasks: orchestrator इसी टेबल को poll करता है
-- ------------------------------------------------------------
create table if not exists public.tasks (
    id          uuid primary key default gen_random_uuid(),
    title       text not null,
    agent_type  text not null,                 -- किस agent को करना है
    payload     jsonb not null default '{}'::jsonb,
    priority    int  not null default 0,       -- ज़्यादा = पहले
    status      text not null default 'pending', -- pending|in_progress|completed|failed
    result      jsonb,
    error       text,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

create index if not exists tasks_status_idx   on public.tasks (status);
create index if not exists tasks_priority_idx on public.tasks (priority desc, created_at);

-- updated_at auto-update trigger
create or replace function public.set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists trg_tasks_updated_at on public.tasks;
create trigger trg_tasks_updated_at
    before update on public.tasks
    for each row execute function public.set_updated_at();

-- ------------------------------------------------------------
-- task_logs: हर task पर agent की activity का audit trail
-- ------------------------------------------------------------
create table if not exists public.task_logs (
    id          uuid primary key default gen_random_uuid(),
    task_id     uuid references public.tasks(id) on delete cascade,
    agent_name  text,
    level       text not null default 'info',
    message     text,
    created_at  timestamptz not null default now()
);

create index if not exists task_logs_task_idx on public.task_logs (task_id);

-- ------------------------------------------------------------
-- Seed: 5 core agents
-- ------------------------------------------------------------
insert into public.agents (agent_type, name, role) values
    ('research', 'Research Agent',  'Market Research Analyst'),
    ('strategy', 'Strategy Agent',  'Business Strategy Lead'),
    ('dev',      'Dev Agent',       'Software Engineer'),
    ('sales',    'Sales Agent',     'Sales & Outreach Specialist'),
    ('delivery', 'Delivery Agent',  'Delivery & Client Success Manager')
on conflict (agent_type) do nothing;

-- ------------------------------------------------------------
-- services: company की services (website Aitotech से दिखाने के लिए)
-- ------------------------------------------------------------
create table if not exists public.services (
    id          uuid primary key default gen_random_uuid(),
    slug        text not null unique,          -- url-friendly id
    name        text not null,
    description text,
    price       text,                          -- "₹49,999/mo" जैसा free-form
    is_active   boolean not null default true,
    sort_order  int not null default 0,
    created_at  timestamptz not null default now()
);

-- ------------------------------------------------------------
-- leads: website Aitotech के contact/inquiry forms से आने वाले leads
-- ------------------------------------------------------------
create table if not exists public.leads (
    id           uuid primary key default gen_random_uuid(),
    name         text,
    email        text,
    phone        text,
    company      text,
    message      text,
    service_slug text,                         -- किस service में interest
    source       text not null default 'website', -- website / aitotech / api
    status       text not null default 'new',  -- new|contacted|qualified|closed
    task_id      uuid references public.tasks(id) on delete set null,
    created_at   timestamptz not null default now()
);

create index if not exists leads_status_idx on public.leads (status);
create index if not exists leads_created_idx on public.leads (created_at desc);

-- ------------------------------------------------------------
-- Seed: Aitotech की sample services (अपने हिसाब से edit करें)
-- ------------------------------------------------------------
insert into public.services (slug, name, description, price, sort_order) values
    ('ai-automation',  'AI Automation',        'Business workflows को AI agents से automate करें।', 'Custom', 1),
    ('ai-chatbots',    'AI Chatbots',          'Website व WhatsApp के लिए smart chatbots।',          '₹19,999/mo', 2),
    ('web-development', 'Web Development',      'Modern, fast websites और web apps।',                 '₹49,999+', 3),
    ('data-analytics', 'Data & Analytics',     'Data pipelines, dashboards और insights।',            'Custom', 4)
on conflict (slug) do nothing;

-- ------------------------------------------------------------
-- Demo task (test के लिए) - चाहें तो comment हटाएँ
-- ------------------------------------------------------------
-- insert into public.tasks (title, agent_type, payload, priority) values
--   ('AI tutoring app के लिए market research', 'research',
--    '{"region": "India", "budget": "low"}'::jsonb, 5);
