# AGENTS.md

Guia do repositório para quem programa aqui, pessoa ou agente de IA. Leia antes de abrir o primeiro PR.

## O projeto

Desvio é um app de celular que monta viagens por terra: de carro, moto ou bicicleta (não tem modo avião). A pessoa informa a viagem, o app sugere lugares no caminho, ela desliza **Bora** ou **Passo**, e a IA ordena o roteiro final.

| O que | Onde |
| --- | --- |
| Requisitos, histórias (HU01 a HU19) e marcos | `docs/PRD.md` |
| Rotas do app e o arquivo de cada tela | `docs/rotas.md` |
| Design system (tokens, componentes, voz) | `docs/design/DESIGN-SYSTEM.md` |
| Layout de referência de cada tela | `docs/design/telas/*.dc.html` (índice em `docs/design/README.md`) |
| Verificação da stack e decisões de infraestrutura | `docs/verificacao-stack.md` |
| Planos de implementação já feitos | `docs/superpowers/plans/` |
| Glossário do domínio (termo pt-BR ↔ identificador no código) | `CONTEXT.md` |
| Decisões de arquitetura e o porquê | `docs/adr/` |

## Mapa do monorepo

```
apps/mobile/                Expo (React Native) + expo-router
  app/                      uma rota por arquivo, espelhando docs/rotas.md
  src/tema/                 tokens do design system; tokens.gerado.ts é gerado, não edite
  src/componentes/          componentes compartilhados
services/coletor/           Python + FastAPI
  app/__init__.py           carrega o .env (app/ambiente.py) antes dos outros módulos
  app/main.py               API HTTP
  app/fila.py               fila de jobs no Postgres do Supabase (FOR UPDATE SKIP LOCKED)
  app/banco.py              conexão com o Postgres (PV_DATABASE_URL)
  app/auth.py               valida o token do Supabase; o usuário sai do token
  app/worker.py             consome a fila e roda a coleta
  app/viagens.py            viagens, paradas e cards guardados no banco
  app/conta.py              LGPD: exportar os dados e apagar a conta (Admin API do Supabase)
  app/coletor.py            orquestra rota, paradas e cards
  app/geo.py                Nominatim (geocodificação) e OSRM (rota)
  app/osm.py                Overpass (cidades e lugares) e Wikipedia
  app/gmaps.py              gosom (Google Maps), única porta para o Google
  app/instagram.py          Instagram pelo site do lugar ou por busca (ddgs)
  app/preferencias.py       swipes, perfil de gosto e ordem estatística
  app/roteiro.py            ordem geométrica (km na rota)
  app/ia.py                 Groq: triagem, ranqueamento e roteiro, sempre com plano B
  tests/                    pytest, sem internet
packages/design-tokens/     tokens.json, a fonte única de cores, tipos, espaços e raios
docs/                       PRD, rotas, design, verificação, planos
```

## Comandos

Configuração inicial: `cp .env.example .env` e preencha `PV_USER_AGENT` e `GROQ_API_KEY`. A API, o worker e o CLI leem esse `.env` sozinhos (`app/ambiente.py`); o docker compose também. O passo a passo completo está em `CONTRIBUTING.md`.

**Coletor** (em `services/coletor`):

```bash
pip install -r requirements-dev.txt
python -m pytest -q                       # testes, sem internet
uvicorn app.main:app --reload             # API em http://localhost:8000/docs
python -m app.worker                      # worker; precisa rodar junto com a API
python cli.py "Alegrete, RS" "Vitória da Conquista, BA" --veiculo moto   # coleta direto, sem API
```

**Tudo junto com o Google Maps** (na raiz): `docker compose up --build` sobe a API, o worker e o gosom.

**App** (em `apps/mobile`):

```bash
npm install
npx expo start
npm run typecheck
npm run tokens        # depois de mudar packages/design-tokens/tokens.json
```

## Regras de código

- **Português do Brasil** em nomes, mensagens, comentários e documentos, como no código que já existe.
- **Sem dependência Python nova** sem justificar no PR. O Groq é chamado por `httpx`, sem SDK.
- **Testes sem internet.** Simule as APIs externas com `httpx.MockTransport` ou `monkeypatch` (veja `tests/test_offline.py`).
- **Toda chamada de IA passa por `app/ia.py`** e tem plano B: se o Groq falhar, demorar mais de 10 s ou bater no limite, a resposta usa a ordem sem IA, sem erro para o app.
- **A chave do Groq só existe no servidor.** O app nunca fala direto com o Groq.
- **O Google só entra por `app/gmaps.py`.** Raspar viola os termos do Google; no lançamento público esse módulo vira a Places API, e o resto do código não muda.
- **A coleta roda no worker, nunca na requisição.** A API cria o job (`fila.criar`) e responde 202; o app consulta `GET /jobs/{id}`.
- **No app, cores, espaços, raios e fontes vêm de `@/tema`**, nunca hex ou número solto. Mudou um token? Edite `packages/design-tokens/tokens.json` e rode `npm run tokens`.
- **Telas seguem o canvas** (`docs/design/telas/`) e as regras de voz do design system: "você", botões curtos (Bora, Passo, Favorito), sem emoji, números no formato brasileiro.

## Fluxo de trabalho

- Branch a partir de `main` com o nome `feat/…`, `fix/…` ou `docs/…`. Nunca faça commit direto na `main`.
- PR pequeno, com a história do PRD que ele atende (ex.: HU09). O CI precisa estar verde, e um colega revisa.
- Mensagens de commit em português, curtas, dizendo o que mudou (veja `git log`).
- **Nunca adicione trailer `Co-Authored-By` de IA** (Claude, Codex ou qualquer outra) nos commits.

## Armadilhas conhecidas

- **gosom:** cada job leva no mínimo uns 3 minutos. Mande todas as buscas da viagem num job só (`gmaps.buscar_lote`). Ele precisa de 1 a 2 GB de RAM.
- **Groq gratuito:** 30 requisições e 8.000 tokens por minuto, 1.000 requisições e 200 mil tokens por dia, por modelo e por conta. Várias chaves não somam. O Llama não está mais no plano gratuito; use `openai/gpt-oss-120b` e `openai/gpt-oss-20b`.
- **Nominatim:** 1 requisição por segundo e um e-mail real em `PV_USER_AGENT`, ou o IP é bloqueado.
- **ddgs:** bloqueia por alguns minutos quando recebe muitas buscas seguidas. O Instagram achado por busca é "provável" (`instagram_origem = "busca"`).
- **Push:** o Expo Go não recebe push no Android. Para testar o aviso de busca pronta, use um development build.
- **`.env` nunca vai para o Git.** Só o `.env.example`.

## Antes de dizer que terminou

1. `python -m pytest -q` em `services/coletor`
2. `npm run typecheck` em `apps/mobile`
3. Se mexeu em tela: abra no aparelho ou no emulador, nos temas claro e escuro
