-- Drivers and delivery dates read by the app (Etapa 3).
-- A row has an NF-e, a CT-e, or both. A row with only a CT-e is a whole load
-- issued with a single XML, where the invoices are not visible.

create table public.entregas (
  id            uuid primary key default gen_random_uuid(),
  nfe           bigint,
  cte           bigint,
  motorista     text not null,
  data_entrega  date,
  atualizado_em timestamptz not null default now(),
  constraint entregas_nfe_ou_cte check (nfe is not null or cte is not null)
);

create unique index entregas_nfe_key on public.entregas (nfe) where nfe is not null;
create index entregas_cte_idx on public.entregas (cte);
create unique index entregas_cte_sem_nfe_key on public.entregas (cte) where nfe is null;

-- The app only reads, with the publishable key (anon role)
alter table public.entregas enable row level security;

create policy "app pode ler" on public.entregas
  for select to anon using (true);

revoke all on public.entregas from anon, authenticated;
grant select on public.entregas to anon;
