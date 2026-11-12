# Desvio

App de celular que monta viagens com paradas escolhidas por swipe. Você informa a viagem (de carro, moto ou bicicleta), o app sugere lugares no caminho, você desliza **Bora** ou **Passo**, e a IA ordena o roteiro final.

> Nome provisório. Detalhes no [PRD](docs/PRD.md).

## Estrutura

```
apps/mobile/            App Expo (React Native + expo-router), uma rota por tela do canvas
services/coletor/       API FastAPI + worker: rota, paradas e lugares (OSM, Google Maps via gosom, Wikipedia) e IA (Groq)
packages/design-tokens/ Tokens do design system Desvio (fonte única de cores, tipos, espaços e raios)
docs/                   PRD, rotas, design system e telas (docs/design), verificação da stack e planos
```

## Rodando

Antes de tudo, `cp .env.example .env` e preencha. O passo a passo completo está em [CONTRIBUTING.md](CONTRIBUTING.md), e as regras do código em [AGENTS.md](AGENTS.md).

**Coletor** (Python 3.11+):

```bash
cd services/coletor
pip install -r requirements-dev.txt
python -m pytest -q                                             # testes
python cli.py "Alegrete, RS" "Vitória da Conquista, BA"   # teste rápido, sem API
uvicorn app.main:app --reload                                   # API em http://localhost:8000/docs
python -m app.worker                                            # worker de coleta (outro terminal)
```

API, worker e o raspador do Google Maps juntos: `docker compose up --build` na raiz.

**App** (Node 22+):

```bash
cd apps/mobile
npm install
npx expo start
```

As telas ainda são provisórias: cada uma mostra a rota e as histórias de usuário que atende, com links para navegar o fluxo. O layout de cada uma está no [canvas de rotas](https://claude.ai/artifact/Y8YekNeBFE8R8nxLUVuPXQ).

## Design

- Design system: [Desvio](https://claude.ai/artifact/4axmnGJWvKEXczHh3RP4uq) (tokens, componentes, regras de uso)
- Telas e navegação: [canvas de rotas](https://claude.ai/artifact/Y8YekNeBFE8R8nxLUVuPXQ), nos temas claro e escuro
- Mudou um token? Atualize `packages/design-tokens/tokens.json` e rode `npm run tokens` em `apps/mobile`.

## Sites da disciplina

Cada pessoa do grupo tem um site com o contexto, o problema, a solução e a evolução do projeto (A13):

- Leonardo: [liaa-leonardo.github.io](https://liaa-leonardo.github.io)

## Avisos

Raspar o Google Maps viola os termos de uso do Google. Use só em teste; para lançamento público, troque `services/coletor/app/gmaps.py` pela Places API oficial. Veja a seção de riscos do PRD.
