-- Issue #93: cards de cada cidade já coletada, por categoria, compartilhados entre todas as pessoas.
-- Uma viagem que passa por uma cidade já feita (há menos de 30 dias) reaproveita os cards e a
-- ordem genérica da IA de cada categoria que já tem linha, sem Overpass, Google, Instagram nem
-- Groq; só as categorias que faltam são coletadas. Uma linha por categoria: a viagem com
-- turismo e restaurante usa a cidade feita com turismo, restaurante e posto.
-- Só o servidor lê e escreve: RLS ligada, sem política, e nada para anon/authenticated.

create table public.parada_cidade (
  cidade text not null,            -- "ibge:4300406" ou, fora da lista do IBGE, "nome:alegrete|RS"
  categoria text not null,         -- turismo, restaurante, posto, natureza ou hospedagem
  variante text not null,          -- raio, cards por categoria e fonte (osm ou google)
  nome text not null,
  uf text,
  lat double precision not null,
  lon double precision not null,
  cards jsonb not null,            -- já na ordem genérica da IA, quando ela respondeu
  ordem_ia jsonb,                  -- ids na ordem da IA, sem o gosto de ninguém; null = plano B
  completa boolean not null default true,  -- false: a busca do Google voltou vazia (vale 1 dia)
  atualizado_em timestamptz not null default now(),
  primary key (cidade, categoria, variante)
);

create index parada_cidade_busca on public.parada_cidade (categoria, variante, lat, lon);

alter table public.parada_cidade enable row level security;
revoke all on public.parada_cidade from anon, authenticated;
