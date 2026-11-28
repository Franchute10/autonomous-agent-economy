-- S0-03 probe ONLY. No business tables or real customer data.
-- Private schema; no Data API exposure. No SECURITY DEFINER functions.
create schema aeos_spike;
revoke all on schema aeos_spike from public, anon, authenticated;
grant usage on schema aeos_spike to authenticated;
create table aeos_spike.tenant_probe (
  id uuid primary key,
  organization_id uuid not null,
  owner_id uuid not null
);
alter table aeos_spike.tenant_probe enable row level security;
alter table aeos_spike.tenant_probe force row level security;
revoke all on table aeos_spike.tenant_probe from public, anon, authenticated;
grant select on table aeos_spike.tenant_probe to authenticated;
create policy probe_read_own on aeos_spike.tenant_probe
  for select to authenticated
  using (owner_id = (select auth.uid()));
-- No write grants and no write policies for application roles.
