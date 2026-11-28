-- Run as database administrator; synthetic data rolled back.
begin;
insert into aeos_spike.tenant_probe values
('10000000-0000-4000-8000-000000000001','20000000-0000-4000-8000-000000000001','30000000-0000-4000-8000-000000000001'),
('10000000-0000-4000-8000-000000000002','20000000-0000-4000-8000-000000000002','30000000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claim.sub','30000000-0000-4000-8000-000000000001',true);
do $$
begin
  if (select count(*) from aeos_spike.tenant_probe) <> 1 then
    raise exception 'A visibility failed';
  end if;
  if exists (select 1 from aeos_spike.tenant_probe where organization_id='20000000-0000-4000-8000-000000000002') then
    raise exception 'A cross-tenant read failed';
  end if;
  if has_table_privilege(current_user,'aeos_spike.tenant_probe','INSERT') or
     has_table_privilege(current_user,'aeos_spike.tenant_probe','UPDATE') or
     has_table_privilege(current_user,'aeos_spike.tenant_probe','DELETE') then
    raise exception 'unexpected write grant';
  end if;
end $$;
select set_config('request.jwt.claim.sub','30000000-0000-4000-8000-000000000002',true);
do $$
begin
  if (select count(*) from aeos_spike.tenant_probe) <> 1 then
    raise exception 'B visibility failed';
  end if;
  if exists (select 1 from aeos_spike.tenant_probe where organization_id='20000000-0000-4000-8000-000000000001') then
    raise exception 'B cross-tenant read failed';
  end if;
end $$;
select set_config('request.jwt.claim.sub','30000000-0000-4000-8000-000000000003',true);
do $$
begin
  if (select count(*) from aeos_spike.tenant_probe) <> 0 then
    raise exception 'unknown user visibility failed';
  end if;
end $$;
reset role;
do $$
begin
  if has_schema_privilege('anon','aeos_spike','USAGE') or
     has_table_privilege('anon','aeos_spike.tenant_probe','SELECT') then
    raise exception 'anonymous access granted';
  end if;
end $$;
rollback;
select 'PASS' as rls_probe, 7 as checks_passed;
