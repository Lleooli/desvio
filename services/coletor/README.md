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
| Rota de carro | OSRM (servidor público) | trajeto, distância, duração |
| Endereço → coordenada | Nominatim / OpenStreetMap | geocodificação |
| Cidades, postos, atrações | Overpass API / OpenStreetMap | base estável e legal de usar |
| Fotos e notas do Google Maps | [gosom/google-maps-scraper](https://github.com/gosom/google-maps-scraper) (MIT, Docker) | raspagem do Maps |
| "Google normal" | [deedy5/ddgs](https://github.com/deedy5/ddgs) (MIT) | metabusca, achar Instagram |
| Fotos de atrações | Wikipedia REST API | quando o OSM aponta o artigo |

## Rodando

**Só OpenStreetMap (mais rápido para começar):**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python cli.py carro "Alegrete, RS" "Vitória da Conquista, BA"
```

**Com Google Maps (fotos, notas, avaliações):**

```bash
docker run -d -p 8080:8080 -v "$PWD/gmapsdata:/gmapsdata" \
  -e DISABLE_TELEMETRY=1 gosom/google-maps-scraper -data-folder /gmapsdata

python cli.py carro "Alegrete, RS" "Vitória da Conquista, BA" --google
```

O gosom leva no mínimo uns 3 minutos por job. Por isso o código manda todas
as buscas da viagem num job só.

**Tudo junto (API + gosom):**

```bash
docker compose up --build
# abre http://localhost:8000/docs
```

## Endpoints

| Método | Rota | O que faz |
|---|---|---|
| POST | `/viagem/carro` | origem, destino, intervalo entre paradas → `202 {job_id}` |
| POST | `/viagem/aviao` | `[{cidade, dias}]` (escalas e destino) → `202 {job_id}` |
| GET | `/jobs/{id}` | `status` (`pendente`, `rodando`, `pronto`, `falhou`); quando pronto, `resultado` traz as paradas com cards |
| POST | `/swipe` | grava `{usuario, card, gostou}` |
| GET | `/perfil/{usuario}` | taxa de aceite por categoria, tipo e faixa de preço |
| POST | `/triagem` | `{respostas: [{pergunta, resposta}]}` → próxima pergunta ou `fim` com o resumo do gosto |
| POST | `/cards/ranquear` | `{cards, resumo}` → os mesmos cards, os 30 primeiros reordenados pela IA |
| POST | `/roteiro/carro` | `{itens, explicacoes, fonte}`: os aceitos pelo km da estrada; com `usar_ia: true` e `contexto`, a IA ajusta ao horário e explica cada parada |
| POST | `/roteiro/cidade` | divide os aceitos em dias, na melhor ordem de visita |

Mandando `usuario` em `/viagem/*`, os cards já avaliados somem e os novos vêm
ordenados pelo gosto aprendido nos swipes anteriores.

A API não coleta nada sozinha: rode o worker junto (`python -m app.worker`, ou
`docker compose up`). Os endpoints de IA respondem mesmo sem `GROQ_API_KEY`:
`/triagem` e `/roteiro/carro` trazem `"fonte": "fixa"` ou `"geometria"` no
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

## Como as paradas são escolhidas (modo carro)

1. Calcula a rota e marca um ponto a cada `intervalo_km` (padrão 200 km, umas 2,5 h).
2. Em volta de cada ponto, escolhe a cidade que equilibra tamanho (população) e
   distância da estrada.
3. Busca atrações, restaurantes e postos num raio de 8 km da cidade (15 km no destino).
4. Prioriza pelo Google (nota ajustada pelo número de avaliações, para 4,9 com
   6 avaliações não ganhar de 4,6 com 2 mil) e completa com o OpenStreetMap.

## Avisos importantes

- **Termos de uso:** raspar o Google Maps e a busca do Google viola os termos
  deles. Para uso pessoal e protótipo costuma funcionar. Para produto público,
  troque `gmaps.py` pela Places API oficial; o resto do código não muda.
- **Bloqueio:** em volume alto o Google bloqueia o IP. Mantenha `-c` baixo e
  use cache. O gosom aceita proxies.
- **Servidores públicos (OSRM, Nominatim, Overpass):** são para uso leve. Em
  produção, suba os seus via Docker. As URLs são configuráveis por
  `PV_OSRM_URL`, `PV_NOMINATIM_URL` e `PV_OVERPASS_URL`.
- Troque o e-mail em `PV_USER_AGENT`; o Nominatim exige identificação.

## Próximos passos sugeridos

- **Fila e banco no Supabase:** trocar o SQLite de `fila.py` e `preferencias.py`
  pelo Postgres (`SELECT … FOR UPDATE SKIP LOCKED`), com a mesma interface.
- **Cache por cidade** (30 dias) das respostas do OSM e do gosom, para não
  raspar de novo a mesma cidade.
- **Push:** o worker avisa o app pelo Expo Push quando o job termina.
