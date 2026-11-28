-- Fix an ambiguous conflict target in create_organization.
-- The output column organization_id shares a name with the membership key.
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
    on conflict on constraint organization_memberships_pkey do nothing;

    return query
    select v_organization.id, v_organization.name, 'owner'::text;
end;
$function$;

revoke all on function public.create_organization(text, uuid) from public, anon, authenticated;
grant execute on function public.create_organization(text, uuid) to authenticated;
