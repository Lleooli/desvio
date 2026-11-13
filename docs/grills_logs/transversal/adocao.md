# Adoção: glossário, restrições e calibragem

13/11/2026 · Emilly

Sessão para registrar o que o código não diz: o vocabulário do domínio, o que não pode mudar no projeto e como o trabalho é dividido.

## Perguntas e respostas

**1. Idioma dos identificadores.** O `AGENTS.md` pede nomes em pt-BR, mas a convenção comum é código em inglês.
Resposta: vale pt-BR. Exceção: os componentes do design system (`Button`, `Chip`, `TextField`, `BottomNav`…) ficam em inglês. Registrado em `docs/adr/0001-identificadores-em-portugues.md`.

**2. Parada, destino e cidade.** No código, "parada" é tanto a lista geral quanto um dos tipos (`parada`, `destino`, `estadia`).
Resposta: **Parada** é o termo geral; **Parada no caminho** (`tipo = "parada"`), **Destino** (`tipo = "destino"`) e, no modo avião, **Escala** (`tipo = "estadia"`). "Cidade" não é termo de domínio.

**3. Lugar × Card e Decisão × Swipe.**
Resposta: **Lugar** é o estabelecimento real, reaproveitado entre viagens; **Card** é a apresentação dele numa parada. **Decisão** é Bora, Passo ou Favorito; "swipe" é só o gesto. **Favorito** é um Bora mais forte: entra no roteiro e pesa mais no perfil de gosto.

**4. Triagem, perfil de gosto, busca, ranqueamento e roteiro.**
Resposta: confirmados como estão no `CONTEXT.md`. Para a pessoa usuária, o processo é **busca** (no código, `coleta`/`job`).

**5. Restrições.**
Resposta:
- Custo zero no MVP: aceito.
- Python 3.12 e Node 22, Expo seguindo a versão do SDK: aceito.
- Persistência: código novo escrito direto para o Postgres do Supabase; o SQLite fica só no que já existe, até ser migrado.
- App sem módulo nativo fora do Expo (rodar no Expo Go): **não decidido**.
- Contrato API ↔ app: aceito.

**6. Calibragem de trabalho.** Aceita a proposta (abaixo).

**7. ADRs retroativos.** Só o dos identificadores em pt-BR. A fila assíncrona e o Postgres do Supabase ficam para quando forem questionados ou executados.

**8. Organização dos logs.** Aceito o `docs/grills_logs/README.md`.

## Divergências encontradas, sem decisão nesta sessão

- O PRD modela a decisão com `tipo` (bora, passo, favorito); o coletor guarda só `gostou: bool` na tabela `swipes`. O Favorito ainda não chega ao servidor.
- O campo `card_id` da tabela `swipes` guarda, na verdade, o id do **lugar**.
- O `AGENTS.md` diz "SQLite hoje, Postgres do Supabase depois", e a decisão agora é escrever o código novo direto para o Postgres.
- Existem `docs/design-system.md` e `docs/design/DESIGN-SYSTEM.md`; o `AGENTS.md` aponta só para o segundo.

## Como ficou decidido

### Restrições

As regras de código e de arquitetura do `AGENTS.md` (IA só por `app/ia.py` com plano B, chave do Groq só no servidor, Google só por `app/gmaps.py`, coleta só no worker, tokens só de `@/tema`, testes sem internet, nada de dependência Python sem justificativa) valem integralmente. Além delas:

- **Custo zero no MVP.** Só serviços gratuitos: Groq no plano gratuito, Nominatim, OSRM e Overpass públicos, gosom local. Qualquer serviço pago é discutido antes.
- **Versões.** Python 3.12 e Node 22, como no CI. O Expo segue a versão do SDK (57) e não é atualizado por conta própria.
- **Persistência.** Código novo de persistência é escrito para o Postgres do Supabase. O SQLite (`fila.py`, `preferencias.py`) fica só no que já existe, até ser migrado.
- **Contrato API ↔ app.** As rotas do coletor são consumidas pelo app; mudar o formato de uma resposta exige ajustar os dois lados no mesmo PR.
- **Pendente:** se o app deve rodar sempre no Expo Go, sem módulo nativo fora do Expo.

Suíte: `cd services/coletor && python -m pytest -q && cd ../../apps/mobile && npm run typecheck`.
Setup: `pip install -r services/coletor/requirements-dev.txt && npm ci --prefix apps/mobile`.

### Quebra de trabalho

A unidade é o **app** (`apps/mobile`) ou o **coletor** (`services/coletor`). Uma issue que mexe nos dois vira plano de sub-tarefas: primeiro o coletor, depois o app. Dentro de uma unidade, quebra quando passa de três módulos (arquivos de `app/` no coletor; rotas ou componentes no app).

### Camadas

- Coletor: `app/main.py` (HTTP) → `app/worker.py` e `app/fila.py` (fila) → `app/coletor.py` (orquestração) → `geo.py`, `osm.py`, `gmaps.py`, `instagram.py`, `ia.py` (integrações externas) → `preferencias.py` e `roteiro.py` (regras).
- App: `packages/design-tokens` e `src/tema` (tokens) → `src/componentes` → `app/` (telas e rotas).
- Quando a mudança atravessa camadas, um commit por camada.
