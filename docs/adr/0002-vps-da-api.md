# VPS da API, do worker e do gosom

A API e o worker cabem em qualquer máquina pequena. O gosom não: ele abre um Chromium e pede 1 a 2 GB de RAM, então não entra em hospedagem gratuita. O Postgres e o login ficam no Supabase. OSRM, Nominatim e Overpass são outra máquina, a de [infra/osm/README.md](../../infra/osm/README.md), e não dividem estes 4 GB.

## Decisão

**Hetzner CPX21** (3 vCPU AMD dedicadas, 4 GB de RAM, 80 GB de disco), Ubuntu 24.04, em Falkenstein ou Helsinki. É a menor máquina com vCPU dedicada e 4 GB. A meta da issue é 2 vCPU e 4 GB; a vCPU a mais é o que o Chromium usa sem brigar com a API.

A região não é o Brasil. A ida e volta até a Europa fica em torno de 200 ms. A busca leva minutos e roda no worker; o que o celular espera na hora (swipe, lista, roteiro) aguenta essa latência. Se um dia ela incomodar, a troca é um droplet de 2 vCPU e 4 GB na DigitalOcean em São Paulo, sem mudar o compose.

## Custo mensal

Preços de tabela de terceiros, em novembro de 2026. Mudam. Confira no site antes de contratar.

| Opção | Máquina | Preço aproximado | Por que sim ou não |
| --- | --- | --- | --- |
| Hetzner CPX21 | 3 vCPU dedicadas, 4 GB, 80 GB | €8 a €12 | A escolha. CPU estável para o Chromium e cabe no teto de RAM abaixo |
| Hetzner CX22 | 2 vCPU compartilhadas, 4 GB, 40 GB | €4 a €6 | Mais barata, mas a CPU some quando o vizinho aperta e o gosom estoura o tempo |
| DigitalOcean, São Paulo | 2 vCPU, 4 GB | US$ 24 | Cabe e fica perto de quem usa o app. Custa cerca do triplo |
| Oracle Cloud, São Paulo | Ampere, até 4 OCPU e 24 GB no always free | R$ 0 se houver vaga | A vaga gratuita esgota. Não dá para marcar o beta em cima dela |
| Contabo Cloud VPS | 4 vCPU compartilhadas, 6 a 8 GB | €5 a €7 | RAM de sobra, CPU e disco irregulares. O job de 3 minutos do gosom varia demais |

Fora da tabela: o plano pago do Supabase (o gratuito pausa o projeto) e, no dia em que o gosom sair, a Places API, que cobra por chamada e não por máquina.

## RAM na máquina de 4 GB

| Peça | Teto no compose |
| --- | --- |
| Sistema | 400 a 600 MB, sem teto no Docker |
| Caddy | 128 MB |
| API | 512 MB |
| Worker | 512 MB |
| gosom | 2 GB (`-c 2`, no máximo dois navegadores) |
| Folga | cerca de 400 a 700 MB |

A soma dos tetos passa de 4 GB de propósito: eles não enchem ao mesmo tempo. O gosom é o único que chega perto do teto, e só durante a busca. Sem o perfil `gosom`, sobram mais de 2 GB.

## Consequências

- Sobe com `docker compose -f docker-compose.prod.yml`. O `docker-compose.yml` da raiz continua sendo o de desenvolvimento. O passo a passo, os segredos e a troca pela Places API estão em [docs/deploy.md](../deploy.md).
- `restart: unless-stopped` em todos os serviços. Reiniciar a VPS traz a API de volta.
- O gosom não publica porta. Só o Caddy escuta 80 e 443.
- `PV_USER_AGENT` e `PV_ACME_EMAIL` são um contato real, só no `.env` da VPS.
