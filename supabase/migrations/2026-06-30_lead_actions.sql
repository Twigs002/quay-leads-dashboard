-- Lead Actions log
-- =================================================================
-- The Quay 1 Seller Lead Bank Google Sheet is READ-ONLY for this
-- dashboard. The Action Tracker tickbox + notes persist here instead.
--
-- Append-only: every tick is a new row. At read time, the dashboard
-- LEFT JOINs the most recent entry per email onto the leads dataframe.
--
-- Run once in the Supabase SQL Editor (project dqszbqiimbfvmmnpgpsb):
--   Dashboard → SQL Editor → paste this file → Run.

create table if not exists public.lead_actions (
  id           bigserial primary key,
  email        text        not null,
  actioned     boolean     not null default true,
  note         text        default '',
  actioned_by  text        not null,       -- staff.id (e.g. "pagan")
  actioned_at  timestamptz not null default now()
);

create index if not exists lead_actions_email_idx       on public.lead_actions (lower(email));
create index if not exists lead_actions_actioned_at_idx on public.lead_actions (actioned_at desc);

-- Row Level Security: only authenticated superusers can read/write
alter table public.lead_actions enable row level security;

drop policy if exists "lead_actions: super/admin can select" on public.lead_actions;
create policy "lead_actions: super/admin can select"
  on public.lead_actions for select to authenticated
  using (
    exists (
      select 1 from public.staff s
      where s.auth_user_id = auth.uid()
        and (s.is_super = true or s.is_admin = true)
        and coalesce(s.active, true) = true
    )
  );

drop policy if exists "lead_actions: super/admin can insert" on public.lead_actions;
create policy "lead_actions: super/admin can insert"
  on public.lead_actions for insert to authenticated
  with check (
    exists (
      select 1 from public.staff s
      where s.auth_user_id = auth.uid()
        and (s.is_super = true or s.is_admin = true)
        and coalesce(s.active, true) = true
    )
  );

comment on table public.lead_actions is
  'Action Tracker log for Quay 1 Seller Lead Bank dashboard. Append-only. The source sheet is read-only by policy.';
