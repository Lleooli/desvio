# Verificação da stack e da arquitetura

Feita em 2026-10-15, sobre o PRD e o código da Fase 0. Decisões novas: IA no **Groq (plano gratuito)**; raspagem com **gosom/google-maps-scraper** e **ddgs**.

## Resumo

| Peça | Situação | Como foi verificado |
| --- | --- | --- |
| gosom (Google Maps) | Funciona com o código atual | Job real rodado no Docker contra a API REST |
| ddgs (busca web) | Funciona; acerto do Instagram precisa melhorar | Busca real com a mesma chamada do `instagram.py` |
| Groq gratuito | Serve para desenvolvimento e testes, não para usuários reais | Docs oficiais de modelos, limites e structured outputs |
| Coletor (FastAPI) | 8 testes passando | `pytest` local |
| App Expo | Versões coerentes (SDK 57.0.30 é a última) | `npm view`; não instalei nem rodei o app |
| Arquitetura | Faltam a fila de jobs e a separação entre API e worker | Leitura do PRD e do código |

## Corrigido em 2026-10-15

Feito pelo plano `docs/superpowers/plans/2026-10-15-organizacao-e-correcoes.md`:

- **Fila e worker:** `app/fila.py` e `app/worker.py`. As viagens viram jobs (202 + `GET /jobs/{id}`), e o serviço `worker` está no `docker-compose.yml`.
- **IA no Groq:** `app/ia.py` com schema estrito, `reasoning_effort: "low"`, limitador por modelo, cards enxutos e plano B. Os endpoints são `/triagem`, `/cards/ranquear` e `/roteiro/carro` com `usar_ia`.
- **Instagram:** `escolher_handle` exige todas as palavras do nome e dá preferência à cidade. Testado ao vivo com "Cantina do Nono", em Curitiba.
- **Dados do gosom:** os cards do Google trazem `sobre` (as opções ativas do `about`).
- **Configuração:** `.env.example` com `PV_USER_AGENT`, `GROQ_API_KEY` e `PV_CORS_ORIGINS`; CORS configurável.
- **Time:** `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, template de PR e CI do app (typecheck e tokens).

Continua aberto:

- Fila e banco no Postgres do Supabase (hoje é SQLite, com a mesma interface)
- Cache de 30 dias por cidade
- Push pelo Expo, com development build
- VPS para o gosom: decisão e compose de produção em [docs/adr/0002-vps-da-api.md](adr/0002-vps-da-api.md) e [docs/deploy.md](deploy.md) (#10); falta contratar a máquina e apontar o DNS
- VPS para OSRM, Nominatim e Overpass próprios: configuração, scripts e dimensionamento estimado prontos em [infra/osm/README.md](../infra/osm/README.md) (#37); falta subir e medir
- Cache das respostas da IA por (cidade, categoria, perfil)

## gosom/google-maps-scraper

Rodei a imagem `gosom/google-maps-scraper` com `-data-folder` e mandei um job com a mesma forma que `services/coletor/app/gmaps.py` usa: `"restaurantes em Lages, SC #!#p1-restaurante"`, `lang: pt`, `depth: 1`, `zoom: 14`, `max_time: 240`.

- **Contrato:** `POST /api/v1/jobs`, `GET /api/v1/jobs/{id}` e `GET /api/v1/jobs/{id}/download` batem com a OpenAPI do container (`/static/spec/spec.yaml`). O status vem na chave `Status` com valor `ok`, e o código já trata os dois formatos. `max_time` vai em segundos.
- **IDs por busca:** a sintaxe `#!#id` funciona. Todas as linhas voltaram com `input_id = p1-restaurante`.
- **Colunas:** todas as que `linha_para_lugar` lê existem no CSV (`title`, `review_rating`, `review_count`, `thumbnail`, `images`, `open_hours`, `price_range`, `descriptions`, `link`, `place_id` etc.).
- **Tempo e volume:** 16 lugares em cerca de 4 minutos para uma busca. O job tem duração mínima de uns 3 minutos, então o "até 4 min sem cache" do PRD fica no limite. O cache por cidade é obrigatório, não otimização.
- **Dados ralos:** `price_range` e `descriptions` vieram vazios na maioria dos lugares. A IA vai ter pouco texto para ranquear. Vale incluir `about` e `category` no card e no prompt.
- **Hospedagem:** o gosom roda um Chromium (Playwright) e precisa de 1 a 2 GB de RAM. Não cabe nos planos gratuitos de hospedagem: planeje uma VPS pequena.
- **Termos do Google:** sem mudança. Só em teste; Places API antes do lançamento público, como já diz o PRD.

## ddgs

`ddgs 9.16.0` (MIT, Python 3.10+). `DDGS().text(query, region="br-pt", max_results=6)` funciona sem chave.

**Problema confirmado: homônimos.** A busca "Cantina do Nono Curitiba instagram" devolveu seis perfis: `@cantina_nono`, `@cantinadonono`, `@cantinadononofilho`, `@cantinadononocanela` e outros dois. `parece_o_mesmo` só confere se uma palavra do nome aparece no resultado. Quatro deles passam, e o código fica com o primeiro, que pode ser de outra cidade.

Ajuste sugerido em `instagram.py`:

1. Exigir que a cidade (ou a UF) apareça no título ou no snippet (`body`), ou dar mais peso quando aparece.
2. Pontuar a semelhança entre o handle e o nome normalizado e escolher o melhor resultado, não o primeiro.
3. Continuar marcando como "provável" (`instagram_origem = "busca"`).

O ddgs é síncrono e o código espera 1,5 s entre buscas. Com 30 restaurantes, são mais de 45 s por viagem. Isso só é aceitável no worker, nunca na requisição do app.

## Groq (plano gratuito)

**Modelos.** Llama 3.1 8B e Llama 3.3 70B saíram dos planos gratuito e Developer em 16/08/2026 (seguem só no Enterprise). Os modelos Qwen e MiniMax estão em *preview*, que o Groq diz ser só para avaliação. Sobram:

| Uso | Modelo | Por quê |
| --- | --- | --- |
| Triagem e roteiro | `openai/gpt-oss-120b` | Melhor raciocínio; poucas chamadas por viagem |
| Ranqueamento dos 30 cards | `openai/gpt-oss-20b` | Duas vezes mais rápido; os limites são por modelo, então dividir dobra a cota |

**JSON validado.** Structured outputs com `strict: true` funcionam nos dois gpt-oss. Atende o "devolve JSON validado" do PRD. Regras do modo estrito: todo campo em `required`, `additionalProperties: false`, opcionais como união com `null`. Não há streaming nem tool use junto com structured outputs.

**Limites do plano gratuito.** São por organização, não por chave:

| Modelo | Req/min | Req/dia | Tokens/min | Tokens/dia |
| --- | --- | --- | --- | --- |
| gpt-oss-120b | 30 | 1.000 | 8.000 | 200.000 |
| gpt-oss-20b | 30 | 1.000 | 8.000 | 200.000 |

O limite que trava é o de tokens. Uma viagem de carro com 5 paradas gasta perto de 30 mil tokens: 5 ranqueamentos de uns 4 mil, roteiro de uns 4 mil e triagem de uns 5 mil. Isso dá **de 7 a 14 viagens por dia** com os dois modelos, e só uns **2 ranqueamentos por minuto** por causa dos 8 mil tokens/min. O próprio Groq descreve o plano gratuito como "para construir e testar, não para tráfego". Para o beta, conte com o plano Developer (pago por uso).

**Como caber no gratuito:**

- Usar `reasoning_effort: "low"` nos gpt-oss. São modelos de raciocínio, e os tokens de raciocínio contam no limite.
- Mandar cards enxutos para a IA: id, categoria, nome, nota, avaliações e até 120 caracteres de descrição.
- Guardar o ranqueamento em cache por (cidade, categoria, hash do resumo do perfil). Tokens em cache também não contam no limite do Groq.
- Ter um limitador central na API (fila com ritmo por modelo). Como o limite é da organização, várias chaves não ajudam.
- Tratar o 429 lendo o `retry-after` e cair na ordem estatística ou geométrica, como o PRD já prevê para o caso de mais de 10 s.
- A chave do Groq fica só no servidor (`GROQ_API_KEY`), nunca no app.

## Arquitetura: lacunas

1. **Fila de jobs não definida.** O PRD diz "fila de jobs", mas não diz qual. Sugestão: uma tabela `jobs` no próprio Supabase, consumida com `SELECT … FOR UPDATE SKIP LOCKED` (ou a extensão `pgmq`). Assim não precisa de Redis.
2. **API e worker ainda são um processo só.** `POST /viagem/carro` coleta dentro da requisição, e isso leva minutos. É preciso separar: a API cria o job e devolve o `id` da viagem; o worker coleta, salva os cards e manda o push.
3. **Banco.** O coletor usa SQLite (`PV_DB`) e cache em memória (`geo._cache`). O PRD prevê Supabase com cache de 30 dias. Migrar `preferencias.py` e o cache para Postgres.
4. **Push.** O Expo Go não recebe push no Android desde o SDK 53. Para testar o aviso de busca pronta, é preciso um development build (EAS).
5. **Supabase gratuito** pausa o projeto depois de uma semana sem uso. Em teste isso é aceitável; no beta, use o plano pago ou um ping periódico.
6. **Nominatim:** o `PV_USER_AGENT` do `docker-compose.yml` ainda tem o e-mail de exemplo. A política de uso exige um contato real.
7. **CORS:** `allow_origins=["*"]` só serve para desenvolvimento.

## O que fica como está

O app em Expo com expo-router, Reanimated e Gesture Handler; a API e o worker em Python com FastAPI; Supabase para Postgres e login com Google, Apple e link por e-mail (o Apple é obrigatório na App Store quando há login com Google); OpenStreetMap como base; e o monorepo.

## Próximos passos sugeridos

1. Criar a chave do Groq e escrever `services/coletor/app/ia.py` com o cliente, os schemas estritos, o limitador e o fallback.
2. Separar API e worker, com a fila no Postgres.
3. Melhorar o casamento do Instagram (cidade e semelhança do handle).
4. Pôr `about` e `category` do gosom nos cards.
