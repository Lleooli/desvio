# Servidores próprios de OSRM, Nominatim e Overpass

Os servidores públicos do OpenStreetMap são para uso leve: o Nominatim aceita 1 requisição por segundo, o Overpass devolve 429 quando a fila enche e o OSRM de demonstração não tem garantia nenhuma. Esta pasta sobe os três numa VPS com o extrato do Brasil da [Geofabrik](https://download.geofabrik.de/south-america/brazil.html) (issue #37).

| Serviço | O que o coletor usa | Imagem (fixada) | Porta no host | Variável do coletor |
| --- | --- | --- | --- | --- |
| OSRM, perfil carro | rota de carro e de moto (`app/geo.py`) | `ghcr.io/project-osrm/osrm-backend:v26.10.0-debian` | 5000 | `PV_OSRM_URL=http://<host>:5000` |
| OSRM, perfil bicicleta | rota de bicicleta | a mesma | 5001 | `PV_OSRM_BIKE_URL=http://<host>:5001` |
| Nominatim | geocodificação e cidade de um ponto | `mediagis/nominatim:5.3.3-2026-10-26T11-48` | 8088 | `PV_NOMINATIM_URL=http://<host>:8088` |
| Overpass | cidades e lugares no caminho (`app/osm.py`) | `wiktorn/overpass-api:v0.7.62.11` | 12345 | `PV_OVERPASS_URL=http://<host>:12345/api/interpreter` |

Por que dois OSRM: cada processo do OSRM serve um único perfil, escolhido no pré-processamento. O `app/geo.py` já manda carro e moto para `PV_OSRM_URL` (perfil `driving`) e bicicleta para `PV_OSRM_BIKE_URL` (perfil `bike`). Não existe perfil de moto no OSRM; a moto usa a rota de carro, como no servidor público.

As imagens foram conferidas no registro em 13/11/2026. O OSRM saiu do Docker Hub (`osrm/osrm-backend` parou na v5.25, de 2021) e agora publica no GitHub Container Registry. Para trocar de versão, mude a tag no `compose.yml` e rode a atualização do OSRM de novo: os arquivos pré-processados têm de sair da mesma versão que vai servi-los, e por isso `preparar-osrm.sh` lê a imagem do próprio `compose.yml`.

## Dimensionamento

O extrato do Brasil tem **2,0 GB** em PBF (13/11/2026). Nenhum dos três projetos publica números para o Brasil: os valores abaixo saem dos números oficiais para o planeta inteiro, escalados pelo tamanho do PBF (o Brasil é uns 3% do planeta), com folga. **São estimativas.** Na primeira subida, registre os números reais na tabela "Medido" (os scripts já imprimem tempo e espaço em disco).

| Serviço | RAM no ar | Pico de RAM na preparação | Disco | Tempo de preparação (8 vCPU, NVMe) |
| --- | --- | --- | --- | --- |
| OSRM carro (MLD) | 4 a 5 GB | 12 a 15 GB (`osrm-extract`) | 10 GB por versão | 30 a 60 min |
| OSRM bicicleta (MLD) | 5 a 6 GB | 14 a 17 GB | 12 GB por versão | 40 a 80 min |
| Nominatim (estilo `address`, com atualização) | 4 a 8 GB (cache do Postgres) | 8 a 16 GB | 30 a 40 GB | 2 a 5 h |
| Overpass (sem metadados, sem áreas) | 2 a 4 GB | 2 a 4 GB | 10 a 15 GB, mais 4 GB temporários | 1 a 2 h (conversão para `.osm.bz2` + importação) |
| PBF do Brasil | | | 2 GB, mais 2 GB durante o download | 5 a 15 min de download |

**Total no ar:** uns 16 a 23 GB de RAM. Na atualização mensal o OSRM é refeito enquanto a versão antiga continua no ar, então o pico soma mais uns 15 GB. **Disco:** uns 110 GB com duas versões de cada perfil do OSRM.

De onde vêm os números:

- **OSRM:** [Disk and Memory Requirements](https://github.com/Project-OSRM/osrm-backend/wiki/Disk-and-Memory-Requirements) (v5.26, planeta de 61 GiB, nov/2021): perfil de carro com pico de 415 GiB no extract, 220 GiB no partition e 174 GiB no customize (MLD), uns 123 GiB de RAM para servir e uns 300 GB de arquivos gerados. O perfil de bicicleta "fica entre" o de carro e o de pedestre (476 GiB). Escalado para 2 GB de PBF: uns 3,3%. A página também recomenda swap, para o sistema não matar o pré-processamento por falta de memória.
- **Nominatim:** [Installation](https://nominatim.org/release-docs/latest/admin/Installation/): mínimo de 2 GB de RAM; planeta pede 128 GB de RAM, 1 TB de disco NVMe e uns 2,5 dias de importação. O estilo `address` (o padrão aqui) importa só o necessário para endereços e cidades, que é o que `app/geo.py` consulta; `full` inclui pontos de interesse e ocupa mais.
- **Overpass:** [Overpass API/Installation](https://wiki.openstreetmap.org/wiki/Overpass_API/Installation): planeta com metadados e histórico ocupa 200 a 300 GB comprimido; um extrato importa em menos de 1 hora; 1 GB de RAM basta para um extrato pequeno, e o servidor público tem 32 GB para atender o mundo. Aqui não há metadados (o PBF público da Geofabrik não tem), nem histórico, nem áreas (`app/osm.py` só usa `around:`), o que reduz bastante o disco.

### VPS recomendada

**12 vCPU, 48 GB de RAM e 250 GB de NVMe**, Ubuntu 24.04 com Docker. Cabe tudo no ar com o pico da atualização mensal e sobra para o coletor e o gosom na mesma máquina. Com 32 GB funciona, mas ponha 16 GB de swap para o `osrm-extract` não ser morto na atualização.

Custo mensal de referência (preços de terceiros, que mudam; confira no site antes de contratar):

| Opção | Configuração | Preço aproximado |
| --- | --- | --- |
| Contabo Cloud VPS 40 | 12 vCPU, 48 GB, 250 GB NVMe | uns €25/mês ([preços 2026](https://onedollarvps.com/br/pricing/contabo-pricing)); CPU compartilhada |
| Contabo Cloud VPS 30 | 8 vCPU, 24 GB, 200 GB NVMe | uns €14/mês; só com swap e sem o gosom junto |
| Hetzner CCX33 | 8 vCPU dedicadas, 32 GB, 240 GB | uns €138/mês depois do reajuste de junho/2026 ([Northflank](https://northflank.com/blog/hetzner-cloud-server-price-increases)) |

A região da VPS pesa pouco: quem fala com esses servidores é o coletor, não o celular. O ideal é o coletor na mesma VPS ou na mesma rede.

### Medido

Preencha na primeira subida de verdade (o critério de aceite da issue #37 pede o dimensionamento registrado):

| Serviço | RAM no ar | Pico de RAM | Disco | Tempo |
| --- | --- | --- | --- | --- |
| OSRM carro | | | | |
| OSRM bicicleta | | | | |
| Nominatim | | | | |
| Overpass | | | | |

Para medir: `docker stats --no-stream` (RAM no ar), a linha `RAM: peak bytes used` do log do OSRM (pico), `du -sh dados/osrm/*/*` e `docker system df -v` (disco).

## Subir na VPS

Tudo a partir de `infra/osm`. Precisa de Docker com o plugin `compose`, `curl`, `md5sum` e `flock` (já vêm no Ubuntu).

```bash
git clone https://github.com/Lleooli/desvio.git /opt/desvio
cd /opt/desvio/infra/osm
cp .env.example .env
# edite .env: NOMINATIM_SENHA (obrigatória); OSM_DADOS se o disco grande estiver em outro lugar

# 1. Extrato do Brasil (2 GB, confere o MD5 da Geofabrik)
./baixar-pbf.sh

# 2. OSRM: pré-processa os dois perfis (um de cada vez, por causa do pico de RAM)
./preparar-osrm.sh carro
./preparar-osrm.sh bicicleta

# 3. Sobe tudo. O Nominatim e o Overpass importam na primeira subida (horas); acompanhe:
docker compose up -d
docker compose logs -f nominatim overpass
docker compose ps        # espere os quatro como "healthy"

# 4. Confere os quatro, com a rota do critério de aceite
./validar.sh
```

O OSRM fica no ar em minutos. O Nominatim e o Overpass ficam "starting" até terminar a importação; o healthcheck deles só conta falha depois de 12 h (Nominatim) e 48 h (Overpass, padrão da imagem).

### Apontar o coletor

No `.env` da raiz (o do coletor):

```bash
PV_OSRM_URL=http://<host>:5000
PV_OSRM_BIKE_URL=http://<host>:5001
PV_NOMINATIM_URL=http://<host>:8088
PV_OVERPASS_URL=http://<host>:12345/api/interpreter
PV_NOMINATIM_INTERVALO=0     # servidor próprio: sem a espera de 1,1 s entre chamadas
```

Sem essas variáveis o coletor continua nos servidores públicos, e `PV_NOMINATIM_INTERVALO` fica em 1,1 s. Com o Nominatim próprio, o `PV_USER_AGENT` com e-mail real deixa de ser exigência (continua valendo para o Wikipedia e para o Overpass público, se algum ficar público).

Onde fica o `<host>`:

- **Coletor na mesma VPS, fora do Docker:** `127.0.0.1` (o padrão do `OSM_BIND`).
- **Coletor na mesma VPS, pelo `docker-compose.yml` da raiz:** dentro do container, `127.0.0.1` é o próprio container. Ponha `OSM_BIND` com o IP do host na bridge do Docker (`172.17.0.1`, veja `ip addr show docker0`) e use esse IP nas URLs.
- **Coletor em outra máquina:** `OSM_BIND` com o IP privado (VPN ou rede interna). Se for `0.0.0.0`, feche as portas no firewall e libere só o IP do coletor:

  ```bash
  sudo ufw allow from <ip-do-coletor> to any port 5000,5001,8088,12345 proto tcp
  ```

  Atenção: o Docker publica portas por fora do `ufw`. Com `0.0.0.0`, use o firewall do provedor ou a cadeia `DOCKER-USER` do iptables. Esses servidores não têm autenticação nem limite de uso; não os deixe abertos na internet.

## Validar o critério de aceite

Rota Alegrete, RS → Vitória da Conquista, BA no OSRM próprio. O OSRM recebe **longitude,latitude**:

```bash
curl -s "http://127.0.0.1:5000/route/v1/driving/-55.7919,-29.7831;-40.8442,-14.8615?overview=false"
```

A resposta tem de ter `"code":"Ok"`, e `routes[0].distance` em metros. No OSRM público (13/11/2026) deu 2.819 km e 37,9 h de carro; de bicicleta, no servidor da FOSSGIS, 3.334 km:

```bash
curl -s "http://127.0.0.1:5001/route/v1/bike/-55.7919,-29.7831;-40.8442,-14.8615?overview=false"
```

O `./validar.sh` faz essas duas chamadas e falha se a distância vier abaixo de 2.000 km (sinal de extrato errado: o OSRM "encaixa" os pontos no que tiver). Ele também testa o Nominatim (`Alegrete, RS`) e o Overpass (cidades num raio de 30 km de Alegrete, a mesma consulta de `app/osm.py`). Para testar a partir da máquina do coletor: `OSM_HOST=<host> ./validar.sh`.

Por último, de ponta a ponta, com o `.env` do coletor apontando para os servidores próprios:

```bash
cd services/coletor
python cli.py "Alegrete, RS" "Vitória da Conquista, BA" --veiculo moto
```

## Atualização mensal

`./atualizar.sh` faz tudo e pode rodar pelo timer do systemd (abaixo) ou pelo cron:

1. Baixa o extrato novo (`baixar-pbf.sh`; se o MD5 não mudou, não baixa).
2. Para cada perfil do OSRM, pré-processa numa pasta nova, `dados/osrm/<perfil>/AAAAMMDD/`, **com a versão antiga no ar**.
3. Troca o link `dados/osrm/<perfil>/atual` para a pasta nova (troca atômica, `mv -T`) e reinicia só aquele container. A queda é o tempo de o `osrm-routed` carregar os arquivos, alguns segundos, e não as horas do pré-processamento. Nesse intervalo o coletor ainda tem o cache de rotas de 30 dias.
4. Espera o healthcheck. Se o container não ficar saudável em 10 minutos, o link volta para a versão anterior e o script sai com erro.
5. Apaga as versões antigas, guardando a atual e mais `OSRM_MANTER` (padrão 1) para voltar atrás.
6. Registra a data dos dados do Nominatim e do Overpass e roda o `validar.sh`.

**Nominatim e Overpass não são refeitos todo mês.** Os dois aplicam sozinhos as diferenças diárias da Geofabrik (`REPLICATION_URL` com `UPDATE_MODE=continuous` e `OVERPASS_DIFF_URL`, no `compose.yml`), sem tirar nada do ar. Reimportar só em caso de problema ou de mudança de estilo do Nominatim:

```bash
docker compose stop nominatim && docker compose rm -f nominatim
docker volume rm osm_nominatim-banco        # o prefixo é o nome do projeto (a pasta): confira com docker volume ls
docker compose up -d nominatim              # importa de novo a partir do PBF em dados/pbf
```

Para voltar o OSRM manualmente para a versão anterior:

```bash
ls dados/osrm/carro/                        # versões guardadas
ln -sfn 20261103 dados/osrm/carro/atual
docker compose restart osrm-carro
```

### Agendar com o systemd (recomendado)

O repositório precisa estar em `/opt/desvio` (ou ajuste os caminhos no `.service`):

```bash
sudo cp systemd/desvio-osm-atualizar.service systemd/desvio-osm-atualizar.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now desvio-osm-atualizar.timer
systemctl list-timers desvio-osm-atualizar.timer      # próxima execução: dia 3, de madrugada
journalctl -u desvio-osm-atualizar.service            # log da última
sudo systemctl start desvio-osm-atualizar.service     # rodar agora
```

### Ou com o cron

```cron
# dia 3 de cada mês, 03:30
30 3 3 * * /opt/desvio/infra/osm/atualizar.sh >> /var/log/desvio-osm.log 2>&1
```

## Arquivos

| Arquivo | O que faz |
| --- | --- |
| `compose.yml` | os quatro serviços, com volumes, healthcheck e `restart: unless-stopped` |
| `.env.example` | senha do Nominatim, pasta de dados, interface das portas, threads |
| `comum.sh` | configuração lida pelos outros scripts |
| `baixar-pbf.sh` | baixa e confere o extrato do Brasil |
| `preparar-osrm.sh` | `osrm-extract`, `osrm-partition` e `osrm-customize` (MLD) de um perfil |
| `atualizar.sh` | rotina mensal: extrato novo, OSRM refeito e trocado, validação |
| `validar.sh` | testa os quatro servidores; inclui a rota do critério de aceite |
| `systemd/` | serviço e timer da rotina mensal |

A pasta `dados/` (PBF e arquivos do OSRM) não vai para o Git.

## O que já foi testado e o que falta

Testado nesta máquina, com o extrato de Mônaco (700 KB) no lugar do Brasil: `baixar-pbf.sh` (download, MD5 e "já está atualizado"), `preparar-osrm.sh` nos dois perfis com a imagem fixada, os dois containers do OSRM ficando "healthy" pelo healthcheck do `compose.yml` e respondendo a `/route`, e o `validar.sh` recusando a rota curta demais. O `compose.yml` passa no `docker compose config`.

Falta, porque precisa da VPS: importar o Brasil de verdade, medir RAM, disco e tempo (tabela "Medido"), rodar o `curl` do critério de aceite no servidor próprio e uma rodada completa do `atualizar.sh`. O Nominatim e o Overpass não foram subidos aqui (a importação passa da RAM e do disco desta máquina).
