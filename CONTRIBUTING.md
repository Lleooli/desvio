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
- `PV_DATABASE_URL`, `SUPABASE_URL` e `SUPABASE_ANON_KEY` do projeto no Supabase (peça a quem cuida do projeto). A fila, as decisões e o cache ficam lá.

A API, o worker e o `cli.py` leem esse arquivo sozinhos, e o docker compose também. Não precisa exportar nada.

**Coletor:**

```bash
cd services/coletor
python -m venv .venv
source .venv/bin/activate        # no Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
docker compose --profile teste up -d banco-teste     # Postgres vazio para os testes
export PV_TEST_DATABASE_URL=postgresql://postgres:teste@localhost:54329/desvio_teste
python -m pytest -q              # tudo verde antes de começar
```

Sem `PV_TEST_DATABASE_URL`, os testes que precisam de banco são pulados (no CI eles sempre rodam). Os testes apagam e recriam o schema desse banco, então nunca aponte para o Supabase.

**Banco (Supabase):**

O projeto se chama `desvio`, fica em São Paulo (`sa-east-1`) e está no plano gratuito. `SUPABASE_URL` é `https://bqtflbmbnkrtjvxsartx.supabase.co`, e a chave pública (`SUPABASE_ANON_KEY`) está em Project Settings > API Keys. A `PV_DATABASE_URL` sai de Connect > Session pooler, com a senha do banco: peça a quem administra o projeto e nunca a coloque no Git. Projeto gratuito parado por 7 dias é pausado; para reativar, clique em Restore no painel.

As migrações ficam em `infra/supabase/migrations/`, uma por arquivo, em ordem pelo nome. Para aplicar no projeto do Supabase, com a [Supabase CLI](https://supabase.com/docs/guides/cli):

```bash
supabase db push --workdir infra --db-url "$PV_DATABASE_URL"
```

Ou, sem a CLI, rode cada arquivo novo em ordem com `psql "$PV_DATABASE_URL" -f <arquivo>`. Mudou o schema? Crie um arquivo novo (`AAAAMMDDhhmmss_o_que_mudou.sql`); nunca edite uma migração que já foi aplicada. `infra/supabase/local/00_auth.sql` imita o `auth` do Supabase para o Postgres de teste e não vai para o Supabase.

Para rodar a API e o worker juntos com o Google Maps, use `docker compose up --build` na raiz. Com o `.env` de exemplo (`COMPOSE_PROFILES=gosom`), ele sobe também o gosom, o raspador usado em desenvolvimento. Para testar com a Places API oficial, ponha `PV_GOOGLE_PLACES_KEY` no `.env` (a fonte passa a ser `places`) e, se não quiser o gosom, apague `COMPOSE_PROFILES`; é assim em produção. Sem Docker, rode `uvicorn app.main:app --reload` e `python -m app.worker` em dois terminais.

No desenvolvimento, o coletor usa os servidores públicos de OSRM, Nominatim e Overpass. Os servidores próprios, com o extrato do Brasil, rodam numa VPS e não cabem num notebook comum: veja [infra/osm/README.md](infra/osm/README.md).

**App:**

```bash
cd apps/mobile
npm install
npx expo start
```

O Expo Go da loja só abre a versão de SDK dele; se o projeto estiver em outra, aparece "Something went wrong". Para não depender disso, use o development build (app "Desvio" separado, que também recebe push):

- **Pelo EAS** (precisa de convite no projeto [@lleooliv/desvio](https://expo.dev/accounts/lleooliv/projects/desvio)): `npx eas-cli build --profile development --platform android`, instale o APK pelo link e rode `npx expo start --dev-client`.
- **Local, com o celular no USB** (Android Studio instalado): `npx expo run:android`. Se o app não achar o Metro, rode `adb reverse tcp:8081 tcp:8081`.

O perfil `preview` do `eas.json` gera o APK do beta fechado (distribuição interna, por link). A pasta `android/` que o build local cria não vai para o Git.

**Beta e loja.** No GitHub, em Settings > Secrets and variables > Actions, crie `EXPO_TOKEN` (expo.dev > Account settings > Access tokens, do dono do projeto `lleooliv/desvio`). O workflow **eas** não roda nos pull requests.

- **Testadores (beta):** Actions > eas > Run workflow, perfil `preview`, plataforma `android`. O APK sai por link na página do build no Expo. Quem tem convite no projeto instala por esse link.
- **Loja:** uma tag `v*` (por exemplo `v0.1.0`) dispara o perfil `production` para Android e iOS. O mesmo workflow manual aceita `production`. Com as credenciais da Apple e do Google já no EAS, `npx eas-cli submit --profile production --platform ios` manda para o TestFlight e `--platform android` para a trilha interna do Play. `eas.json` já tem `submit.production`.

**Login (Supabase Auth):** copie `apps/mobile/.env.example` para `apps/mobile/.env` e preencha `EXPO_PUBLIC_SUPABASE_URL` e `EXPO_PUBLIC_SUPABASE_ANON_KEY`. No painel do Supabase, em Authentication:

- **URL Configuration > Redirect URLs:** `desvio://**` (development build e lojas) e `exp://**` (Expo Go). É para lá que voltam o Google, a Apple no navegador e o link por e-mail.
- **Sign In / Providers > Email:** link por e-mail ligado, com validade (Email OTP Expiration) de `900` segundos, os 15 minutos da HU01.
- **Sign In / Providers > Google e Apple:** ligados, com as credenciais de cada um. No iOS a Apple entra pelo app nativo (`signInWithIdToken`); ponha o bundle id `app.desvio` em Client IDs da Apple.

O primeiro login de uma conta leva à triagem e marca `ja_entrou` no metadata da conta; os seguintes, em qualquer celular, levam a Minhas viagens.

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
