# Estrada
Pista curva com o nome das cidades da rota correndo por ela, a assinatura visual do Desvio.

**O consumidor fornece:** `cidades` na ordem da rota; opcionalmente `variante` (`curva` ou `subida`), `velocidade`, `parado` e `largura`.

- Lugar certo: a tela Carregando rota (enquanto os lugares são buscados) e o topo do Roteiro. No máximo uma Estrada por tela.
- A pista é `asfalto` com bordas `faixa`; o texto, em `estrada`, é `on-asfalto`.
- O texto corre sozinho e para quando o sistema pede menos movimento (`prefers-reduced-motion`) ou com `parado`.
- O SVG tem `aria-label` com a rota inteira; o texto em movimento é escondido do leitor de tela.
- Não coloque informação essencial só na Estrada: ela é ilustração. A lista de paradas está no StopItem.
