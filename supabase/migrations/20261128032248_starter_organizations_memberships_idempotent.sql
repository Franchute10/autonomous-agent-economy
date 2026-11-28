-- AEOS Starter organization onboarding with user-scoped PostgreSQL access.
-- This migration creates no tenant or user rows.
create table if not exists public.organizations (
    id uuid primary key default gen_random_uuid(),
    name text not null check (char_length(name) between 2 and 120),
    created_by uuid not null references auth.users(id) on delete restrict,
    creation_key uuid not null,
    created_at timestamptz not null default now(),
    unique (created_by, creation_key)
);

create table if not exists public.organization_memberships (
    organization_id uuid not null references public.organizations(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    role text not null check (role in ('owner', 'admin', 'member', 'viewer')),
    created_at timestamptz not null default now(),
    primary key (organization_id, user_id)
);

create index if not exists organization_memberships_user_idx
    on public.organization_memberships (user_id, created_at);

alter table public.organizations enable row level security;
alter table public.organization_memberships enable row level security;

revoke all on table public.organizations from public, anon, authenticated;
revoke all on table public.organization_memberships from public, anon, authenticated;
grant select on table public.organizations to authenticated;
grant select on table public.organization_memberships to authenticated;

drop policy if exists organizations_member_read on public.organizations;
create policy organizations_member_read
    on public.organizations
    for select
    to authenticated
    using (
        exists (
            select 1
            from public.organization_memberships m
            where m.organization_id = organizations.id
              and m.user_id = (select auth.uid())
        )
    );

drop policy if exists memberships_self_read on public.organization_memberships;
create policy memberships_self_read
    on public.organization_memberships
    for select
    to authenticated
    using (user_id = (select auth.uid()));

create or replace function public.create_organization(p_name text, p_creation_key uuid)
returns table (organization_id uuid, name text, role text)
language plpgsql
security definer
set search_path = pg_catalog, public
as $function$
declare
    v_user_id uuid;
    v_organization public.organizations%rowtype;
    v_name text;
begin
    v_user_id := auth.uid();
    if v_user_id is null then
        raise exception 'authentication required' using errcode = '42501';
    end if;

    v_name := btrim(p_name);
    if v_name is null or char_length(v_name) < 2 or char_length(v_name) > 120 then
        raise exception 'invalid organization name' using errcode = '22023';
    end if;

    if p_creation_key is null then
        raise exception 'idempotency key required' using errcode = '22023';
    end if;

    insert into public.organizations (name, created_by, creation_key)
    values (v_name, v_user_id, p_creation_key)
    on conflict (created_by, creation_key) do nothing
    returning * into v_organization;

    if not found then
        select *
        into v_organization
        from public.organizations
        where created_by = v_user_id
          and creation_key = p_creation_key;
    end if;

    insert into public.organization_memberships (organization_id, user_id, role)
    values (v_organization.id, v_user_id, 'owner')
    on conflict (organization_id, user_id) do nothing;

    return query
    select v_organization.id, v_organization.name, 'owner'::text;
end;
$function$;

revoke all on function public.create_organization(text, uuid) from public, anon, authenticated;
grant execute on function public.create_organization(text, uuid) to authenticated;
