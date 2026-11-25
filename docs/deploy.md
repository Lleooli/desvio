# Deploy da API na VPS

Sobe a API, o worker e o gosom com HTTPS. A escolha da máquina e a conta de RAM estão no [ADR 0002](adr/0002-vps-da-api.md). Nada desta página é segredo: domínio, IP, chave e e-mail de verdade ficam fora do Git.

## Uma vez na VPS

Ubuntu 24.04 com Docker e o plugin `compose`. O firewall só deixa 22, 80 e 443. O DNS do domínio aponta para a VPS antes do primeiro `up`, senão o Caddy não emite o certificado.

```bash
git clone git@github.com:Lleooli/desvio.git /srv/desvio
cd /srv/desvio
cp .env.prod.example .env
# edite o .env: PV_USER_AGENT e PV_ACME_EMAIL com um e-mail real,
# PV_DOMINIO, PV_DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, GROQ_API_KEY
docker compose -f docker-compose.prod.yml up -d --build
```

O clone em `/srv/desvio` é o caminho que o workflow usa. A chave SSH desse `git clone` é um deploy key só de leitura, no repositório, e não é a mesma chave com que o GitHub Actions entra na VPS.

Confira `https://<PV_DOMINIO>/docs`. O gosom não tem porta aberta: a API fala com ele em `http://gosom:8080`.

## Segredos no GitHub

Em Settings > Secrets and variables > Actions, no repositório:

| Segredo | O que é |
| --- | --- |
| `VPS_HOST` | IP ou nome da VPS |
| `VPS_USER` | Usuário do SSH, com permissão para o Docker |
| `VPS_SSH_KEY` | Chave privada. A pública correspondente fica em `authorized_keys` na VPS |
| `VPS_PORT` | Opcional. Sem ele, a porta é 22 |

O workflow [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml) roda em todo push na `main`. Ele entra por SSH, faz `git pull --ff-only` e `docker compose -f docker-compose.prod.yml pull` e `up -d --build --remove-orphans`. Não roda em pull request e não precisa desses segredos para o CI de testes.

## Trocar o gosom pela Places API

Quando o beta for para a Places API oficial, no `.env` da VPS:

1. Apague `COMPOSE_PROFILES=gosom`.
2. Ponha `PV_GOOGLE_PLACES_KEY` com a chave restrita ao IP da VPS e só à Places API (New).
3. Ponha `PV_GOOGLE_FONTE=places` e `PV_API_URL_PUBLICA=https://<PV_DOMINIO>`.

Depois:

```bash
cd /srv/desvio
docker compose -f docker-compose.prod.yml up -d --remove-orphans
```

O `--remove-orphans` tira o container do gosom. A API e o worker continuam os mesmos. Sem `COMPOSE_PROFILES` e com a chave, `gmaps.fonte()` escolhe `places` e o gosom deixa de ser chamado.
