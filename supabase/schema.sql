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

-- pipeline lineage (agent-to-agent chaining) — existing tables ke liye safe add
alter table public.tasks add column if not exists parent_task_id uuid;
alter table public.tasks add column if not exists pipeline_id uuid;

create index if not exists tasks_status_idx   on public.tasks (status);
create index if not exists tasks_priority_idx on public.tasks (priority desc, created_at);
create index if not exists tasks_pipeline_idx on public.tasks (pipeline_id);

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
-- Seed: agent swarm (pipeline order)
-- ------------------------------------------------------------
insert into public.agents (agent_type, name, role) values
    ('research',    'Research Agent',    'Market Research Analyst'),
    ('opportunity', 'Opportunity Agent', 'Business Opportunity & Monetization Analyst'),
    ('strategy',    'Strategy Agent',    'Business Strategy Lead'),
    ('product',     'Product Agent',     'Product Designer / Solution Architect'),
    ('dev',         'Dev Agent',         'Software Engineer'),
    ('marketing',   'Marketing Agent',   'Marketing & Content Strategist'),
    ('sales',       'Sales Agent',       'Sales & Outreach Specialist'),
    ('delivery',    'Delivery Agent',    'Delivery & Client Success Manager'),
    ('finance',     'Finance Agent',     'Finance & Pricing Analyst'),
    ('support',     'Support Agent',     'Customer Support Specialist')
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
-- opportunities: paisa-banane wale business opportunities (Opportunity Agent)
-- ------------------------------------------------------------
create table if not exists public.opportunities (
    id          uuid primary key default gen_random_uuid(),
    title       text not null,
    analysis    text,                          -- full agent output (markdown sections)
    market      text,
    region      text,
    status      text not null default 'discovered',  -- discovered|qualified|pursuing|won|lost
    priority    int,
    task_id     uuid references public.tasks(id) on delete set null,
    created_at  timestamptz not null default now()
);

create index if not exists opportunities_status_idx on public.opportunities (status);
create index if not exists opportunities_created_idx on public.opportunities (created_at desc);

-- ------------------------------------------------------------
-- company_memory: shared brain — agents yahan se context padhte/likhte hain
-- ------------------------------------------------------------
create table if not exists public.company_memory (
    id          uuid primary key default gen_random_uuid(),
    kind        text not null default 'note',  -- research|opportunity|strategy|product|dev|marketing|sales|delivery|finance|support|note
    title       text,
    content     text,
    tags        text[] not null default '{}',  -- pipeline_id yahan store hota hai
    agent       text,
    task_id     uuid references public.tasks(id) on delete set null,
    created_at  timestamptz not null default now()
);

create index if not exists memory_kind_idx    on public.company_memory (kind);
create index if not exists memory_tags_idx     on public.company_memory using gin (tags);
create index if not exists memory_created_idx  on public.company_memory (created_at desc);

-- ------------------------------------------------------------
-- Seed: Aitotech की sample services (अपने हिसाब से edit करें)
-- ------------------------------------------------------------
insert into public.services (slug, name, description, price, sort_order) values
    ('data-automation',      'Data Automation',      'AI-driven data pipelines, real-time sync, schema intelligence.', 'Custom quote', 1),
    ('workflow-automation',  'Workflow Automation',  'Multi-app orchestration, approvals, SLA monitoring.',           'Custom quote', 2),
    ('invoice-intelligence', 'Invoice Intelligence', 'OCR + NLP invoice extraction, PO matching, ERP integration.', 'Custom quote', 3),
    ('custom-ai',            'Custom AI Systems',    'Fine-tuned LLMs, private RAG, autonomous agents in your VPC.',  'Custom quote', 4)
on conflict (slug) do nothing;

-- ------------------------------------------------------------
-- Demo task (test के लिए) - चाहें तो comment हटाएँ
-- ------------------------------------------------------------
-- insert into public.tasks (title, agent_type, payload, priority) values
--   ('AI tutoring app के लिए market research', 'research',
--    '{"region": "India", "budget": "low"}'::jsonb, 5);
