# Groq: plano gratuito ou Developer

Status: **decidido em 25/11/2026**. Passar para o plano Developer antes de o beta passar de 12 viagens por dia, com limite de gasto no console. A conta e os números estão abaixo.

## Como medir

Cada chamada que chega ao Groq é somada por modelo e por dia (UTC) na tabela `uso_ia` do Postgres, compartilhada pela API e pelo worker (`services/coletor/app/uso_ia.py`, migração `20261113040000_uso_ia.sql`). Se a cota do Groq virar em outro horário, o dia do alerta e o da cota podem não bater por algumas horas.

- **Terminal:** `python cli.py uso-ia --dias 30` em `services/coletor` (precisa de `PV_DATABASE_URL`). Mostra uma linha por dia e modelo, com chamadas, tokens e a % da cota diária. A linha que passou de 80% sai marcada com `ALERTA`.
- **HTTP:** `GET /uso/ia?dias=30` com o cabeçalho `X-Admin-Token: $PV_ADMIN_TOKEN` devolve os mesmos números em JSON. Sem `PV_ADMIN_TOKEN` configurado, a rota responde 404.
- **Alerta:** quando um modelo passa de 80% da cota do dia (requisições ou tokens), o log do coletor registra `ALERTA cota do Groq`, uma vez por modelo e por dia (coluna `alertado` da tabela).

As cotas usadas no cálculo vêm de `PV_GROQ_COTA_REQ_DIA` (padrão 1000) e `PV_GROQ_COTA_TOKENS_DIA` (padrão 200000). Depois de mudar de plano, ajuste as duas para os limites novos, ou o alerta dispara cedo demais.

## Limites do plano gratuito

Por modelo e por organização (várias chaves não somam):

| | por minuto | por dia |
| --- | --- | --- |
| Requisições | 30 | 1.000 |
| Tokens | 8.000 | 200.000 |

## Uso medido por viagem

Medição de 24/11/2026 ([resultados do relatório](https://liaa-leonardo.github.io/#resultados)): **uns 17 mil tokens por viagem completa**, sendo 1,1 mil por parada (ranqueamento, gpt-oss-20b) e 4,1 mil no roteiro (gpt-oss-120b). Numa viagem típica de umas 12 paradas, isso dá:

| Modelo | Uso | Tokens por viagem |
| --- | --- | --- |
| gpt-oss-20b | ranqueamento, 1 chamada por parada | ~12,9 mil |
| gpt-oss-120b | roteiro, 1 chamada por viagem | ~4,1 mil |

A triagem (gpt-oss-120b) roda uma vez por pessoa nova e não entra na conta por viagem. A estimativa antiga, de 27 mil tokens por viagem, era anterior à medição e fica descartada.

### O que isso dá no plano gratuito

| Viagens por dia | gpt-oss-20b (% de 200 mil) | gpt-oss-120b (% de 200 mil) |
| --- | --- | --- |
| 10 | 129 mil (65%) | 41 mil (21%) |
| 50 | 645 mil (323%) | 205 mil (103%) |
| 200 | 2,58 milhões (1.290%) | 820 mil (410%) |

- O gargalo é o gpt-oss-20b: a cota de tokens acaba em **umas 15 viagens por dia**, e o alerta de 80% dispara perto de **12 viagens por dia**.
- Requisições não travam: 12 chamadas por viagem dão umas 83 viagens antes das 1.000 requisições do dia.
- O limite por minuto (8 mil tokens) é menor que o ranqueamento de uma viagem só (12,9 mil). Duas viagens ao mesmo tempo já mandam parte das paradas para o plano B (ordem estatística, sem IA).

## Custo no plano Developer

Preços por milhão de tokens na [documentação de modelos do Groq](https://console.groq.com/docs/models), consultada em 25/11/2026:

| Modelo | Entrada | Saída |
| --- | --- | --- |
| openai/gpt-oss-120b | US$ 0,15 | US$ 0,60 |
| openai/gpt-oss-20b | US$ 0,075 | US$ 0,30 |

A medição dá o total de tokens, sem separar entrada e saída. Por isso a conta usa a divisão estimada pelo código (`app/ia.py`): no ranqueamento, uns 85% de entrada e 15% de saída; no roteiro, 70% e 30%. Como teto, a coluna "pior caso" cobra todos os tokens pelo preço de saída, o que cobre os tokens de raciocínio do gpt-oss, que contam como saída.

Por viagem:

- ranqueamento: 12,9 mil × (0,85 × 0,075 + 0,15 × 0,30) / 1 milhão = US$ 0,0014
- roteiro: 4,1 mil × (0,70 × 0,15 + 0,30 × 0,60) / 1 milhão = US$ 0,0012
- total: **uns US$ 0,0026 por viagem** (pior caso: US$ 0,0063)

Por mês (30 dias):

| Viagens por dia | Viagens por mês | Custo estimado | Pior caso |
| --- | --- | --- | --- |
| 10 | 300 | US$ 0,77 | US$ 1,90 |
| 50 | 1.500 | US$ 3,86 | US$ 9,50 |
| 200 | 6.000 | US$ 15,43 | US$ 37,98 |

A triagem soma uns US$ 0,001 por pessoa nova (estimativa pelo código, sem medição). O cache de prompt do Groq dá 50% de desconto na entrada repetida (o texto de sistema) e os tokens em cache não contam no limite ([documentação](https://console.groq.com/docs/prompt-caching), consultada em 25/11/2026), então o valor real tende a ficar abaixo da coluna "custo estimado".

**Limites do Developer.** A [página de limites](https://console.groq.com/docs/rate-limits) do Groq não deixa claro qual tabela vale para cada plano. Fontes de terceiros citam, para o gpt-oss-20b no Developer, 1.000 requisições e 250 mil tokens por minuto ([developersdigest](https://www.developersdigest.tech/models/free-api/groq), [morphllm](https://www.morphllm.com/groq-pricing)). Depois da troca, confira os números reais em `console.groq.com/settings/limits` e ajuste `PV_GROQ_COTA_REQ_DIA` e `PV_GROQ_COTA_TOKENS_DIA`.

## Decisão

**Passar para o plano Developer agora, antes de o beta passar de umas 12 viagens por dia.**

Por quê:

1. Com 10 viagens por dia, o gratuito ainda cabe, mas já usa 65% da cota do gpt-oss-20b. Com 50 ou 200 viagens por dia, ele não cabe: a maior parte das paradas cairia no plano B, e a IA deixaria de existir para quem usa.
2. O limite por minuto já atrapalha hoje: duas viagens montadas ao mesmo tempo estouram os 8 mil tokens por minuto.
3. O custo é baixo. No pior caso, 200 viagens por dia custam menos de US$ 40 por mês.

Como fazer:

- Ativar o Developer em `console.groq.com/settings/billing/plans`, com cartão da organização.
- Pôr um limite de gasto mensal de US$ 10 no console para o beta, e subir para US$ 50 se o uso passar de 50 viagens por dia.
- Ajustar `PV_GROQ_COTA_REQ_DIA` e `PV_GROQ_COTA_TOKENS_DIA` para os limites novos, para o alerta de 80% continuar útil.
- Manter o plano B como está. Ele continua cobrindo erro, demora de mais de 10 s e 429.

Quando rever: se o custo de uma semana em `uso-ia` passar de 2 vezes a coluna "pior caso" para o número de viagens do período, ou se o ranqueamento em lote (#95) mudar muito os tokens por viagem. Nesse caso, refazer a conta com uma medição nova.
