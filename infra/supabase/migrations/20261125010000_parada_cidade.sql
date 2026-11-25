-- Issue #93: cards de cada cidade já coletada, compartilhados entre todas as pessoas.
-- Uma viagem que passa por uma cidade já feita (há menos de 30 dias) reaproveita os cards
-- e a ordem genérica da IA, sem Overpass, Google, Instagram nem Groq.
-- Só o servidor lê e escreve: RLS ligada, sem política, e nada para anon/authenticated.

create table public.parada_cidade (
  cidade text not null,            -- "ibge:4300406" ou, fora da lista do IBGE, "nome:alegrete|RS"
  categorias text not null,        -- categorias ordenadas, separadas por vírgula
  variante text not null,          -- raio, cards por categoria e fonte (osm ou google)
  nome text not null,
  uf text,
  lat double precision not null,
  lon double precision not null,
  cards jsonb not null,            -- já na ordem genérica da IA, quando ela respondeu
  ordem_ia jsonb,                  -- ids na ordem da IA, sem o gosto de ninguém; null = plano B
  completa boolean not null default true,  -- false: alguma busca do Google voltou vazia (vale 1 dia)
  atualizado_em timestamptz not null default now(),
  primary key (cidade, categorias, variante)
);

create index parada_cidade_busca on public.parada_cidade (categorias, variante, lat, lon);

alter table public.parada_cidade enable row level security;
revoke all on public.parada_cidade from anon, authenticated;
