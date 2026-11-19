# Coletor do Desvio

Backend do app. Você informa a viagem, ele devolve **cards** (foto, nota,
Instagram, km na rota) para a pessoa aceitar ou recusar. Depois monta a ordem
de visita do que foi aceito.

A coleta leva minutos, então roda num **worker** separado da API: a API cria um
job na fila (`app/fila.py`) e o worker (`app/worker.py`) processa. A IA
(`app/ia.py`, Groq gratuito) faz triagem, ranqueamento e roteiro e tem plano B
sem IA. A coleta é gratuita e sem chave; só a IA usa `GROQ_API_KEY`.

| Peça | Projeto | Para quê |
|---|---|---|
| Rota (carro e moto) | OSRM (servidor público) | trajeto, distância, duração |
| Rota de bicicleta | OSRM, perfil bike da FOSSGIS (`PV_OSRM_BIKE_URL`) | trajeto que evita rodovias, horas de pedal |
| Autocompletar de cidade com UF | Lista de municípios do IBGE (Fonte: IBGE; via [kelvins/municipios-brasileiros](https://github.com/kelvins/municipios-brasileiros), MIT) | busca local, sem gastar o Nominatim |
| Endereço → coordenada | Nominatim / OpenStreetMap | geocodificação |
| Cidades, postos, atrações | Overpass API / OpenStreetMap | base estável e legal de usar |
| Fotos e notas do Google Maps (produção) | [Places API (New)](https://developers.google.com/maps/documentation/places/web-service/op-overview) oficial (`PV_GOOGLE_PLACES_KEY`) | Text Search e Place Photos, pagos por chamada |
| Fotos e notas do Google Maps (desenvolvimento) | [gosom/google-maps-scraper](https://github.com/gosom/google-maps-scraper) (MIT, Docker) | raspagem do Maps |
| "Google normal" | [deedy5/ddgs](https://github.com/deedy5/ddgs) (MIT) | metabusca, achar Instagram |
| Fotos de atrações | Wikipedia REST API | quando o OSM aponta o artigo |

## Rodando

**Só OpenStreetMap (mais rápido para começar):**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python cli.py "Alegrete, RS" "Vitória da Conquista, BA" --veiculo bicicleta --intervalo 40
```

**Com Google Maps pela Places API (produção):**

```bash
export PV_GOOGLE_PLACES_KEY=...      # ou no .env; a fonte passa a ser "places"
python cli.py "Alegrete, RS" "Vitória da Conquista, BA" --google
```

Uma Text Search por parada e categoria, até 5 ao mesmo tempo; a viagem toda
sai em segundos. O field mask (`gmaps.CAMPOS_PLACES`) pede só o que vira card
e cai no SKU **Text Search Enterprise** (nota, avaliações, site, telefone,
horário e preço são Enterprise; o resto é Pro). `descricao` e `sobre` ficam
vazios nessa fonte, porque os campos que os preenchem (`editorialSummary`,
`allowsDogs`…) são Atmosphere e encareceriam todas as buscas. Não precisa de
Place Details.

Se uma busca falha ou passa de 15 s, ela fica de fora (e não entra no cache);
se todas falham, a viagem sai só com OpenStreetMap e um aviso, como com o gosom.

**Fotos e atribuição:** o card não leva a URL do Google, que exigiria a chave.
`foto` e `fotos` apontam para `GET /fotos/places/.../photos/...?l=800&ass=...`
da nossa API, uma URL assinada (HMAC) pelo coletor. O endpoint confere a
assinatura, pede ao Google a URL da imagem (`skipHttpRedirect=true`) e
redireciona (302). Não pede token, porque o `<Image>` do app não manda cabeçalho,
mas só aceita fotos que o coletor assinou, então não vira um proxy aberto. Com
`PV_API_URL_PUBLICA`, a URL sai absoluta; sem ela, o app junta com a base da API.
`fotos_autores` traz, na mesma ordem de `fotos`, os autores de cada foto
(`[{nome, uri, avatar, link_foto}]`): pelos termos do Google, o app mostra o
nome (com link para `uri`) e o avatar junto da foto, dá acesso à foto no Google
Maps (`link_foto`) e marca os dados do Google com "Google Maps". Numa miniatura
dá para omitir o autor, desde que a foto ampliada o mostre.

**Com Google Maps pelo gosom (só desenvolvimento):**

```bash
docker run -d -p 8080:8080 -v "$PWD/gmapsdata:/gmapsdata" \
  -e DISABLE_TELEMETRY=1 gosom/google-maps-scraper -data-folder /gmapsdata

python cli.py "Alegrete, RS" "Vitória da Conquista, BA" --google
```

O gosom leva no mínimo uns 3 minutos por job. Por isso o código manda todas
as buscas da viagem num job só.

Sem `PV_GOOGLE_PLACES_KEY`, a fonte é o gosom. Com a chave e o gosom ao
mesmo tempo, `PV_GOOGLE_FONTE=gosom` força o raspador.

**Tudo junto (API + worker):**

```bash
docker compose up --build                  # com COMPOSE_PROFILES=gosom no .env (o padrão do exemplo), sobe o gosom
docker compose --profile gosom up --build  # o mesmo, explícito
# produção: .env sem COMPOSE_PROFILES e com PV_GOOGLE_PLACES_KEY; o mesmo `docker compose up --build`
# sobe só a API e o worker
# abre http://localhost:8000/docs
```

## Endpoints

Todas as rotas, menos `/docs` e `/fotos`, exigem o token do Supabase Auth no cabeçalho
`Authorization: Bearer <access_token>` (sem token ou com token vencido: 401).
O usuário sai do token, nunca do corpo; o job ou a viagem de outra pessoa responde 404.

| Método | Rota | O que faz |
|---|---|---|
| POST | `/viagem` | origem, destino, veículo (`carro`, `moto` ou `bicicleta`) e intervalo entre paradas, escolhido pela pessoa → `202 {job_id, viagem_id}`. A viagem já fica guardada com status `buscando` |
| GET | `/viagens` | `{viagens: [...]}`, as da pessoa, a mais recente primeiro: `id`, `origem`, `destino`, `veiculo`, `status` (`buscando`, `pronta` ou `falhou`), `job_id`, `criado_em` e `progresso: {decididos, total}` (cards da viagem já avaliados pela pessoa) |
| GET | `/viagens/{id}` | a viagem com `polilinha` e `paradas` (`ordem` a partir de 0, `nome`, `uf`, `tipo`, `km_na_rota`, `cards` e `progresso: {aceitos, total}`, os cards com Bora ou Favorito sobre todos os da parada); os cards já avaliados somem e o resto vem ordenado pelo gosto. Viagem de outra pessoa: 404 |
| GET | `/jobs/{id}` | `status` (`pendente`, `rodando`, `pronto`, `falhou`); quando pronto, `resultado` traz as paradas com cards. Enquanto roda, `progresso` traz `{etapa, titulo, detalhe, percentual}`, com as etapas `rota`, `cidades`, `lugares` e `instagram`, nessa ordem, e os textos da tela Carregando. Com o Google ligado, `parcial` traz as paradas só com cards do OpenStreetMap antes do gosom; o `resultado` final contém esses cards, com os mesmos ids, menos os que a pessoa já deslizou (Bora ou Passo) enquanto esperava |
| GET | `/eu/exportar` | LGPD: JSON com `usuario` (email, provedor, perfil_gosto, tema, criado_em), `perfil`, `viagens` (com paradas, cards e roteiro) e `decisoes`; só os dados de quem pede |
| DELETE | `/eu` | LGPD: corpo `{"confirmar": "APAGAR"}` (sem isso, 422). Apaga na hora a linha em `usuario` (e em cascata viagens, paradas, decisões e roteiros) e os jobs, e pede ao Supabase Auth que apague a conta. Responde `{dados: "apagados", conta: "apagada" ou "pendente"}`; pendente é quando o Supabase falhou, e o worker tenta de novo (até 15 dias, veja [docs/privacidade.md](../../docs/privacidade.md)) |
| POST | `/swipe` | grava `{card, gostou}` em `lugar` e `decisao` |
| GET | `/perfil` | taxa de aceite por categoria, tipo e faixa de preço |
| POST | `/triagem` | `{respostas: [{pergunta, resposta}]}` → próxima pergunta ou `fim` com o resumo do gosto |
| POST | `/cards/ranquear` | `{cards, resumo}` → os mesmos cards, os 30 primeiros reordenados pela IA |
| GET | `/fotos/{nome}?l=&ass=` | sem token: foto da Places API por URL assinada pelo coletor → `302` para a imagem no Google; assinatura errada ou foto vencida: `404` |
| POST | `/roteiro` | `{itens, explicacoes, fonte}`: os aceitos pelo km da estrada; com `usar_ia: true` e `contexto`, a IA ajusta ao horário e explica cada parada |

Em `/viagem`, os cards que a pessoa do token já avaliou somem e os novos vêm
ordenados pelo gosto aprendido nos swipes anteriores.

Quando o job termina, o worker grava a viagem no banco (`viagem`, `parada`,
`parada_lugar` e `lugar`, em `app/viagens.py`) e ela passa a `pronta`. A
coleta atualiza o card em `lugar` (é dado do servidor); o `/swipe` nunca
reescreve um lugar que já existe.

Para apagar a conta no Supabase Auth, a API usa `SUPABASE_SERVICE_ROLE_KEY`
(só no servidor). Sem ela, ou com o Supabase fora do ar, os dados somem do
mesmo jeito e a conta fica em `exclusao_pendente` até o worker conseguir
(`PV_EXCLUSAO_INTERVALO_MIN`, padrão 10). Enquanto isso, o token antigo responde 401.

A API não coleta nada sozinha: rode o worker junto (`python -m app.worker`, ou
`docker compose up`). Os endpoints de IA respondem mesmo sem `GROQ_API_KEY`:
`/triagem` e `/roteiro` trazem `"fonte": "fixa"` ou `"geometria"` no
lugar de `"ia"`, e `/cards/ranquear` devolve os cards na ordem em que vieram.

A API, o worker e o `cli.py` leem sozinhos o `.env` da raiz do repositório
(`app/ambiente.py`). Variáveis que já existem no ambiente têm prioridade.

Exemplo de card:

```json
{
  "id": "gmaps:ChIJ...", "fonte": "google_maps",
  "nome": "Churrascaria X", "categoria": "restaurante", "tipo": "Churrascaria",
  "cidade": "Lages", "uf": "SC", "lat": -27.81, "lon": -50.32,
  "foto": "https://lh5.googleusercontent.com/...", "fotos": ["..."],
  "nota": 4.7, "avaliacoes": 1834, "faixa_preco": "R$ 50–100",
  "instagram": "https://instagram.com/churrascariax", "instagram_origem": "site",
  "km_na_rota": 512.3, "horas_desde_saida": 6.8,
  "link_maps": "https://www.google.com/maps/place/..."
}
```

`instagram_origem` = `site` (veio do site ou cadastro, confiável) ou `busca`
(achado por busca web; mostre como "provável").

## Como as paradas são escolhidas

1. Calcula a rota e marca um ponto a cada `intervalo_km` (padrão 200 km, umas 2,5 h).
2. Em volta de cada ponto, escolhe a cidade que equilibra tamanho (população) e
   distância da estrada.
3. Busca atrações, restaurantes e postos num raio de 8 km da cidade (15 km no destino).
4. Prioriza pelo Google (nota ajustada pelo número de avaliações, para 4,9 com
   6 avaliações não ganhar de 4,6 com 2 mil) e completa com o OpenStreetMap.

## Avisos importantes

- **Termos de uso:** raspar o Google Maps e a busca do Google viola os termos
  deles. O gosom serve para protótipo; em produto público, use a Places API
  (`PV_GOOGLE_PLACES_KEY`). O resto do código não muda.
- **Bloqueio:** em volume alto o Google bloqueia o IP. Mantenha `-c` baixo e
  use cache. O gosom aceita proxies.
- **Servidores públicos (OSRM, Nominatim, Overpass):** são para uso leve. Em
  produção, suba os seus via Docker. As URLs são configuráveis por
  `PV_OSRM_URL`, `PV_NOMINATIM_URL` e `PV_OVERPASS_URL`.
- Troque o e-mail em `PV_USER_AGENT`; o Nominatim exige identificação.

## Próximos passos sugeridos

- **Push:** o worker avisa o app pelo Expo Push quando o job termina.
