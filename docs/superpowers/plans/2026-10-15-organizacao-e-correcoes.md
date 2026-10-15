# Organização do repositório e correções da verificação — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir o que a verificação da stack apontou (fila e worker, IA no Groq, Instagram por busca, dados do gosom) e deixar o repositório pronto para mais desenvolvedores, com AGENTS.md, CLAUDE.md, guia de contribuição e CI.

**Architecture:** O coletor ganha uma fila de jobs em SQLite (`app/fila.py`) e um worker (`app/worker.py`). A API cria o job e responde 202; o worker coleta e grava o resultado. A IA fica num módulo próprio (`app/ia.py`) que fala com o Groq por HTTP usando `httpx`, com schema JSON estrito, um limitador por modelo e um plano B sem IA sempre que algo falha. A troca da fila para o Postgres do Supabase fica para outro plano: a interface de `fila.py` já é a que o Postgres vai implementar.

**Tech Stack:** Python 3.11+, FastAPI, httpx, SQLite (stdlib), pytest; Groq (`openai/gpt-oss-120b`, `openai/gpt-oss-20b`); Expo SDK 57 e TypeScript no app; GitHub Actions.

**Spec:** `docs/verificacao-stack.md` (achados) e `docs/PRD.md` (seções "IA: triagem, ranqueamento e roteiro" e "Arquitetura e stack").

## Global Constraints

- Python 3.11 ou mais novo; o CI roda em 3.12.
- Nenhuma dependência Python nova em `requirements.txt`. O Groq é chamado por `httpx`, sem o SDK `groq`. `pytest` vai para `requirements-dev.txt`.
- Os testes não usam a internet: toda chamada externa é simulada com `httpx.MockTransport` ou `monkeypatch`.
- Nomes de código, mensagens e documentos em português do Brasil, como o código atual.
- Nenhum commit com trailer `Co-Authored-By` de IA.
- A chave do Groq só existe no servidor (`GROQ_API_KEY`); nunca vai para o app nem para o repositório.
- Modelos: `openai/gpt-oss-120b` para triagem e roteiro e `openai/gpt-oss-20b` para ranqueamento, ambos trocáveis por variável de ambiente.
- Limite do Groq gratuito por modelo: 30 requisições/min e 8.000 tokens/min.
- Se a IA falhar ou passar de 10 s, a resposta usa a ordem sem IA, sem erro para o app.
- A IA ranqueia no máximo os 30 primeiros cards de cada parada.
- A triagem tem no máximo 5 perguntas, e a primeira é fixa.

## Review Focus

- Sem `GROQ_API_KEY` no ambiente: triagem, ranqueamento e roteiro continuam funcionando pelo plano B. Teste na Task 4 (`test_ia_sem_chave`) e na Task 5 (`test_ranquear_fallback`).
- A IA devolve ids que não existem, repetidos ou faltando: ids desconhecidos e repetidos são ignorados, e os que faltam entram no fim, na ordem original. Teste na Task 5 (`test_ranquear_ids_estranhos`).
- O worker quebra no meio de um job: o job vira `falhou` com a mensagem, e o worker segue para o próximo. Teste na Task 3 (`test_worker_marca_falha`).
- Dois workers pegam jobs ao mesmo tempo: cada job sai da fila uma vez só. Teste na Task 3 (`test_fila_nao_entrega_duas_vezes`).
- O app consulta um job que não existe: a API responde 404, não 500. Teste na Task 3 (`test_api_job_inexistente`).

---

## Mapa de arquivos

| Arquivo | Responsabilidade | Task |
| --- | --- | --- |
| `services/coletor/app/gmaps.py` | Ler `about` do gosom como `sobre` | 1 |
| `services/coletor/app/instagram.py` | Escolher o melhor handle por nome e cidade | 2 |
| `services/coletor/app/fila.py` (novo) | Fila de jobs em SQLite | 3 |
| `services/coletor/app/worker.py` (novo) | Consome a fila e roda a coleta | 3 |
| `services/coletor/app/preferencias.py` | Recebe `personalizar`, que sai de `main.py` | 3 |
| `services/coletor/app/main.py` | Viagens viram jobs; `GET /jobs/{id}`; CORS por variável; endpoints de IA | 3, 5 |
| `services/coletor/app/ia.py` (novo) | Cliente do Groq, limitador, triagem, ranqueamento e roteiro | 4, 5 |
| `services/coletor/tests/test_*.py` | Testes novos, um arquivo por módulo | 1 a 5 |
| `docker-compose.yml`, `.env.example` | Serviço `worker` e variáveis | 3 |
| `apps/mobile/package-lock.json`, `.github/workflows/mobile.yml` | Lock e typecheck no CI | 6 |
| `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `.github/pull_request_template.md`, READMEs | Organização para o time | 7 |

---

### Task 1: Cards do Google com o campo `sobre`

O gosom manda `about` como JSON (`[{"id","name","options":[{"name","enabled"}]}]`). Hoje ele é descartado, e `descriptions` vem vazio na maioria dos lugares. A IA precisa de texto para ranquear.

**Files:**
- Modify: `services/coletor/app/gmaps.py` (função `linha_para_lugar`)
- Test: `services/coletor/tests/test_gmaps.py` (novo)

**Interfaces:**
- Produces: `gmaps.sobre_de_about(valor: str) -> list[str]`; `linha_para_lugar` passa a devolver a chave `"sobre": list[str]`, que `coletor._card_google` já copia para o card.

- [ ] **Step 1: Escrever o teste que falha**

```python
# services/coletor/tests/test_gmaps.py
import json

from app import gmaps

ABOUT = json.dumps([
    {"id": "accessibility", "name": "Acessibilidade", "options": [
        {"name": "Entrada acessível", "enabled": True},
        {"name": "Banheiro acessível", "enabled": False}]},
    {"id": "service", "name": "Opções de serviço", "options": [
        {"name": "Refeição no local", "enabled": True},
        {"name": "Aceita pets", "enabled": True}]},
])


def test_sobre_so_opcoes_ativas():
    assert gmaps.sobre_de_about(ABOUT) == ["Entrada acessível", "Refeição no local", "Aceita pets"]


def test_sobre_invalido_ou_vazio():
    assert gmaps.sobre_de_about("") == []
    assert gmaps.sobre_de_about("não é json") == []
    assert gmaps.sobre_de_about('{"id": "x"}') == []


def test_sobre_limita_a_oito():
    muitas = json.dumps([{"options": [{"name": f"op{i}", "enabled": True} for i in range(12)]}])
    assert len(gmaps.sobre_de_about(muitas)) == 8


def test_linha_para_lugar_inclui_sobre():
    lugar = gmaps.linha_para_lugar({"title": "X", "about": ABOUT})
    assert lugar["sobre"][0] == "Entrada acessível"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd services/coletor && python -m pytest tests/test_gmaps.py -v`
Expected: FAIL com `AttributeError: module 'app.gmaps' has no attribute 'sobre_de_about'`

- [ ] **Step 3: Implementar**

Em `gmaps.py`, logo depois de `_json`:

```python
def sobre_de_about(valor: str, limite: int = 8) -> list[str]:
    """Opções ativas do campo "about" do gosom: "Aceita pets", "Entrada acessível"…"""
    secoes = _json(valor)
    if not isinstance(secoes, list):
        return []
    nomes = [op["name"] for s in secoes if isinstance(s, dict)
             for op in s.get("options") or [] if isinstance(op, dict) and op.get("enabled") and op.get("name")]
    return nomes[:limite]
```

Em `linha_para_lugar`, depois de `"descricao": ...`:

```python
        "sobre": sobre_de_about(linha.get("about", "")),
```

- [ ] **Step 4: Rodar tudo e ver passar**

Run: `cd services/coletor && python -m pytest -q`
Expected: todos passam (8 antigos + 4 novos)

- [ ] **Step 5: Commit**

```bash
git add services/coletor/app/gmaps.py services/coletor/tests/test_gmaps.py
git commit -m "Coletor: cards do Google trazem o campo sobre (about do gosom)"
```

---

### Task 2: Instagram por busca escolhe pelo nome e pela cidade

Hoje `por_busca` fica com o primeiro resultado em que uma palavra do nome aparece. Na busca real por "Cantina do Nono Curitiba", 4 de 6 perfis passavam.

**Files:**
- Modify: `services/coletor/app/instagram.py` (`por_busca`, nova `escolher_handle`)
- Test: `services/coletor/tests/test_instagram.py` (novo)

**Interfaces:**
- Produces: `instagram.escolher_handle(nome: str, cidade: str, resultados: list[dict]) -> str | None`. Cada resultado tem `href`, `title` e `body`, como os do `DDGS().text`.

- [ ] **Step 1: Escrever o teste que falha**

```python
# services/coletor/tests/test_instagram.py
from app import instagram


def r(handle, title, body=""):
    return {"href": f"https://www.instagram.com/{handle}/", "title": title, "body": body}


def test_cidade_no_texto_ganha_da_ordem():
    res = [r("cantina_nono", "Cantina do Nono (@cantina_nono)", "Canela, RS. Massas"),
           r("cantinadonono", "Cantina do Nono (@cantinadonono)", "Curitiba, PR. Massa caseira")]
    assert instagram.escolher_handle("Cantina do Nono", "Curitiba", res) == "cantinadonono"


def test_sem_cidade_vence_o_handle_mais_parecido():
    res = [r("cantinadononofilho", "Cantina do Nono Filho"),
           r("cantinadonono", "Cantina do Nono")]
    assert instagram.escolher_handle("Cantina do Nono", "Lages", res) == "cantinadonono"


def test_nome_que_nao_bate_devolve_none():
    res = [r("nonnogastronomia", "Nonno Gastronomia"), r("p", "post qualquer")]
    assert instagram.escolher_handle("Churrascaria Gaúcha", "Lages", res) is None


def test_lista_vazia():
    assert instagram.escolher_handle("X", "Y", []) is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd services/coletor && python -m pytest tests/test_instagram.py -v`
Expected: FAIL com `AttributeError: ... 'escolher_handle'`

- [ ] **Step 3: Implementar**

Em `instagram.py`, adicionar `import difflib` aos imports e, depois de `parece_o_mesmo`:

```python
def escolher_handle(nome: str, cidade: str, resultados: list[dict]) -> str | None:
    """Melhor perfil entre os resultados da busca: nome parecido e, de preferência, da cidade."""
    alvo = _norm(nome).replace(" ", "")
    cid = _norm(cidade).replace(" ", "")
    melhor, melhor_nota = None, 0.0
    for res in resultados:
        h = handle_de_texto(res.get("href", ""))
        texto = f'{res.get("title", "")} {res.get("body", "")}'
        if not h or not parece_o_mesmo(nome, f"{texto} {h}"):
            continue
        nota = difflib.SequenceMatcher(None, alvo, _norm(h).replace(" ", "")).ratio()
        if cid and cid in _norm(texto).replace(" ", ""):
            nota += 1.0
        if nota > melhor_nota:
            melhor, melhor_nota = h, nota
    return melhor if melhor_nota >= 0.5 else None
```

Em `por_busca`, trocar o laço final inteiro (`for r in resultados or []: ...` até o `return None`) por:

```python
    return escolher_handle(nome, cidade, resultados or [])
```

- [ ] **Step 4: Rodar tudo e ver passar**

Run: `cd services/coletor && python -m pytest -q`
Expected: todos passam

- [ ] **Step 5: Commit**

```bash
git add services/coletor/app/instagram.py services/coletor/tests/test_instagram.py
git commit -m "Coletor: Instagram por busca pesa nome e cidade, não o primeiro resultado"
```

---

### Task 3: Fila de jobs, worker e API assíncrona

A coleta leva minutos e hoje roda dentro da requisição. Passa a ser assim: `POST /viagem/*` cria o job e responde 202 com o `job_id`; o worker coleta; `GET /jobs/{id}` devolve o status e, quando pronto, o resultado.

**Files:**
- Create: `services/coletor/app/fila.py`, `services/coletor/app/worker.py`
- Modify: `services/coletor/app/preferencias.py` (recebe `personalizar`), `services/coletor/app/main.py`, `docker-compose.yml`
- Create: `.env.example`, `services/coletor/requirements-dev.txt`
- Test: `services/coletor/tests/test_fila.py` (novo); `services/coletor/tests/test_offline.py` (`test_api` muda)

**Interfaces:**
- Produces (`fila.py`):
  - `DB: str` (variável `PV_DB`, padrão `planejador.db`; os testes trocam por `monkeypatch`)
  - `criar(tipo: str, entrada: dict) -> str`: devolve o id (uuid hex)
  - `pegar_proximo() -> dict | None`: marca o mais antigo `pendente` como `rodando` e devolve `{"id", "tipo", "entrada"}`
  - `concluir(job_id: str, resultado: dict) -> None` e `falhar(job_id: str, erro: str) -> None`
  - `obter(job_id: str) -> dict | None`: devolve `{"id", "tipo", "status", "resultado", "erro", "criado_em", "atualizado_em"}`
  - Status possíveis: `pendente`, `rodando`, `pronto`, `falhou`
- Produces (`worker.py`): `async processar(job: dict) -> dict`, `async rodar_uma_vez() -> bool` (True se processou um job) e `main() -> None` (laço infinito)
- Produces (`preferencias.py`): `personalizar(resultado: dict, usuario: str | None) -> dict` (o mesmo corpo de `main._personalizar`)
- Produces (API): `POST /viagem/carro` e `POST /viagem/aviao` → 202 `{"job_id": str, "status": "pendente"}`; `GET /jobs/{job_id}` → 200 com `fila.obter(...)` ou 404

- [ ] **Step 1: Escrever os testes da fila que falham**

```python
# services/coletor/tests/test_fila.py
import asyncio

import pytest

from app import fila, worker


@pytest.fixture(autouse=True)
def banco(tmp_path, monkeypatch):
    monkeypatch.setattr(fila, "DB", str(tmp_path / "fila.db"))


def test_ciclo_de_vida():
    jid = fila.criar("carro", {"origem": "A", "destino": "B"})
    assert fila.obter(jid)["status"] == "pendente"
    job = fila.pegar_proximo()
    assert job == {"id": jid, "tipo": "carro", "entrada": {"origem": "A", "destino": "B"}}
    assert fila.obter(jid)["status"] == "rodando"
    fila.concluir(jid, {"paradas": []})
    j = fila.obter(jid)
    assert j["status"] == "pronto" and j["resultado"] == {"paradas": []} and j["erro"] is None


def test_fila_nao_entrega_duas_vezes():
    a = fila.criar("carro", {})
    b = fila.criar("carro", {})
    assert [fila.pegar_proximo()["id"], fila.pegar_proximo()["id"]] == [a, b]
    assert fila.pegar_proximo() is None


def test_obter_inexistente():
    assert fila.obter("nao-existe") is None


def test_worker_processa(monkeypatch):
    async def falso(**kw):
        return {"modo": "carro", "paradas": [], "recebido": kw}
    monkeypatch.setattr(worker.coletor, "planejar_carro", falso)
    jid = fila.criar("carro", {"origem": "A", "destino": "B"})
    assert asyncio.run(worker.rodar_uma_vez()) is True
    j = fila.obter(jid)
    assert j["status"] == "pronto" and j["resultado"]["recebido"]["origem"] == "A"
    assert asyncio.run(worker.rodar_uma_vez()) is False


def test_worker_marca_falha(monkeypatch):
    async def quebra(**kw):
        raise ValueError("Não achamos essa cidade")
    monkeypatch.setattr(worker.coletor, "planejar_carro", quebra)
    ruim = fila.criar("carro", {"origem": "?", "destino": "?"})
    bom = fila.criar("tipo-desconhecido", {})
    assert asyncio.run(worker.rodar_uma_vez()) is True
    assert fila.obter(ruim)["status"] == "falhou"
    assert "Não achamos" in fila.obter(ruim)["erro"]
    assert asyncio.run(worker.rodar_uma_vez()) is True
    assert fila.obter(bom)["status"] == "falhou"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd services/coletor && python -m pytest tests/test_fila.py -v`
Expected: FAIL com `ImportError: cannot import name 'fila'`

- [ ] **Step 3: Implementar `fila.py`**

```python
# services/coletor/app/fila.py
"""Fila de jobs de coleta em SQLite.

A API cria o job e responde na hora; o worker (app/worker.py) pega o mais
antigo, roda a coleta e grava o resultado. A interface (criar, pegar_proximo,
concluir, falhar, obter) é a mesma que a versão em Postgres vai ter.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import closing

DB = os.getenv("PV_DB", "planejador.db")


def _con() -> sqlite3.Connection:
    con = sqlite3.connect(DB, timeout=30)
    con.execute("""CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY, tipo TEXT NOT NULL, entrada TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pendente', resultado TEXT, erro TEXT,
        criado_em TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
        atualizado_em TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')))""")
    return con


def criar(tipo: str, entrada: dict) -> str:
    jid = uuid.uuid4().hex
    with closing(_con()) as con, con:
        con.execute("INSERT INTO jobs (id, tipo, entrada) VALUES (?,?,?)",
                    (jid, tipo, json.dumps(entrada, ensure_ascii=False)))
    return jid


def pegar_proximo() -> dict | None:
    with closing(_con()) as con, con:
        linha = con.execute(
            "UPDATE jobs SET status='rodando', atualizado_em=strftime('%Y-%m-%dT%H:%M:%f', 'now') "
            "WHERE id = (SELECT id FROM jobs WHERE status='pendente' ORDER BY criado_em, rowid LIMIT 1) "
            "RETURNING id, tipo, entrada").fetchone()
    return {"id": linha[0], "tipo": linha[1], "entrada": json.loads(linha[2])} if linha else None


def _fechar(job_id: str, status: str, resultado: dict | None, erro: str | None) -> None:
    with closing(_con()) as con, con:
        con.execute("UPDATE jobs SET status=?, resultado=?, erro=?, "
                    "atualizado_em=strftime('%Y-%m-%dT%H:%M:%f', 'now') WHERE id=?",
                    (status, json.dumps(resultado, ensure_ascii=False) if resultado is not None else None,
                     erro, job_id))


def concluir(job_id: str, resultado: dict) -> None:
    _fechar(job_id, "pronto", resultado, None)


def falhar(job_id: str, erro: str) -> None:
    _fechar(job_id, "falhou", None, erro)


def obter(job_id: str) -> dict | None:
    with closing(_con()) as con:
        l = con.execute("SELECT id, tipo, status, resultado, erro, criado_em, atualizado_em "
                        "FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not l:
        return None
    return {"id": l[0], "tipo": l[1], "status": l[2], "resultado": json.loads(l[3]) if l[3] else None,
            "erro": l[4], "criado_em": l[5], "atualizado_em": l[6]}
```

- [ ] **Step 4: Mover `personalizar` para `preferencias.py`**

No fim de `preferencias.py`:

```python
def personalizar(resultado: dict, usuario: str | None) -> dict:
    """Tira cards já avaliados e ordena os novos pelo gosto do usuário."""
    if not usuario:
        return resultado
    vistos, p = ja_vistos(usuario), perfil(usuario)
    for parada in resultado["paradas"]:
        parada["cards"] = pontuar([c for c in parada["cards"] if c["id"] not in vistos], p)
    return resultado
```

- [ ] **Step 5: Implementar `worker.py`**

```python
# services/coletor/app/worker.py
"""Worker de coleta. Rode com:  python -m app.worker

Pega um job da fila por vez, roda a coleta (minutos, por causa do gosom) e
grava o resultado. Um job que quebra vira "falhou" e o worker segue.
"""
from __future__ import annotations

import asyncio
import logging
import os

from . import coletor, fila, preferencias

log = logging.getLogger("desvio.worker")
INTERVALO_S = float(os.getenv("PV_WORKER_INTERVALO", "2"))


async def processar(job: dict) -> dict:
    e = dict(job["entrada"])
    usuario = e.pop("usuario", None)
    if job["tipo"] == "carro":
        r = await coletor.planejar_carro(**e)
    elif job["tipo"] == "aviao":
        r = await coletor.planejar_cidades(**e)
    else:
        raise ValueError(f"Tipo de job desconhecido: {job['tipo']}")
    return preferencias.personalizar(r, usuario)


async def rodar_uma_vez() -> bool:
    job = fila.pegar_proximo()
    if not job:
        return False
    try:
        fila.concluir(job["id"], await processar(job))
    except Exception as e:  # o worker não pode morrer por causa de um job
        log.exception("job %s falhou", job["id"])
        fila.falhar(job["id"], str(e) or e.__class__.__name__)
    return True


async def _laco() -> None:
    while True:
        if not await rodar_uma_vez():
            await asyncio.sleep(INTERVALO_S)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_laco())


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Rodar os testes da fila e ver passar**

Run: `cd services/coletor && python -m pytest tests/test_fila.py -v`
Expected: 5 PASS

- [ ] **Step 7: Mudar a API e o `test_api`**

Em `main.py`: trocar o import para `from fastapi import FastAPI, HTTPException`, adicionar `import os` e `from . import coletor, fila, preferencias, roteiro`, e apagar `_personalizar`. O CORS passa a ler a variável:

```python
ORIGENS = [o.strip() for o in os.getenv("PV_CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=ORIGENS, allow_methods=["*"], allow_headers=["*"])
```

Os dois endpoints de viagem e o novo endpoint de job:

```python
@app.post("/viagem/carro", status_code=202)
def viagem_carro(req: ViagemCarro):
    return {"job_id": fila.criar("carro", req.model_dump()), "status": "pendente"}


@app.post("/viagem/aviao", status_code=202)
def viagem_aviao(req: ViagemAviao):
    return {"job_id": fila.criar("aviao", req.model_dump()), "status": "pendente"}


@app.get("/jobs/{job_id}")
def job(job_id: str):
    j = fila.obter(job_id)
    if not j:
        raise HTTPException(404, "Viagem não encontrada")
    return j
```

`ViagemAviao` tem os campos `cidades, categorias, por_categoria, usar_google_maps, buscar_instagram, usuario`. Todos eles, menos `usuario` (que o worker tira), são parâmetros de `coletor.planejar_cidades`, então `**e` funciona. O mesmo vale para `ViagemCarro` e `planejar_carro`. Atualizar a docstring do topo de `main.py`: o passo 1 vira "POST /viagem/carro ou /viagem/aviao → job_id; GET /jobs/{id} até status pronto".

Em `test_offline.py`, trocar `test_api` por:

```python
def test_api(mock_http, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import fila, worker
    from app.main import app
    monkeypatch.setattr(preferencias, "DB", str(tmp_path / "api.db"))
    monkeypatch.setattr(fila, "DB", str(tmp_path / "api.db"))
    cli = TestClient(app)
    r = cli.post("/viagem/aviao", json={"cidades": [{"cidade": "Destino, BA", "dias": 2}], "usuario": "leo"})
    assert r.status_code == 202, r.text
    jid = r.json()["job_id"]
    assert cli.get(f"/jobs/{jid}").json()["status"] == "pendente"
    assert asyncio.run(worker.rodar_uma_vez())
    j = cli.get(f"/jobs/{jid}").json()
    assert j["status"] == "pronto", j
    cards = j["resultado"]["paradas"][0]["cards"]
    assert cli.post("/swipe", json={"usuario": "leo", "card": cards[0], "gostou": True}).json()["ok"]
    assert cli.get("/perfil/leo").json()["aceitos"] == 1
    dias = cli.post("/roteiro/cidade", json={"cards": cards, "dias": 2}).json()
    assert len(dias) == 2


def test_api_job_inexistente(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import fila
    from app.main import app
    monkeypatch.setattr(fila, "DB", str(tmp_path / "x.db"))
    assert TestClient(app).get("/jobs/nao-existe").status_code == 404
```

- [ ] **Step 8: Rodar tudo e ver passar**

Run: `cd services/coletor && python -m pytest -q`
Expected: todos passam

- [ ] **Step 9: Serviço `worker`, `.env.example` e `requirements-dev.txt`**

`docker-compose.yml`: o `coletor` passa a ler `env_file: .env` (mantendo `PV_GOSOM_URL` e `PV_DB` em `environment`) e perde `PV_USER_AGENT` do bloco `environment`. Um serviço novo, depois de `coletor`:

```yaml
  worker:
    build: ./services/coletor
    command: ["python", "-m", "app.worker"]
    env_file: .env
    environment:
      - PV_GOSOM_URL=http://gosom:8080
      - PV_DB=/dados/desvio.db
    volumes:
      - ./dados:/dados
    depends_on:
      - gosom
```

`.env.example` na raiz:

```dotenv
# Copie para .env e preencha. O .env nunca vai para o Git.

# Nominatim exige um contato real no User-Agent
PV_USER_AGENT=desvio/0.1 (seu-email@exemplo.com)

# Groq (https://console.groq.com/keys). Sem chave, a IA cai no plano B.
GROQ_API_KEY=
# Opcionais
# PV_MODELO_RACIOCINIO=openai/gpt-oss-120b
# PV_MODELO_RAPIDO=openai/gpt-oss-20b

# Origens liberadas no CORS, separadas por vírgula (padrão: *)
# PV_CORS_ORIGINS=http://localhost:8081

# Servidores próprios (padrão: públicos)
# PV_OSRM_URL=
# PV_NOMINATIM_URL=
# PV_OVERPASS_URL=
```

`services/coletor/requirements-dev.txt`:

```text
-r requirements.txt
pytest>=8.0
```

`.github/workflows/coletor.yml`: trocar `pip install -r requirements.txt pytest` por `pip install -r requirements-dev.txt`.

Run: `docker compose config -q`
Expected: sem saída, código 0. Se reclamar que o `.env` não existe, crie antes com `cp .env.example .env`.

- [ ] **Step 10: Commit**

```bash
git add services/coletor docker-compose.yml .env.example .github/workflows/coletor.yml
git commit -m "Coletor: fila de jobs, worker separado e viagens assíncronas (202 + GET /jobs/{id})"
```

---

### Task 4: Cliente do Groq com limitador e plano B

**Files:**
- Create: `services/coletor/app/ia.py`
- Test: `services/coletor/tests/test_ia.py` (novo)

**Interfaces:**
- Produces:
  - `class IAIndisponivel(RuntimeError)`
  - `MODELO_RACIOCINIO: str` (env `PV_MODELO_RACIOCINIO`, padrão `openai/gpt-oss-120b`) e `MODELO_RAPIDO: str` (env `PV_MODELO_RAPIDO`, padrão `openai/gpt-oss-20b`)
  - `GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"`
  - `class Limitador(rpm: int = 30, tpm: int = 8000, relogio=time.monotonic)` com `espera(tokens: int) -> float` (segundos até caber) e `registrar(tokens: int) -> None`
  - `estimar_tokens(texto: str) -> int` (`len(texto) // 4 + 1`)
  - `async chamar_json(client: httpx.AsyncClient, *, modelo: str, sistema: str, dados: dict, schema: dict, nome: str, max_tokens: int = 1024, timeout: float = 10.0) -> dict`. Lança `IAIndisponivel` em todos os casos de falha: sem chave, 429, outro erro HTTP, timeout, JSON inválido ou espera do limitador maior que `timeout`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# services/coletor/tests/test_ia.py
import asyncio
import json

import httpx
import pytest

from app import ia

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}},
          "required": ["ok"], "additionalProperties": False}


def cliente(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def resposta(conteudo: str, status=200, headers=None):
    return httpx.Response(status, headers=headers,
                          json={"choices": [{"message": {"content": conteudo}}]} if status == 200 else {"error": {}})


@pytest.fixture(autouse=True)
def chave(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "teste")
    ia._limitadores.clear()


def chamar(handler, **kw):
    async def go():
        async with cliente(handler) as c:
            return await ia.chamar_json(c, modelo="m", sistema="s", dados={"x": 1},
                                        schema=SCHEMA, nome="t", **kw)
    return asyncio.run(go())


def test_chamada_ok_manda_schema_estrito():
    visto = {}
    def h(req):
        visto.update(json.loads(req.content))
        visto["auth"] = req.headers["authorization"]
        return resposta('{"ok": true}')
    assert chamar(h) == {"ok": True}
    assert visto["auth"] == "Bearer teste"
    assert visto["response_format"]["json_schema"]["strict"] is True
    assert visto["response_format"]["json_schema"]["schema"] == SCHEMA
    assert visto["reasoning_effort"] == "low"
    assert json.loads(visto["messages"][1]["content"]) == {"x": 1}


def test_ia_sem_chave(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY")
    with pytest.raises(ia.IAIndisponivel, match="GROQ_API_KEY"):
        chamar(lambda req: resposta('{"ok": true}'))


def test_429_vira_indisponivel():
    with pytest.raises(ia.IAIndisponivel, match="429"):
        chamar(lambda req: resposta("", status=429, headers={"retry-after": "7"}))


def test_json_invalido_vira_indisponivel():
    with pytest.raises(ia.IAIndisponivel):
        chamar(lambda req: resposta("isto não é json"))


def test_timeout_vira_indisponivel():
    def h(req):
        raise httpx.ReadTimeout("lento", request=req)
    with pytest.raises(ia.IAIndisponivel):
        chamar(h)


def test_limitador_por_tokens_e_requisicoes():
    agora = [100.0]
    lim = ia.Limitador(rpm=2, tpm=1000, relogio=lambda: agora[0])
    assert lim.espera(600) == 0
    lim.registrar(600)
    assert lim.espera(600) == pytest.approx(60.0)   # passaria de 1000 tokens no minuto
    assert lim.espera(300) == 0
    lim.registrar(300)
    assert lim.espera(10) == pytest.approx(60.0)    # já são 2 requisições no minuto
    agora[0] += 61
    assert lim.espera(600) == 0


def test_limitador_cheio_nao_espera_mais_que_o_timeout():
    ia._limitadores["m"] = ia.Limitador(rpm=1, tpm=8000)
    ia._limitadores["m"].registrar(10)
    with pytest.raises(ia.IAIndisponivel, match="limite"):
        chamar(lambda req: resposta('{"ok": true}'))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd services/coletor && python -m pytest tests/test_ia.py -v`
Expected: FAIL com `ImportError: cannot import name 'ia'`

- [ ] **Step 3: Implementar `ia.py`**

```python
# services/coletor/app/ia.py
"""IA do Desvio no Groq (plano gratuito), com saída em JSON validada por schema.

Os modelos gpt-oss aceitam structured outputs estritos. O plano gratuito tem,
por modelo e por organização, 30 requisições e 8.000 tokens por minuto: o
Limitador segura as chamadas para não tomar 429. Qualquer falha vira
IAIndisponivel, e quem chama usa o plano B sem IA (ver PRD, seção de IA).
"""
from __future__ import annotations

import asyncio
import collections
import json
import os
import time

import httpx

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELO_RACIOCINIO = os.getenv("PV_MODELO_RACIOCINIO", "openai/gpt-oss-120b")
MODELO_RAPIDO = os.getenv("PV_MODELO_RAPIDO", "openai/gpt-oss-20b")


class IAIndisponivel(RuntimeError):
    pass


def estimar_tokens(texto: str) -> int:
    return len(texto) // 4 + 1


class Limitador:
    """Janela deslizante de 60 s com limite de requisições e de tokens."""

    def __init__(self, rpm: int = 30, tpm: int = 8000, relogio=time.monotonic):
        self.rpm, self.tpm, self.relogio = rpm, tpm, relogio
        self._uso: collections.deque[tuple[float, int]] = collections.deque()

    def _limpar(self, agora: float) -> None:
        while self._uso and agora - self._uso[0][0] >= 60:
            self._uso.popleft()

    def espera(self, tokens: int) -> float:
        agora = self.relogio()
        self._limpar(agora)
        usados = sum(t for _, t in self._uso)
        if len(self._uso) < self.rpm and usados + tokens <= self.tpm:
            return 0.0
        return max(0.0, 60 - (agora - self._uso[0][0]))

    def registrar(self, tokens: int) -> None:
        self._uso.append((self.relogio(), tokens))


_limitadores: dict[str, Limitador] = {}


async def chamar_json(client: httpx.AsyncClient, *, modelo: str, sistema: str, dados: dict,
                      schema: dict, nome: str, max_tokens: int = 1024, timeout: float = 10.0) -> dict:
    chave = os.getenv("GROQ_API_KEY")
    if not chave:
        raise IAIndisponivel("GROQ_API_KEY não configurada")
    conteudo = json.dumps(dados, ensure_ascii=False)
    tokens = estimar_tokens(sistema + conteudo) + max_tokens
    lim = _limitadores.setdefault(modelo, Limitador())
    espera = lim.espera(tokens)
    if espera > timeout:
        raise IAIndisponivel(f"limite do Groq: {espera:.0f}s de espera para {modelo}")
    if espera:
        await asyncio.sleep(espera)
    lim.registrar(tokens)
    corpo = {
        "model": modelo,
        "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": conteudo}],
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": nome, "schema": schema, "strict": True}},
        "reasoning_effort": "low",  # tokens de raciocínio contam no limite por minuto
        "max_completion_tokens": max_tokens,
        "temperature": 0.3,
    }
    try:
        r = await client.post(GROQ_URL, json=corpo, timeout=timeout,
                              headers={"Authorization": f"Bearer {chave}"})
    except httpx.HTTPError as e:
        raise IAIndisponivel(f"Groq não respondeu: {e.__class__.__name__}") from e
    if r.status_code == 429:
        raise IAIndisponivel(f"Groq 429, tente em {r.headers.get('retry-after', '?')}s")
    if r.status_code >= 400:
        raise IAIndisponivel(f"Groq {r.status_code}")
    try:
        return json.loads(r.json()["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise IAIndisponivel("Groq devolveu JSON inválido") from e
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd services/coletor && python -m pytest tests/test_ia.py -v`
Expected: 7 PASS

- [ ] **Step 5: Commit**

```bash
git add services/coletor/app/ia.py services/coletor/tests/test_ia.py
git commit -m "Coletor: cliente do Groq com schema estrito, limitador por modelo e falha controlada"
```

---

### Task 5: Triagem, ranqueamento e roteiro com IA, e os endpoints

**Files:**
- Modify: `services/coletor/app/ia.py` (funções de produto)
- Modify: `services/coletor/app/main.py` (endpoints)
- Test: `services/coletor/tests/test_ia_produto.py` (novo)

**Interfaces:**
- Consumes: `ia.chamar_json`, `ia.IAIndisponivel`, `ia.MODELO_RACIOCINIO`, `ia.MODELO_RAPIDO` (Task 4); `roteiro.ordenar_carro` (existente)
- Produces:
  - `ia.PRIMEIRA_PERGUNTA: dict` e `ia.PERGUNTAS_RESERVA: list[dict]`, cada uma `{"pergunta": str, "opcoes": list[str]}`
  - `async ia.triagem(client, respostas: list[dict]) -> dict` → `{"pergunta": str | None, "opcoes": list[str], "fim": bool, "resumo": str | None, "fonte": "ia" | "fixa"}`; cada resposta é `{"pergunta": str, "resposta": str}`
  - `async ia.ranquear(client, cards: list[dict], resumo: str) -> list[dict]`: reordena os 30 primeiros e mantém o resto depois
  - `async ia.ajustar_roteiro(client, itens: list[dict], contexto: dict) -> dict` → `{"itens": list[dict], "explicacoes": dict[str, str], "fonte": "ia" | "geometria"}`
  - Endpoints: `POST /triagem` `{respostas}`; `POST /cards/ranquear` `{cards, resumo}` → lista; `POST /roteiro/carro` ganha `usar_ia: bool = False` e `contexto: dict = {}` (com `usar_ia`, devolve o dict de `ajustar_roteiro`; sem, a lista de sempre)

- [ ] **Step 1: Escrever os testes que falham**

```python
# services/coletor/tests/test_ia_produto.py
import asyncio
import json

import httpx
import pytest

from app import ia

CARDS = [{"id": f"c{i}", "nome": f"Lugar {i}", "categoria": "restaurante", "nota": 4.5,
          "avaliacoes": 100, "descricao": "x" * 300, "sobre": ["Aceita pets"], "km_na_rota": i * 10.0}
         for i in range(35)]


@pytest.fixture(autouse=True)
def limpa(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "teste")
    ia._limitadores.clear()


def rodar(coro_fn, conteudo=None, falha=False):
    enviados = []
    def h(req):
        enviados.append(json.loads(req.content))
        if falha:
            return httpx.Response(500)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(conteudo)}}]})
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
            return await coro_fn(c)
    return asyncio.run(go()), enviados


def test_triagem_primeira_pergunta_e_fixa_sem_ia():
    r, enviados = rodar(lambda c: ia.triagem(c, []))
    assert r["pergunta"] == ia.PRIMEIRA_PERGUNTA["pergunta"] and r["fonte"] == "fixa" and not r["fim"]
    assert enviados == []


def test_triagem_usa_ia_depois():
    resp = [{"pergunta": ia.PRIMEIRA_PERGUNTA["pergunta"], "resposta": "Natureza"}]
    ia_diz = {"pergunta": "Viaja com pet?", "opcoes": ["Sim", "Não"], "fim": False, "resumo": None}
    r, enviados = rodar(lambda c: ia.triagem(c, resp), ia_diz)
    assert r["pergunta"] == "Viaja com pet?" and r["fonte"] == "ia"
    assert enviados[0]["model"] == ia.MODELO_RACIOCINIO


def test_triagem_termina_na_quinta():
    resp = [{"pergunta": f"p{i}", "resposta": "r"} for i in range(5)]
    ia_diz = {"pergunta": "mais uma?", "opcoes": [], "fim": False, "resumo": "Gosta de natureza."}
    r, _ = rodar(lambda c: ia.triagem(c, resp), ia_diz)
    assert r["fim"] is True and r["pergunta"] is None and r["resumo"] == "Gosta de natureza."


def test_triagem_fallback_usa_reserva():
    resp = [{"pergunta": ia.PRIMEIRA_PERGUNTA["pergunta"], "resposta": "Natureza"}]
    r, _ = rodar(lambda c: ia.triagem(c, resp), falha=True)
    assert r["pergunta"] == ia.PERGUNTAS_RESERVA[0]["pergunta"] and r["fonte"] == "fixa"


def test_ranquear_reordena_os_30_primeiros_e_mantem_o_resto():
    ordem = [f"c{i}" for i in reversed(range(30))]
    r, enviados = rodar(lambda c: ia.ranquear(c, CARDS, "Viaja com pet"), {"ids": ordem})
    assert [c["id"] for c in r[:30]] == ordem
    assert [c["id"] for c in r[30:]] == [f"c{i}" for i in range(30, 35)]
    mandados = json.loads(enviados[0]["messages"][1]["content"])["cards"]
    assert len(mandados) == 30 and len(mandados[0]["descricao"]) <= 120
    assert enviados[0]["model"] == ia.MODELO_RAPIDO


def test_ranquear_ids_estranhos():
    r, _ = rodar(lambda c: ia.ranquear(c, CARDS[:4], "x"), {"ids": ["c2", "zzz", "c2", "c0"]})
    assert [c["id"] for c in r] == ["c2", "c0", "c1", "c3"]


def test_ranquear_fallback():
    r, _ = rodar(lambda c: ia.ranquear(c, CARDS[:3], "x"), falha=True)
    assert [c["id"] for c in r] == ["c0", "c1", "c2"]


def test_ranquear_sem_resumo_nao_chama_ia():
    r, enviados = rodar(lambda c: ia.ranquear(c, CARDS[:3], ""))
    assert enviados == [] and [c["id"] for c in r] == ["c0", "c1", "c2"]


def test_roteiro_ia_e_fallback():
    itens = [CARDS[2], CARDS[0], CARDS[1]]
    ia_diz = {"ordem": [{"id": "c1", "porque": "almoço"}, {"id": "c0", "porque": "café"}]}
    r, _ = rodar(lambda c: ia.ajustar_roteiro(c, itens, {"saida": "07:00"}), ia_diz)
    assert [c["id"] for c in r["itens"]] == ["c1", "c0", "c2"] and r["fonte"] == "ia"
    assert r["explicacoes"] == {"c1": "almoço", "c0": "café"}
    r2, _ = rodar(lambda c: ia.ajustar_roteiro(c, itens, {}), falha=True)
    assert [c["id"] for c in r2["itens"]] == ["c0", "c1", "c2"] and r2["fonte"] == "geometria"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd services/coletor && python -m pytest tests/test_ia_produto.py -v`
Expected: FAIL com `AttributeError: module 'app.ia' has no attribute 'triagem'`

- [ ] **Step 3: Implementar as funções em `ia.py`**

Adicionar `from . import roteiro` aos imports e, no fim do arquivo:

```python
# --- Triagem -----------------------------------------------------------------

MAX_PERGUNTAS = 5
PRIMEIRA_PERGUNTA = {"pergunta": "O que não pode faltar numa viagem sua?",
                     "opcoes": ["Comida boa", "Natureza", "Pontos turísticos", "Descanso", "Aventura"]}
PERGUNTAS_RESERVA = [
    {"pergunta": "Com quem você costuma viajar?", "opcoes": ["Sozinho", "Casal", "Família com crianças", "Amigos", "Com pet"]},
    {"pergunta": "Que comida você procura na estrada?", "opcoes": ["Comida caseira", "Churrasco", "Lanche rápido", "Vegetariana", "Tanto faz"]},
    {"pergunta": "Quanto quer gastar por refeição?", "opcoes": ["Até R$ 50", "R$ 50 a 100", "Mais de R$ 100"]},
    {"pergunta": "Prefere lugares famosos ou escondidos?", "opcoes": ["Famosos", "Escondidos", "Um pouco de cada"]},
]
_SCHEMA_TRIAGEM = {
    "type": "object", "additionalProperties": False,
    "required": ["pergunta", "opcoes", "fim", "resumo"],
    "properties": {"pergunta": {"type": ["string", "null"]},
                   "opcoes": {"type": "array", "items": {"type": "string"}},
                   "fim": {"type": "boolean"},
                   "resumo": {"type": ["string", "null"]}},
}
_SISTEMA_TRIAGEM = (
    "Você monta o perfil de gosto de viagem de uma pessoa no Brasil, com no máximo "
    f"{MAX_PERGUNTAS} perguntas. Recebe as respostas até agora. Faça a próxima pergunta curta, "
    "tratando por 'você', com 2 a 5 opções curtas, sem repetir assunto. Quando já der para "
    "recomendar lugares (ou na última pergunta), responda fim=true, pergunta=null, opcoes=[] e "
    "um resumo de uma frase do gosto da pessoa. Português do Brasil.")


async def triagem(client: httpx.AsyncClient, respostas: list[dict]) -> dict:
    if not respostas:
        return {**PRIMEIRA_PERGUNTA, "fim": False, "resumo": None, "fonte": "fixa"}
    try:
        r = await chamar_json(client, modelo=MODELO_RACIOCINIO, sistema=_SISTEMA_TRIAGEM,
                              dados={"respostas": respostas, "restantes": MAX_PERGUNTAS - len(respostas)},
                              schema=_SCHEMA_TRIAGEM, nome="triagem", max_tokens=400)
        r["fonte"] = "ia"
    except IAIndisponivel:
        i = len(respostas) - 1
        r = ({**PERGUNTAS_RESERVA[i], "fim": False, "resumo": None} if i < len(PERGUNTAS_RESERVA)
             else {"pergunta": None, "opcoes": [], "fim": True, "resumo": None})
        r["fonte"] = "fixa"
    if len(respostas) >= MAX_PERGUNTAS or r["fim"]:
        r.update(pergunta=None, opcoes=[], fim=True)
    return r


# --- Ranqueamento ------------------------------------------------------------

MAX_RANQUEAR = 30
_SCHEMA_RANQUEAR = {"type": "object", "additionalProperties": False, "required": ["ids"],
                    "properties": {"ids": {"type": "array", "items": {"type": "string"}}}}
_SISTEMA_RANQUEAR = (
    "Você ordena lugares numa parada de viagem pelo gosto da pessoa. Recebe o resumo do gosto e "
    "os cards. Devolva todos os ids, do mais recomendado ao menos, sem inventar ids.")


def _card_enxuto(c: dict) -> dict:
    return {"id": c["id"], "nome": c.get("nome"), "categoria": c.get("categoria"), "tipo": c.get("tipo"),
            "nota": c.get("nota"), "avaliacoes": c.get("avaliacoes"),
            "descricao": (c.get("descricao") or "")[:120], "sobre": (c.get("sobre") or [])[:5]}


def _reordenar(cards: list[dict], ids: list[str]) -> list[dict]:
    por_id = {c["id"]: c for c in cards}
    vistos: set[str] = set()
    saida = []
    for i in ids:
        if i in por_id and i not in vistos:
            saida.append(por_id[i])
            vistos.add(i)
    return saida + [c for c in cards if c["id"] not in vistos]


async def ranquear(client: httpx.AsyncClient, cards: list[dict], resumo: str) -> list[dict]:
    topo, resto = cards[:MAX_RANQUEAR], cards[MAX_RANQUEAR:]
    if not resumo or len(topo) < 2:
        return cards
    try:
        r = await chamar_json(client, modelo=MODELO_RAPIDO, sistema=_SISTEMA_RANQUEAR,
                              dados={"gosto": resumo, "cards": [_card_enxuto(c) for c in topo]},
                              schema=_SCHEMA_RANQUEAR, nome="ranqueamento", max_tokens=600)
    except IAIndisponivel:
        return cards
    return _reordenar(topo, r["ids"]) + resto


# --- Roteiro -----------------------------------------------------------------

_SCHEMA_ROTEIRO = {
    "type": "object", "additionalProperties": False, "required": ["ordem"],
    "properties": {"ordem": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["id", "porque"],
        "properties": {"id": {"type": "string"}, "porque": {"type": "string"}}}}},
}
_SISTEMA_ROTEIRO = (
    "Você ajusta a ordem das paradas de uma viagem de carro. Recebe os lugares já em ordem de km "
    "e o contexto (hora de saída, dias). Ajuste ao horário: almoço entre 11h e 14h, mirante no fim "
    "da tarde, pernoite. Não volte na estrada mais de 30 km. Para cada lugar, uma linha curta "
    "dizendo por quê, em português do Brasil.")


async def ajustar_roteiro(client: httpx.AsyncClient, itens: list[dict], contexto: dict) -> dict:
    base = roteiro.ordenar_carro(itens)
    try:
        r = await chamar_json(client, modelo=MODELO_RACIOCINIO, sistema=_SISTEMA_ROTEIRO,
                              dados={"contexto": contexto,
                                     "lugares": [{**_card_enxuto(c), "km_na_rota": c.get("km_na_rota"),
                                                  "horarios": c.get("horarios")} for c in base]},
                              schema=_SCHEMA_ROTEIRO, nome="roteiro", max_tokens=1200)
    except IAIndisponivel:
        return {"itens": base, "explicacoes": {}, "fonte": "geometria"}
    validos = {c["id"] for c in base}
    explic = {o["id"]: o["porque"] for o in r["ordem"] if o["id"] in validos}
    return {"itens": _reordenar(base, [o["id"] for o in r["ordem"]]), "explicacoes": explic, "fonte": "ia"}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd services/coletor && python -m pytest tests/test_ia_produto.py -v`
Expected: 9 PASS

- [ ] **Step 5: Endpoints em `main.py` e teste de API**

Adicionar `import httpx` e `ia` ao import de `.`. Modelos e endpoints novos:

```python
class Triagem(BaseModel):
    respostas: list[dict] = []


class Ranquear(BaseModel):
    cards: list[dict]
    resumo: str = ""


@app.post("/triagem")
async def triagem(req: Triagem):
    async with httpx.AsyncClient() as client:
        return await ia.triagem(client, req.respostas)


@app.post("/cards/ranquear")
async def ranquear(req: Ranquear):
    async with httpx.AsyncClient() as client:
        return await ia.ranquear(client, req.cards, req.resumo)
```

Em `RoteiroCarro`, adicionar `usar_ia: bool = False` e `contexto: dict = {}`. O endpoint fica assim:

```python
@app.post("/roteiro/carro")
async def roteiro_carro(req: RoteiroCarro):
    if not req.usar_ia:
        return roteiro.ordenar_carro(req.cards)
    async with httpx.AsyncClient() as client:
        return await ia.ajustar_roteiro(client, req.cards, req.contexto)
```

No fim de `test_ia_produto.py`:

```python
def test_endpoints_sem_chave_funcionam(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.delenv("GROQ_API_KEY")
    cli = TestClient(app)
    assert cli.post("/triagem", json={"respostas": []}).json()["fonte"] == "fixa"
    assert [c["id"] for c in cli.post("/cards/ranquear", json={"cards": CARDS[:3], "resumo": "x"}).json()] == ["c0", "c1", "c2"]
    r = cli.post("/roteiro/carro", json={"cards": CARDS[:3], "usar_ia": True}).json()
    assert r["fonte"] == "geometria"
```

Run: `cd services/coletor && python -m pytest -q`
Expected: todos passam

- [ ] **Step 6: Commit**

```bash
git add services/coletor/app/ia.py services/coletor/app/main.py services/coletor/tests/test_ia_produto.py
git commit -m "Coletor: triagem, ranqueamento e roteiro com IA no Groq, com plano B sem IA"
```

---

### Task 6: App com lockfile e typecheck no CI

**Files:**
- Create: `apps/mobile/package-lock.json` (gerado)
- Create: `.github/workflows/mobile.yml`
- Modify: arquivos `.tsx` do app, só se o typecheck acusar erro

- [ ] **Step 1: Instalar e rodar o typecheck**

Run: `cd apps/mobile && npm install && npm run typecheck`
Expected: `tsc --noEmit` sem erros. Se der erro de tipo, corrija o arquivo apontado no menor diff possível e rode de novo. Se for erro de versão entre pacotes do Expo, rode `npx expo install --check` e aceite as versões sugeridas.

- [ ] **Step 2: Workflow do app**

```yaml
# .github/workflows/mobile.yml
name: mobile

on:
  push:
    paths: ["apps/mobile/**", "packages/design-tokens/**", ".github/workflows/mobile.yml"]
  pull_request:
    paths: ["apps/mobile/**", "packages/design-tokens/**", ".github/workflows/mobile.yml"]

jobs:
  typecheck:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/mobile
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: apps/mobile/package-lock.json
      - run: npm ci
      - run: npm run tokens
      - run: git diff --exit-code src/tema/tokens.gerado.ts
      - run: npm run typecheck
```

O passo `git diff --exit-code` falha quando alguém muda `tokens.json` e esquece de rodar `npm run tokens`.

Run: `cd apps/mobile && npm run tokens && git diff --exit-code src/tema/tokens.gerado.ts`
Expected: sem diferença

- [ ] **Step 3: Commit**

```bash
git add apps/mobile/package-lock.json .github/workflows/mobile.yml apps/mobile
git commit -m "App: lockfile e CI de typecheck e tokens"
```

---

### Task 7: AGENTS.md, CLAUDE.md, guia de contribuição e docs

**Files:**
- Create: `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `.github/pull_request_template.md`
- Modify: `README.md`, `services/coletor/README.md`, `docs/verificacao-stack.md`

- [ ] **Step 1: `AGENTS.md`**

Este é o guia canônico para agentes de IA e para pessoas. Tem que conter, em seções curtas:

1. **O projeto em 3 linhas** e onde estão o PRD (`docs/PRD.md`), o design system (`docs/design/DESIGN-SYSTEM.md`), as telas (`docs/design/telas/`) e a verificação da stack.
2. **Mapa do monorepo**: o que mora em cada pasta (`apps/mobile`, `services/coletor/app/*.py` com uma linha por módulo, `packages/design-tokens`, `docs`).
3. **Comandos** exatos para instalar, testar, rodar a API, o worker, o CLI, o gosom, o app, o typecheck e os tokens.
4. **Regras de código**: português do Brasil nos nomes; nada de dependência Python nova sem discutir no PR; testes sem internet (`httpx.MockTransport`); toda chamada de IA passa por `app/ia.py` e tem plano B; a chave só no servidor; o Google só via `gmaps.py`; cores, espaços e fontes só pelos tokens (`@/tema`), nunca hex solto; telas seguem o canvas e as regras de voz do design system.
5. **Fluxo de trabalho**: branch a partir de `main`, PR pequeno, CI verde, um revisor; nunca commit direto na `main`; mensagens de commit em português, no imperativo ou descritivas como as do histórico; **sem trailer `Co-Authored-By` de IA**.
6. **Armadilhas conhecidas**: o gosom leva no mínimo uns 3 minutos por job; limites do Groq gratuito; Nominatim a 1 req/s com e-mail real; o Expo Go não recebe push no Android; o `.env` nunca vai para o Git.
7. **Antes de dizer que terminou**: `python -m pytest -q` no coletor e `npm run typecheck` no app.

- [ ] **Step 2: `CLAUDE.md`**

```markdown
# CLAUDE.md

@AGENTS.md

## Específico do Claude Code

- Para tarefas de várias etapas, use as skills do superpowers: `superpowers:brainstorming` antes de criar algo novo, `superpowers:writing-plans` para o plano (salve em `docs/superpowers/plans/`), `superpowers:test-driven-development` ao implementar e `superpowers:verification-before-completion` antes de dizer que terminou.
- Os planos já feitos ficam em `docs/superpowers/plans/`; leia o mais recente antes de mexer na mesma área.
- Telas: o layout de referência está em `docs/design/telas/*.dc.html` e o canvas vivo no link de `docs/design/README.md`.
- Nunca adicione `Co-Authored-By` nos commits.
```

- [ ] **Step 3: `CONTRIBUTING.md` e template de PR**

`CONTRIBUTING.md`: o primeiro setup passo a passo (clonar, `cp .env.example .env`, preencher `PV_USER_AGENT` e `GROQ_API_KEY`, criar o venv, `pip install -r requirements-dev.txt`, `docker compose up --build`, `npm install` no app); como escolher tarefa (issues do GitHub, uma pessoa por issue); branches `tipo/descricao-curta` (`feat/`, `fix/`, `docs/`); o checklist do PR; e quem revisa.

`.github/pull_request_template.md`:

```markdown
## O que muda

## Histórias do PRD
<!-- ex.: HU09, HU10 -->

## Como testei
- [ ] `python -m pytest -q` em services/coletor
- [ ] `npm run typecheck` em apps/mobile
- [ ] Testei no aparelho ou emulador (se mexeu no app)

## Telas
<!-- prints claro e escuro, se mexeu em tela -->
```

- [ ] **Step 4: Atualizar os READMEs e a verificação**

- `README.md`: na seção "Rodando", trocar o bloco do coletor para mostrar API e worker (`uvicorn app.main:app --reload` e `python -m app.worker`), citar `.env.example` e apontar para `CONTRIBUTING.md` e `AGENTS.md`.
- `services/coletor/README.md`: trocar o título para "Coletor do Desvio"; na tabela de endpoints, `/viagem/*` devolve `job_id` (202) e aparecem `GET /jobs/{id}`, `POST /triagem`, `POST /cards/ranquear` e `usar_ia` em `/roteiro/carro`; na seção "Próximos passos", tirar os itens já feitos (IA e fila).
- `docs/verificacao-stack.md`: depois do resumo, uma seção "Corrigido em 2026-10-15" listando o que este plano resolveu (fila e worker, IA com plano B, Instagram, `sobre`, `.env.example`, CORS) e o que continua aberto (fila no Postgres do Supabase, push com development build, VPS para o gosom).

Run: `cd services/coletor && python -m pytest -q`
Expected: todos passam

- [ ] **Step 5: Commit e PR**

```bash
git add AGENTS.md CLAUDE.md CONTRIBUTING.md .github/pull_request_template.md README.md services/coletor/README.md docs/verificacao-stack.md
git commit -m "Docs: AGENTS.md, CLAUDE.md, guia de contribuição e template de PR"
git push -u origin organizacao-inicial
gh pr create --title "Organização do repositório e correções da verificação da stack" --body-file <arquivo com resumo>
```
