# Groq: plano gratuito ou Developer

Status: **pendente**. Falta o uso real do beta fechado (#44). Esta página tem a conta e o que medir; a decisão entra aqui quando os números chegarem.

## Como medir

Cada chamada que chega ao Groq é somada por modelo e por dia na tabela `uso_ia` (`services/coletor/app/uso_ia.py`):

- `GET /uso/ia?dias=30`, com o cabeçalho `X-Admin-Token: $PV_ADMIN_TOKEN`, devolve chamadas, tokens e a fração da cota usada em cada dia. Sem `PV_ADMIN_TOKEN` configurado, a rota responde 404.
- Quando um modelo passa de 80% da cota do dia (requisições ou tokens), o log do coletor registra `ALERTA cota do Groq`, uma vez por modelo e por dia.

## Limites do plano gratuito

Por modelo e por organização (várias chaves não somam):

| | por minuto | por dia |
| --- | --- | --- |
| Requisições | 30 | 1.000 |
| Tokens | 8.000 | 200.000 |

## Estimativa por viagem (antes do beta)

Estimativa feita a partir do código (`app/ia.py`), não de medição. Os tokens de raciocínio do gpt-oss contam como saída, então a saída real pode ser maior.

| Chamada | Modelo | Quando | Tokens por chamada |
| --- | --- | --- | --- |
| Triagem | gpt-oss-120b | até 4 por pessoa, uma vez | ~300 entrada + ~400 saída |
| Ranqueamento | gpt-oss-20b | 1 por parada (até 30 cards) | ~1.800 entrada + ~300 saída |
| Roteiro | gpt-oss-120b | 1 por viagem | ~2.800 entrada + ~1.200 saída |

Viagem típica do PRD: Alegrete a Vitória da Conquista, 2.731 km, uma parada a cada 200 km, umas 13 paradas.

- gpt-oss-20b: 13 chamadas e uns 27 mil tokens. A cota diária de 200 mil tokens dá **umas 7 viagens por dia**, que é o gargalo.
- gpt-oss-120b: 1 chamada e uns 4 mil tokens por viagem, mais uns 2.800 por pessoa nova.

**Achado:** as 13 chamadas de ranqueamento de uma viagem somam uns 27 mil tokens, mais que os 8 mil tokens **por minuto** do plano gratuito. O limitador espera no máximo 10 s, então hoje a maior parte das paradas cai no plano B (ordem estatística, sem IA) já na primeira viagem. Vale olhar isso no `uso_ia` do beta, antes de qualquer outra métrica de ranqueamento.

## Custo no plano Developer

Preços por milhão de tokens na [documentação do Groq](https://console.groq.com/docs/models), consultada em 11/2026. Confira antes de decidir.

| Modelo | Entrada | Saída |
| --- | --- | --- |
| gpt-oss-120b | US$ 0,15 | US$ 0,60 |
| gpt-oss-20b | US$ 0,075 | US$ 0,30 |

Por viagem:
- ranqueamento: 23,4 mil × 0,075 + 3,9 mil × 0,30, uns US$ 0,003
- roteiro: 2,8 mil × 0,15 + 1,2 mil × 0,60, uns US$ 0,001

Total: **uns US$ 0,004 por viagem**, mais uns US$ 0,001 por pessoa nova (triagem).

| Viagens por mês | Custo estimado | Com margem 2× (raciocínio) |
| --- | --- | --- |
| 300 (10 por dia) | US$ 1,20 | US$ 2,40 |
| 3.000 (100 por dia) | US$ 12 | US$ 24 |
| 30.000 (1.000 por dia) | US$ 120 | US$ 240 |

O cache automático de prompt do Groq dá 50% de desconto na entrada repetida (o texto de sistema), então o valor real tende a ficar abaixo disso.

## Decisão

A preencher depois do beta, com:

1. o pico diário de tokens do gpt-oss-20b em `/uso/ia`;
2. quantas paradas caíram no plano B por limite por minuto;
3. o custo mensal recalculado com os tokens medidos.

Regra proposta: passar para o Developer quando qualquer modelo passar de 80% da cota diária em 3 dias de uma mesma semana, ou se o plano B por limite atingir mais de 20% das paradas.
