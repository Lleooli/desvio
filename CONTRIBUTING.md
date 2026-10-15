# Como contribuir

As regras de código e a arquitetura estão em [AGENTS.md](AGENTS.md). Este guia é o passo a passo para começar.

## Primeiro setup

Você precisa de Python 3.11+, Node 22+, Docker e Git.

```bash
git clone https://github.com/Lleooli/desvio.git
cd desvio
cp .env.example .env
```

No `.env`, preencha:

- `PV_USER_AGENT` com o seu e-mail (o Nominatim exige)
- `GROQ_API_KEY` com uma chave gratuita de https://console.groq.com/keys. Sem ela, tudo funciona, mas a IA usa o plano B.

A API, o worker e o `cli.py` leem esse arquivo sozinhos, e o docker compose também. Não precisa exportar nada.

**Coletor:**

```bash
cd services/coletor
python -m venv .venv
source .venv/bin/activate        # no Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m pytest -q              # tudo verde antes de começar
```

Para rodar a API e o worker juntos com o Google Maps, use `docker compose up --build` na raiz. Sem Docker, rode `uvicorn app.main:app --reload` e `python -m app.worker` em dois terminais.

**App:**

```bash
cd apps/mobile
npm install
npx expo start
```

## Escolhendo o que fazer

- O trabalho fica nas issues do GitHub. Cada issue cita a história do PRD (HU01 a HU19).
- Atribua a issue a você antes de começar. Uma pessoa por issue.
- O marco atual está em `docs/PRD.md`, seção "Marcos e entregas".

## Branches e commits

- Crie a branch a partir da `main` atualizada: `feat/swipe-desfazer`, `fix/instagram-homonimo`, `docs/rotas`.
- Commits em português, curtos, dizendo o que mudou.
- Sem trailer `Co-Authored-By` de IA.

## Pull request

1. `python -m pytest -q` em `services/coletor` e `npm run typecheck` em `apps/mobile` passando
2. Se mexeu em tela: prints nos temas claro e escuro
3. Preencha o template do PR, com a história do PRD
4. Peça revisão de um colega. O merge só acontece com o CI verde e uma aprovação.
